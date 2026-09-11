import os
import json
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Configuration
USE_MOCK = os.getenv("USE_MOCK", "false").lower() == "true"


def _resolve_agent_url() -> str:
    """AGENT_API_URL env, else auto-discover App A ('sentiva-agent-api') via the SDK."""
    url = os.getenv("AGENT_API_URL", "").rstrip("/")
    if url:
        return url
    app_name = os.getenv("AGENT_APP_NAME", "sentiva-agent-api")
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        # Prefer typed API when present; fall back to REST (portable across SDK versions).
        try:
            a = w.apps.get(name=app_name)
            u = getattr(a, "url", "")
        except Exception:
            resp = w.api_client.do("GET", f"/api/2.0/apps/{app_name}")
            u = (resp or {}).get("url", "")
        u = (u or "").rstrip("/")
        print(f"  Discovered agent app URL: {u or 'EMPTY'}")
        return u
    except Exception as e:  # pragma: no cover
        print(f"  Could not auto-discover agent app URL: {e}")
        return ""


AGENT_API_URL = _resolve_agent_url()

# Get the directory where server.py is located
BASE_DIR = Path(__file__).parent
DIST_DIR = BASE_DIR / "frontend" / "dist"

# Global HTTP client
http_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global http_client
    # The tool-calling agent makes multiple LLM calls; allow generous headroom (and let
    # it be tuned via env). 30s was too tight and produced "Request to agent API timed out".
    _timeout = float(os.getenv("AGENT_TIMEOUT_S", "120"))
    http_client = httpx.AsyncClient(timeout=_timeout)
    print(f"Starting Sentiva Chat App")
    print(f"  AGENT_API_URL: {AGENT_API_URL or 'NOT SET'}")
    print(f"  USE_MOCK: {USE_MOCK}")
    print(f"  DIST_DIR: {DIST_DIR}")
    yield
    # Shutdown
    await http_client.aclose()


app = FastAPI(title="Sentiva Chat App", lifespan=lifespan)


def get_mock_response():
    """Return a mock API response for testing."""
    return {
        "answer": "Sentiva Shield is our flagship antivirus and security suite. It provides real-time threat protection, malware scanning, and advanced security features for your devices. It's available on Windows, macOS, iOS, and Android. Visit our website for current pricing and plans.",
        "sources": [
            {
                "title": "Sentiva Shield Features and Pricing",
                "source_uri": "https://example.com/shield",
                "product": "Shield",
                "lang": "en",
            },
            {
                "title": "Security Comparison Guide",
                "source_uri": "https://example.com/comparison",
                "product": "Shield",
                "lang": "en",
            },
        ],
        "timings": {
            "retrieval_ms": 45,
            "llm_ms": 230,
            "total_ms": 275,
        },
        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
    }


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/info")
async def info():
    """Expose the agent API base URL so the UI can render a copy-paste curl command."""
    return {"agent_api_url": AGENT_API_URL or ""}


@app.get("/api/token")
async def get_token(request: Request):
    """Return a bearer token the caller can use to hit the agent API from curl.

    Prefers the signed-in viewer's own token (x-forwarded-access-token, present when
    the app has user authorization enabled); falls back to the app service principal
    token. Both are accepted by the agent app's OAuth front door. Short-lived (~1h).
    For demo convenience only.
    """
    user_token = request.headers.get("x-forwarded-access-token")
    if user_token:
        return {"token": user_token, "kind": "user", "note": "your workspace token (~1h)"}
    try:
        from databricks.sdk.core import Config
        cfg = Config()
        auth = cfg.authenticate()  # {"Authorization": "Bearer <token>"}
        tok = (auth.get("Authorization", "") or "").replace("Bearer ", "", 1)
        if tok:
            return {"token": tok, "kind": "service_principal", "note": "app service-principal token (~1h)"}
    except Exception as e:
        return JSONResponse({"detail": f"could not mint token: {e}"}, status_code=500)
    return JSONResponse({"detail": "no token available"}, status_code=500)


@app.post("/api/chat")
async def chat(request: Request):
    """Proxy chat requests to the agent API or return mock response."""
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"detail": f"Invalid request body: {str(e)}"}, status_code=400)

    session_id = body.get("session_id")
    message = body.get("message")

    if not session_id or not message:
        return JSONResponse(
            {"detail": "Missing required fields: session_id, message"},
            status_code=400,
        )

    # If USE_MOCK is enabled, return mock response
    if USE_MOCK:
        return get_mock_response()

    # Otherwise, proxy to agent API
    if not AGENT_API_URL:
        return JSONResponse(
            {
                "detail": "AGENT_API_URL not configured and USE_MOCK is disabled. "
                "Set AGENT_API_URL environment variable or enable USE_MOCK=true."
            },
            status_code=500,
        )

    try:
        headers = {"Content-Type": "application/json"}
        # Prefer forwarding the logged-in user's token — App A is user-OAuth gated and
        # the user already has access to it. Databricks injects this header in the app.
        user_token = request.headers.get("x-forwarded-access-token")
        if user_token:
            headers["Authorization"] = f"Bearer {user_token}"
        else:
            # Fallback: service-principal auth (authenticate() returns a header dict).
            try:
                from databricks.sdk.core import Config
                headers.update(Config().authenticate())
            except Exception as e:
                print(f"Warning: Could not get Databricks token: {e}")

        # Proxy the request to the agent API
        response = await http_client.post(
            f"{AGENT_API_URL}/api/chat",
            json={"session_id": session_id, "message": message},
            headers=headers,
        )

        if response.status_code != 200:
            error_detail = response.text
            try:
                error_data = response.json()
                error_detail = error_data.get("detail", error_detail)
            except:
                pass
            return JSONResponse(
                {"detail": f"Agent API error: {error_detail}"},
                status_code=response.status_code,
            )

        return response.json()

    except httpx.TimeoutException:
        return JSONResponse(
            {"detail": "Request to agent API timed out"},
            status_code=504,
        )
    except httpx.RequestError as e:
        return JSONResponse(
            {"detail": f"Failed to connect to agent API: {str(e)}"},
            status_code=502,
        )
    except Exception as e:
        print(f"Proxy error: {e}")
        return JSONResponse(
            {"detail": f"Internal server error: {str(e)}"},
            status_code=500,
        )


def _agent_headers(request: Request):
    headers = {"Content-Type": "application/json"}
    user_token = request.headers.get("x-forwarded-access-token")
    if user_token:
        headers["Authorization"] = f"Bearer {user_token}"
    else:
        try:
            from databricks.sdk.core import Config
            headers.update(Config().authenticate())
        except Exception as e:
            print(f"Warning: Could not get Databricks token: {e}")
    return headers


@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    """Proxy the agent's Server-Sent Events stream through to the browser."""
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"detail": f"Invalid request body: {str(e)}"}, status_code=400)
    session_id, message = body.get("session_id"), body.get("message")
    if not session_id or not message:
        return JSONResponse({"detail": "Missing required fields: session_id, message"}, status_code=400)

    if USE_MOCK or not AGENT_API_URL:
        # Mock/misconfig: emit the non-streaming mock as a single SSE 'done' so the UI still works.
        mock = get_mock_response()
        payload = mock.body.decode() if hasattr(mock, "body") else json.dumps({"answer": "", "sources": [], "timings": {}})
        async def mockgen():
            import json as _j
            d = _j.loads(payload) if isinstance(payload, str) else payload
            yield f"data: {_j.dumps({'type':'token','text': d.get('answer','')})}\n\n"
            yield f"data: {_j.dumps({'type':'done','sources': d.get('sources',[]),'timings': d.get('timings',{}),'trace_id': d.get('trace_id','')})}\n\n"
        return StreamingResponse(mockgen(), media_type="text/event-stream")

    headers = _agent_headers(request)

    async def gen():
        try:
            async with http_client.stream(
                "POST", f"{AGENT_API_URL}/api/chat/stream",
                json={"session_id": session_id, "message": message}, headers=headers,
            ) as resp:
                if resp.status_code != 200:
                    text = (await resp.aread()).decode(errors="replace")
                    yield f"data: {json.dumps({'type':'error','error': f'Agent API {resp.status_code}: {text[:200]}'})}\n\n"
                    return
                async for line in resp.aiter_lines():
                    if line:
                        yield line + "\n"
                    else:
                        yield "\n"  # preserve SSE event boundaries
        except httpx.TimeoutException:
            yield f"data: {json.dumps({'type':'error','error':'Request to agent API timed out'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','error': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# Serve static files
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="frontend")
else:
    print(f"Warning: DIST_DIR does not exist: {DIST_DIR}")


# Fallback for SPA routing
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve index.html for SPA routing."""
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)

    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse({"detail": "Frontend not built. Run: cd frontend && npm run build"}, status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=False)
