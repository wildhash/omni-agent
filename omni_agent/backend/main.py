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

import asyncio
import base64
import binascii
import logging
import os
import uuid
from typing import Any, Dict, Optional

import anyio
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from omni_agent.orchestrator import AgentOrchestrator
from omni_agent.vision.vision_agent import build_analyser

logger = logging.getLogger(__name__)

orchestrator = AgentOrchestrator()

app = FastAPI(title="Omni-Agent API / OmniSight", version="0.2.0")

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "OMNI_AGENT_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]
CORS_ALLOW_ORIGINS = ["*"] if "*" in CORS_ORIGINS else CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("OMNI_AGENT_API_KEY")
ALLOW_INSECURE_NOAUTH = os.getenv("OMNI_AGENT_ALLOW_INSECURE_NOAUTH") == "1"

MAX_FRAME_B64_LEN = int(os.getenv("OMNISIGHT_MAX_FRAME_B64", "2000000"))
MAX_FRAME_JPEG_BYTES = int(os.getenv("OMNISIGHT_MAX_FRAME_JPEG", "1500000"))
VISION_ANALYSIS_TIMEOUT_S = float(os.getenv("OMNISIGHT_ANALYSIS_TIMEOUT_S", "30"))

app.state.vision_lock = asyncio.Lock()
app.state.vision_sem = asyncio.Semaphore(int(os.getenv("OMNISIGHT_MAX_CONCURRENCY", "1")))
app.state.vision_analyser = None


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


def _ws_origin_allowed(origin: str | None) -> bool:
    if ALLOW_INSECURE_NOAUTH:
        return True
    if not origin:
        return True
    if "*" in CORS_ALLOW_ORIGINS:
        return True
    return origin in CORS_ALLOW_ORIGINS


def _get_ws_api_key(ws: WebSocket) -> str | None:
    return ws.query_params.get("api_key") or ws.headers.get("x-api-key")


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
    if not _ws_origin_allowed(ws.headers.get("origin")):
        await ws.close(code=1008)
        return

    try:
        _require_api_key(_get_ws_api_key(ws))
    except HTTPException:
        await ws.close(code=1008)
        return

    await ws.accept()

    async with app.state.vision_lock:
        if app.state.vision_analyser is None:
            try:
                app.state.vision_analyser = build_analyser()
            except Exception:
                logger.exception("Vision analyser init failed")
                await ws.send_json({"type": "error", "msg": "Vision analyser init failed"})
                await ws.close(code=1011)
                return
    analyser = app.state.vision_analyser

    await ws.send_json({"type": "status", "message": "OmniSight vision pipeline ready"})
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") != "frame":
                continue
            b64 = data.get("data", "")
            if not b64:
                continue
            if len(b64) > MAX_FRAME_B64_LEN:
                await ws.send_json({"type": "error", "msg": "Frame too large"})
                continue

            try:
                jpeg_bytes = base64.b64decode(b64, validate=True)
            except (binascii.Error, ValueError):
                await ws.send_json({"type": "error", "msg": "Invalid frame encoding"})
                continue

            if len(jpeg_bytes) > MAX_FRAME_JPEG_BYTES:
                await ws.send_json({"type": "error", "msg": "Frame too large"})
                continue

            try:
                async with app.state.vision_sem:
                    result = await asyncio.wait_for(
                        anyio.to_thread.run_sync(analyser.analyse, jpeg_bytes),
                        timeout=VISION_ANALYSIS_TIMEOUT_S,
                    )
                await ws.send_json({"type": "analysis", "result": result.to_dict()})
            except TimeoutError:
                await ws.send_json({"type": "error", "msg": "Vision analysis timed out"})
            except Exception:
                error_id = uuid.uuid4().hex[:10]
                logger.exception("Vision analysis failed (error_id=%s)", error_id)
                await ws.send_json(
                    {"type": "error", "msg": "Vision analysis failed", "error_id": error_id}
                )
    except WebSocketDisconnect:
        logger.info("Vision client disconnected")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
