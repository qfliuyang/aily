from __future__ import annotations

import importlib.util
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aily.ui.router import create_ui_router
from aily.verify.run_registry import RunRegistry


HAS_MULTIPART = importlib.util.find_spec("python_multipart") is not None


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


def test_ui_router_auth_gate_when_configured() -> None:
    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=None,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            enable_uploads=False,
            auth_token="secret-token",
        )
    )
    client = TestClient(app)

    rejected = client.get("/api/ui/status")
    accepted = client.get("/api/ui/status", headers={"authorization": "Bearer secret-token"})

    assert rejected.status_code == 401
    assert accepted.status_code == 200


def test_ui_router_websocket_auth_gate_when_configured() -> None:
    import asyncio
    from aily.ui.events import ui_event_hub

    asyncio.run(ui_event_hub.emit("pipeline_started", pipeline_id="auth-pipe"))
    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=None,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            enable_uploads=False,
            auth_token="secret-token",
        )
    )
    client = TestClient(app)

    with client.websocket_connect("/api/ui/events?token=secret-token") as websocket:
        events = [websocket.receive_json() for _ in range(min(50, len(ui_event_hub.recent_events(limit=50))))]

    assert any(event["type"] == "pipeline_started" and event.get("pipeline_id") == "auth-pipe" for event in events)


def test_ui_router_rate_limit_rejects_abusive_upload_stream() -> None:
    from aily.security.rate_limit import FixedWindowRateLimiter

    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=None,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            enable_uploads=False,
            rate_limiter=FixedWindowRateLimiter(max_requests=1, window_seconds=60),
        )
    )
    client = TestClient(app)

    first = client.post("/api/ui/uploads")
    second = client.post("/api/ui/uploads")

    assert first.status_code == 503
    assert second.status_code == 429


def test_ui_router_run_registry_endpoints(tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        '{"run_id":"run-1","scenario":"unit","exit_code":0,"acceptance":{"mocked":false,"fake_components":[],"real_llm":true}}',
        encoding="utf-8",
    )
    (run_dir / "source-manifest.json").write_text("[]", encoding="utf-8")
    (run_dir / "ui-events.jsonl").write_text('{"type":"stage_started","stage":"DATA"}\n', encoding="utf-8")
    (run_dir / "llm-calls.jsonl").write_text('{"provider":"kimi"}\n', encoding="utf-8")

    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=None,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            run_registry=RunRegistry(runs_dir),
            enable_uploads=False,
        )
    )
    client = TestClient(app)

    runs = client.get("/api/ui/runs")
    detail = client.get("/api/ui/runs/run-1")
    events = client.get("/api/ui/runs/run-1/events")
    calls = client.get("/api/ui/runs/run-1/llm-calls")
    missing = client.get("/api/ui/runs/../secret")

    assert runs.status_code == 200
    assert runs.json()["runs"][0]["run_id"] == "run-1"
    assert detail.status_code == 200
    assert detail.json()["manifest"]["run_id"] == "run-1"
    assert events.json()["events"][0]["stage"] == "DATA"
    assert calls.json()["llm_calls"][0]["provider"] == "kimi"
    assert missing.status_code == 404


def test_ui_router_source_store_endpoints() -> None:
    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=None,
            url_handler=_url_handler,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            source_provider=_source_provider,
            source_detail_provider=_source_detail_provider,
            enable_uploads=False,
        )
    )
    client = TestClient(app)

    sources = client.get("/api/ui/sources")
    source = client.get("/api/ui/sources/source-1")
    missing = client.get("/api/ui/sources/missing")

    assert sources.status_code == 200
    assert sources.json()["sources"][0]["source_id"] == "source-1"
    assert source.status_code == 200
    assert source.json()["status"] == "completed"
    assert missing.status_code == 404


def test_ui_router_persisted_event_query_endpoint(tmp_path) -> None:
    from aily.ui.events import ui_event_hub

    event_log = tmp_path / "ui-events.jsonl"
    event_log.write_text(
        '{"id":"1","type":"stage_started","run_id":"run-1","pipeline_id":"pipe-1","upload_id":"up-1","stage":"DATA"}\n'
        '{"id":"2","type":"stage_started","run_id":"run-2","pipeline_id":"pipe-2","upload_id":"up-2","stage":"IMPACT"}\n',
        encoding="utf-8",
    )
    ui_event_hub.configure_persistence(event_log)

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

    response = client.get("/api/ui/events/query?run_id=run-1")

    assert response.status_code == 200
    assert response.json()["events"][0]["pipeline_id"] == "pipe-1"


def test_ui_router_proposal_entrepreneur_and_control_endpoints() -> None:
    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=None,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            proposal_provider=_proposal_provider,
            entrepreneurship_provider=_entrepreneurship_provider,
            control_handler=_control_handler,
            enable_uploads=False,
        )
    )
    client = TestClient(app)

    proposals = client.get("/api/ui/proposals")
    entrepreneurship = client.get("/api/ui/entrepreneurship")
    control = client.post("/api/ui/control", json={"action": "cancel_all_uploads"})

    assert proposals.status_code == 200
    assert proposals.json()["items"][0]["title"] == "Proposal A"
    assert entrepreneurship.status_code == 200
    assert entrepreneurship.json()["items"][0]["title"] == "Review A"
    assert control.status_code == 200
    assert control.json()["action"] == "cancel_all_uploads"


def test_ui_router_url_intake_endpoint() -> None:
    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=None,
            url_handler=_url_handler,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            enable_uploads=False,
        )
    )
    client = TestClient(app)

    response = client.post("/api/ui/sources/urls", json={"url": "https://example.com/a"})
    invalid = client.post("/api/ui/sources/urls", json={"url": "file:///tmp/a"})

    assert response.status_code == 200
    assert response.json()["source_id"].startswith("url:")
    assert invalid.status_code == 400


def test_ui_router_uploads_disabled_returns_service_unavailable() -> None:
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

    response = client.post("/api/ui/uploads")

    assert response.status_code == 503
    assert "python-multipart" in response.json()["detail"]


@pytest.mark.skipif(not HAS_MULTIPART, reason="python-multipart not installed")
def test_ui_router_upload_limit() -> None:
    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=_upload_handler,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            enable_uploads=True,
            max_files_per_request=1,
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/ui/uploads",
        files=[
            ("files", ("a.txt", BytesIO(b"a"), "text/plain")),
            ("files", ("b.txt", BytesIO(b"b"), "text/plain")),
        ],
    )

    assert response.status_code == 400
    assert "Too many files uploaded" in response.json()["detail"]


@pytest.mark.skipif(not HAS_MULTIPART, reason="python-multipart not installed")
def test_ui_router_upload_size_limit_rejects_before_handler() -> None:
    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=_failing_upload_handler,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            enable_uploads=True,
            max_upload_bytes=1,
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/ui/uploads",
        files=[("files", ("a.txt", BytesIO(b"alpha"), "text/plain"))],
    )

    assert response.status_code == 413
    assert "max upload size" in response.json()["detail"]


@pytest.mark.skipif(not HAS_MULTIPART, reason="python-multipart not installed")
def test_ui_router_uses_batch_upload_handler_for_multiple_files() -> None:
    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=_upload_handler,
            batch_upload_handler=_batch_upload_handler,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            enable_uploads=True,
            max_files_per_request=3,
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/ui/uploads",
        files=[
            ("files", ("a.txt", BytesIO(b"a"), "text/plain")),
            ("files", ("b.txt", BytesIO(b"b"), "text/plain")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "batched"
    assert payload["file_count"] == 2


@pytest.mark.skipif(not HAS_MULTIPART, reason="python-multipart not installed")
def test_ui_router_upload_accepts_file() -> None:
    app = FastAPI()
    app.include_router(
        create_ui_router(
            upload_handler=_upload_handler,
            status_provider=_status_provider,
            graph_provider=_graph_provider,
            pipeline_provider=_pipeline_provider,
            enable_uploads=True,
            max_files_per_request=2,
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/ui/uploads",
        files=[("files", ("a.txt", BytesIO(b"alpha"), "text/plain"))],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["uploads"][0]["filename"] == "a.txt"


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


async def _source_provider(limit: int, offset: int):
    return {
        "total": 1,
        "sources": [
            {
                "source_id": "source-1",
                "status": "completed",
                "filename": "a.txt",
                "size_bytes": 5,
            }
        ],
    }


async def _source_detail_provider(source_id: str):
    if source_id != "source-1":
        return None
    return {
        "source_id": "source-1",
        "status": "completed",
        "filename": "a.txt",
        "size_bytes": 5,
    }


async def _url_handler(url: str):
    return {
        "source_id": "url:" + ("a" * 64),
        "url": url,
        "sha256": "a" * 64,
        "duplicate": False,
        "status": "accepted",
    }


async def _upload_handler(file, upload_id: str):
    return {
        "upload_id": upload_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "status": "accepted",
    }


async def _failing_upload_handler(file, upload_id: str):
    raise AssertionError("oversized upload should be rejected before handler")


async def _batch_upload_handler(files, batch_id: str):
    return {
        "batch_id": batch_id,
        "file_count": len(files),
        "status": "batched",
    }


async def _proposal_provider(limit: int):
    return {"total": 1, "items": [{"title": "Proposal A", "note_path": "/vault/07-Proposal/a.md"}]}


async def _entrepreneurship_provider(limit: int):
    return {"total": 1, "items": [{"title": "Review A", "note_path": "/vault/08-Entrepreneurship/a.md"}]}


async def _control_handler(action: str, payload: dict):
    return {"action": action, "payload": payload}
