from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aily.ui.router import create_ui_router


def test_ui_router_status_and_graph_endpoints() -> None:
    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=None,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            enable_uploads=False,
        )
    )
    client = TestClient(app)

    status = client.get("/api/ui/status")
    graph = client.get("/api/ui/graph")
    pipeline = client.get("/api/ui/pipelines/pipe-1")

    assert status.status_code == 200
    assert status.json()["queue"]["pending"] == 1
    assert graph.status_code == 200
    assert graph.json()["nodes"][0]["id"] == "n1"
    assert pipeline.status_code == 200
    assert pipeline.json()["pipeline_id"] == "pipe-1"


async def _status_provider():
    return {
        "queue": {"pending": 1, "running": 0, "completed": 0, "failed": 0, "total": 1},
        "graph": {"information": 3},
        "active_pipelines": [],
        "active_uploads": [],
        "daemons": {"queue_worker": True},
        "minds": {"dikiwi": True},
    }


async def _graph_provider():
    return {"nodes": [{"id": "n1"}], "edges": []}


async def _pipeline_provider(pipeline_id: str):
    return {"pipeline_id": pipeline_id, "status": "pipeline_completed", "events": []}
