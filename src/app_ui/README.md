# Sentiva Chat Support UI

A polished React-based chat interface for Sentiva's RAG-powered customer support demo.

## Overview

This is a Databricks App that serves a React single-page application (SPA) with a FastAPI backend. The frontend is a clean, modern chat interface styled for Sentiva, a consumer digital-safety company. The backend proxies API calls to a separate agent service and serves the built React frontend.

## Structure

```
src/app_ui/
├── frontend/                    # React + Vite frontend
│   ├── src/
│   │   ├── main.tsx            # React entry point
│   │   ├── App.tsx             # Root component
│   │   ├── styles.css          # Polished, responsive CSS
│   │   └── components/
│   │       ├── Chat.tsx        # Main chat interface
│   │       ├── MessageBubble.tsx # Message display with sources/timings
│   │       ├── SuggestionCards.tsx # Quick question cards
│   │       └── TypingIndicator.tsx # Loading animation
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── index.html
├── server.py                    # FastAPI app: serves dist/ + proxies /api/*
├── app.yaml                     # Databricks App config
├── requirements.txt             # Python dependencies
├── build.sh                     # Build script
└── README.md                    # This file
```

## Features

- **Modern Chat UI**: Clean, professional design with light/dark mode support
- **Session Tracking**: Each user gets a persistent session ID (stored in localStorage)
- **Quick Question Cards**: Multilingual suggestion chips for common questions (en/ja/fr/de)
- **Source Attribution**: Collapsible sources section showing retrieval context
- **Observability**: Displays retrieval, LLM, and total latency; trace ID for debugging
- **Error Handling**: Graceful error messages and retry capability
- **Responsive**: Mobile-friendly layout that works on all screen sizes
- **Accessible**: WCAG-friendly color contrast, keyboard navigation, semantic HTML

## Building Locally

### Prerequisites
- Node.js 18+ (for frontend)
- Python 3.10+ (for backend)
- npm or yarn

### Steps

1. **Install frontend dependencies:**
   ```bash
   cd src/app_ui/frontend
   npm ci
   ```

2. **Build frontend:**
   ```bash
   npm run build
   ```
   This creates a `dist/` directory with the optimized SPA.

3. **Install backend dependencies:**
   ```bash
   cd ..  # back to src/app_ui
   pip install -r requirements.txt
   ```

4. **Run locally (with mock data):**
   ```bash
   USE_MOCK=true python -m uvicorn server:app --host 0.0.0.0 --port 8080
   ```

5. **Or run with a real agent API:**
   ```bash
   AGENT_API_URL=https://your-agent-api-url python -m uvicorn server:app --host 0.0.0.0 --port 8080
   ```

6. **Access the app:**
   - Navigate to `http://localhost:8080`

### Development

For live frontend development:
```bash
cd frontend
npm run dev
# Vite will proxy /api/* to http://localhost:8080 (run server.py separately)
```

## Environment Variables

- **`AGENT_API_URL`** (optional): URL of the agent API to proxy chat requests to.
  - Example: `https://app-a.cloud.databricks.com`
  - If not set and `USE_MOCK=false`, the app returns a 500 error.

- **`USE_MOCK`** (optional): Set to `true` to return mock responses without calling the agent API.
  - Useful for local testing and demos.
  - Default: `false`

## API Contract

The app expects the agent API to implement:

### `POST /api/chat`
Request:
```json
{
  "session_id": "uuid-string",
  "message": "user question"
}
```

Response:
```json
{
  "answer": "answer text",
  "sources": [
    {
      "title": "Source Title",
      "source_uri": "https://example.com/...",
      "product": "Shield|Alert|Family|ID|Scan",
      "lang": "en|ja|fr|de|..."
    }
  ],
  "timings": {
    "retrieval_ms": 45,
    "llm_ms": 230,
    "total_ms": 275
  },
  "trace_id": "trace-uuid"
}
```

### `GET /api/health`
Response:
```json
{ "status": "ok" }
```

## Databricks App Deployment

This app is deployed via Databricks Assets Bundles (DAB). The `app.yaml` file configures:
- App name and description
- Command to start the server
- Environment variables

To deploy:
1. Add this app to your `databricks.yml` DAB configuration
2. Set `AGENT_API_URL` in the DAB environment or app resource
3. Run `databricks app deploy` (or your DAB deploy process)

## Styling

The UI uses a custom CSS system with:
- **Color scheme**: Indigo primary (`#4f46e5`), clean grays
- **Dark mode**: Respects `prefers-color-scheme: dark`
- **Responsive**: Mobile-first design with breakpoints at 640px
- **Animations**: Smooth transitions and keyframe animations for loading states

## Troubleshooting

### Build fails with module errors
- Ensure Node.js is up to date: `node -v` (18+)
- Delete `node_modules` and `package-lock.json`, then `npm ci` again

### Frontend not served (404)
- Verify `frontend/dist/` exists: `ls -la src/app_ui/frontend/dist`
- Re-run `npm run build` in the frontend directory

### API requests fail
- Check `AGENT_API_URL` is set correctly (if not using `USE_MOCK=true`)
- Verify Databricks authentication is working
- Check server logs for proxy errors

### Mock responses not working
- Ensure `USE_MOCK=true` is set
- Check server logs confirm mock mode is active

## Brand Guidelines

This app showcases the **Sentiva** brand:
- **Tagline**: "Digital safety, simplified."
- **Products**: Sentiva Shield (antivirus), Sentiva Alert (fraud detection), Sentiva Family (family safety), Sentiva ID (identity/VPN), Sentiva Scan (free security check)
- **No references to other brands**: This is explicitly checked in the UI and build process

## License

Databricks App internal use.
