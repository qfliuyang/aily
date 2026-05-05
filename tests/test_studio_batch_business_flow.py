from __future__ import annotations

from types import SimpleNamespace

import pytest

import aily.main as main


class FakeSourceStore:
    def __init__(self) -> None:
        self.statuses: list[tuple[str, str, dict | None]] = []
        self.reads: list[str] = []
        self.jobs: list[dict] = []

    async def read_stored_object(self, source_id: str) -> bytes:
        self.reads.append(source_id)
        return b"real stored bytes"

    async def update_status(self, source_id: str, status: str, metadata: dict | None = None) -> None:
        self.statuses.append((source_id, status, metadata))

    async def enqueue_source_job(self, **kwargs):
        job = {"job_id": "job-1", "job_type": kwargs["job_type"], **kwargs}
        self.jobs.append(job)
        return job


class FakeRouter:
    def __init__(self, browser_manager=None) -> None:
        self.browser_manager = browser_manager

    async def process(self, data: bytes, *, filename: str, http_content_type: str):
        assert data == b"real stored bytes"
        return SimpleNamespace(
            source_type="pdf",
            text="extracted text with enough signal for DIKIWI",
            title="Meaningful extracted title",
            metadata={"image_assets": ["00-Chaos/_assets/page-1.png"]},
        )


class FakeDikiwiMind:
    async def process_inputs_batched(self, drops):
        assert len(drops) == 1
        assert drops[0].raw_bytes == b""
        assert drops[0].content.startswith("# Meaningful extracted title")
        return SimpleNamespace(
            results=[
                SimpleNamespace(
                    pipeline_id="pipeline-1",
                    final_stage_reached=SimpleNamespace(name="IMPACT"),
                    stage_results=[],
                )
            ],
            incremental_ratio=0.25,
            incremental_threshold=0.05,
            higher_order_triggered=True,
        )


class FakeReactor:
    def __init__(self) -> None:
        self.llm_client = SimpleNamespace(model="kimi-k2", _provider_name=lambda: "kimi")
        self.calls: list[tuple[dict, bool, bool]] = []

    async def _gather_context(self) -> dict:
        return {"graph_nodes": ["n1", "n2"], "graph_edges": ["e1"]}

    async def evaluate_context(self, context: dict, *, persist: bool = False, output: bool = False, budget=None):
        self.calls.append((context, persist, output))
        return [SimpleNamespace(proposal_id="proposal-1")]


class FakeEntrepreneur:
    def __init__(self) -> None:
        self.llm_client = SimpleNamespace(model="deepseek-reasoner", _provider_name=lambda: "deepseek")
        self.runs = 0

    async def _run_session_wrapper(self) -> None:
        self.runs += 1


@pytest.mark.asyncio
async def test_studio_batch_reads_stored_bytes_and_runs_business_flow(monkeypatch) -> None:
    events: list[tuple[str, dict]] = []
    source_store = FakeSourceStore()
    reactor = FakeReactor()
    entrepreneur = FakeEntrepreneur()

    async def fake_emit(event_type: str, **payload):
        events.append((event_type, payload))

    monkeypatch.setattr(main, "source_store", source_store)
    monkeypatch.setattr(main, "ProcessingRouter", FakeRouter)
    monkeypatch.setattr(main, "dikiwi_mind", FakeDikiwiMind())
    monkeypatch.setattr(main, "innovation_scheduler", reactor)
    monkeypatch.setattr(main, "entrepreneur_scheduler", entrepreneur)
    monkeypatch.setattr(main, "emit_ui_event", fake_emit)

    await main._process_ui_upload_batch(
        "batch-1",
        [
            {
                "upload_id": "upload-1",
                "source_id": "source-1",
                "filename": "input.pdf",
                "content_type": "application/pdf",
                "size_bytes": 100,
                "sha256": "abc",
                "duplicate": False,
                "status": "accepted",
            }
        ],
    )

    assert source_store.reads == ["source-1"]
    assert ("source-1", "completed", {"batch_id": "batch-1", "pipeline_id": "pipeline-1", "final_stage": "IMPACT"}) in source_store.statuses
    assert reactor.calls
    _, persist, output = reactor.calls[0]
    assert persist is True
    assert output is True
    assert entrepreneur.runs == 1
    assert "proposal_generation_completed" in [event_type for event_type, _ in events]
    completed_events = [payload for event_type, payload in events if event_type == "upload_batch_completed"]
    assert completed_events
    assert completed_events[0]["business_flow"]["proposal_count"] == 1


@pytest.mark.asyncio
async def test_retry_upload_source_uses_durable_source_job(monkeypatch) -> None:
    events: list[tuple[str, dict]] = []
    source_store = FakeSourceStore()

    async def fake_emit(event_type: str, **payload):
        events.append((event_type, payload))

    monkeypatch.setattr(main, "source_store", source_store)
    monkeypatch.setattr(main, "emit_ui_event", fake_emit)

    retry = await main._retry_source(
        {
            "source_id": "sha256:abc123",
            "kind": "upload",
            "status": "failed",
            "filename": "input.pdf",
            "content_type": "application/pdf",
        }
    )

    assert retry["started"] is True
    assert source_store.reads == ["sha256:abc123"]
    assert source_store.statuses[-1][1] == "queued"
    assert source_store.jobs[0]["job_type"] == "process_upload_source"
    assert source_store.jobs[0]["priority"] == 50
    assert "source_job_queued" in [event_type for event_type, _ in events]
