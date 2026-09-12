"""App A entry — MLflow AgentServer hosting the Sentiva agent (see agent.py).

AgentServer (databricks-agents / mlflow.genai.agent_server) provides the FastAPI app,
the /responses + /invocations endpoints, streaming, and request handling. We keep the
MLflow UC trace-location binding here so per-request traces land in the Unity Catalog
OTel tables (requirement #3), exactly as before.
"""
import os
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sentiva-agent-app")

# Bind the MLflow experiment to a UC trace location BEFORE the agent traces anything, so
# spans export to dbx_agent_lakebase.rag.<prefix>_otel_* (needs MLFLOW_TRACING_SQL_WAREHOUSE_ID).
try:
    import mlflow
    mlflow.set_tracking_uri("databricks")
    from mlflow.entities.trace_location import UnityCatalog
    mlflow.set_experiment(
        experiment_name=os.getenv("MLFLOW_EXPERIMENT", "/Shared/sentiva-rag-traces"),
        trace_location=UnityCatalog(
            catalog_name=os.getenv("TRACE_CATALOG", "dbx_agent_lakebase"),
            schema_name=os.getenv("TRACE_SCHEMA", "rag"),
            table_prefix=os.getenv("TRACE_TABLE_PREFIX", "sentiva"),
        ),
    )
    log.info("MLflow tracing -> Unity Catalog trace location")
except Exception as e:
    log.warning("UC trace_location bind failed (%s); tracing may use the default experiment", e)

from mlflow.genai.agent_server import AgentServer
import agent  # noqa: F401,E402  — registers @invoke/@stream handlers + autolog

# App B (React) is our customer-site simulator, so no built-in chat proxy/UI here.
agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=False)
app = agent_server.app  # uvicorn entry: `uvicorn app:app`
