"""Helpers to bridge a LangGraph agent's async stream to MLflow ResponsesAgent events.

Adapted from the official Databricks agent-langgraph template (agent_server/utils.py):
turns `agent.astream(stream_mode=["updates","messages"])` events into
ResponsesAgentStreamEvent objects (output items + text deltas).
"""
import json
import logging

from langchain_core.messages import AIMessageChunk, ToolMessage
from mlflow.types.responses import (
    ResponsesAgentStreamEvent,
    create_text_delta,
    output_to_responses_items_stream,
)


def get_session_id(request):
    """conversation_id (context) or custom_inputs.session_id."""
    if getattr(request, "context", None) and getattr(request.context, "conversation_id", None):
        return request.context.conversation_id
    ci = getattr(request, "custom_inputs", None)
    if isinstance(ci, dict):
        return ci.get("session_id")
    return None


async def process_agent_astream_events(async_stream):
    """Yield ResponsesAgentStreamEvent from a LangGraph astream (updates + messages modes)."""
    async for event in async_stream:
        if event[0] == "updates":
            for node_data in event[1].values():
                msgs = node_data.get("messages", []) if isinstance(node_data, dict) else []
                for msg in msgs:
                    if isinstance(msg, ToolMessage) and not isinstance(msg.content, str):
                        msg.content = json.dumps(msg.content)
                if msgs:
                    for item in output_to_responses_items_stream(msgs):
                        yield item
        elif event[0] == "messages":
            try:
                chunk = event[1][0]
                if isinstance(chunk, AIMessageChunk) and (content := chunk.content):
                    yield ResponsesAgentStreamEvent(**create_text_delta(delta=content, item_id=chunk.id))
            except Exception as e:
                logging.exception("stream event error: %s", e)
