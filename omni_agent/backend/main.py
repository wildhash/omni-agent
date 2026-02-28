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
      -d '{"task": "book flight from SFO to NYC", "context": {"date": "2026-03-15"}}'
"""

import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from omni_agent.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator()
app = FastAPI(title="Omni-Agent API", version="0.1.0")


class TaskRequest(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = None


def _get_weaviate_client():
    """Return a Weaviate client, or *None* if the server is unavailable."""
    try:
        import weaviate  # type: ignore

        url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
        client = weaviate.Client(url)
        return client
    except Exception:
        return None


@app.post("/task")
async def handle_task(request: TaskRequest) -> Dict:
    """Delegate a task to the appropriate agent and log it to memory."""
    try:
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/memory")
async def recall_memory(query: str) -> Dict:
    """Retrieve task history entries semantically similar to *query*."""
    client = _get_weaviate_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Memory store unavailable.")
    result = (
        client.query.get("TaskHistory", ["content", "context", "result"])
        .with_near_text({"concepts": [query]})
        .do()
    )
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
