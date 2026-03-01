"""FastAPI backend for Omni-Agent.

Endpoints
---------
POST /task
    Delegate a task to the appropriate agent.
GET /memory
    Retrieve relevant task history from Weaviate.

Example
-------
.. code-block:: bash

    curl -X POST http://localhost:8000/task \\
      -H "Content-Type: application/json" \\
      -H "X-API-Key: $OMNI_AGENT_API_KEY" \\
      -d '{"task": "book flight from SFO to NYC", "context": {"date": "2026-03-15"}}'
"""

import base64
import logging
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from omni_agent.orchestrator import AgentOrchestrator
from omni_agent.vision.vision_agent import build_analyser

logger = logging.getLogger(__name__)

orchestrator = AgentOrchestrator()
_vision_analyser = None  # lazy-init

app = FastAPI(title="Omni-Agent API / OmniSight", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("OMNI_AGENT_API_KEY")
ALLOW_INSECURE_NOAUTH = os.getenv("OMNI_AGENT_ALLOW_INSECURE_NOAUTH") == "1"


class TaskRequest(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = None


def _require_api_key(x_api_key: str | None) -> None:
    if ALLOW_INSECURE_NOAUTH:
        return
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Server not configured. Set OMNI_AGENT_API_KEY or OMNI_AGENT_ALLOW_INSECURE_NOAUTH=1.",
        )
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _get_weaviate_client():
    """Return a Weaviate client, or *None* if the server is unavailable."""
    try:
        import weaviate  # type: ignore

        url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
        api_key = os.getenv("WEAVIATE_API_KEY")
        auth = weaviate.AuthApiKey(api_key=api_key) if api_key else None
        client = weaviate.Client(url, auth_client_secret=auth)
        return client
    except Exception:
        return None


@app.post("/task")
async def handle_task(
    request: TaskRequest,
    x_api_key: str | None = Header(default=None),
) -> Dict:
    """Delegate a task to the appropriate agent and log it to memory."""
    try:
        _require_api_key(x_api_key)
        result = orchestrator.delegate(request.task, request.context)

        client = _get_weaviate_client()
        if client is not None:
            try:
                client.data_object.create(
                    data_object={
                        "content": request.task,
                        "context": str(request.context),
                        "result": str(result),
                    },
                    class_name="TaskHistory",
                )
            except Exception:
                pass  # Memory logging is best-effort

        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/memory")
async def recall_memory(
    query: str,
    x_api_key: str | None = Header(default=None),
) -> Dict:
    """Retrieve task history entries matching *query* via keyword search."""
    _require_api_key(x_api_key)
    client = _get_weaviate_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Memory store unavailable.")
    result = client.query.get("TaskHistory", ["content", "context", "result"]).with_bm25(
        query=query
    ).do()
    return result


@app.websocket("/ws/vision")
async def vision_ws(ws: WebSocket) -> None:
    """WebSocket endpoint for real-time frame analysis.

    Client sends JSON: {"type": "frame", "data": "<base64 jpeg>", "w": int, "h": int}
    Server replies:    {"type": "analysis", "result": {...}}  |  {"type": "error", "msg": "..."}
    """
    global _vision_analyser
    await ws.accept()
    if _vision_analyser is None:
        _vision_analyser = build_analyser()
    await ws.send_json({"type": "status", "message": "OmniSight vision pipeline ready"})
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") != "frame":
                continue
            b64 = data.get("data", "")
            if not b64:
                continue
            jpeg_bytes = base64.b64decode(b64)
            try:
                result = _vision_analyser.analyse(jpeg_bytes)
                await ws.send_json({"type": "analysis", "result": result.to_dict()})
            except Exception as exc:
                logger.exception("Vision analysis failed")
                await ws.send_json({"type": "error", "msg": str(exc)})
    except WebSocketDisconnect:
        logger.info("Vision client disconnected")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
