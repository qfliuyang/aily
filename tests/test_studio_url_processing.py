from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import aily.main as main
from aily.orchestration.runs import WorkflowRunStore
from aily.processing.processors import ExtractedContent
from aily.source_store import SourceStore


pytestmark = pytest.mark.contract


class _FakeProcessingRouter:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def process(self, data: bytes, *, filename: str, http_content_type: str) -> ExtractedContent:
        return ExtractedContent(
            text=data.decode("utf-8"),
            title=filename,
            source_type="text",
            metadata={"filename": filename},
        )

    async def process_url(self, url: str, browser_manager=None) -> ExtractedContent:
        return ExtractedContent(
            text="Fetched article body with enough real content for DIKIWI.",
            title="Fetched Article",
            source_type="web",
            metadata={"url": url},
        )


class _FakeDikiwiMind:
    async def process_input(self, drop):
        assert drop.rain_type.name == "URL"
        assert drop.stream_type.name == "FETCH_ANALYZE"
        assert drop.metadata["processing_method"] in {"studio_url_fetch_extract_dikiwi", "durable_studio_url_fetch_extract_dikiwi"}
        assert "Fetched article body" in drop.content
        return SimpleNamespace(
            pipeline_id="url-pipeline-1",
            final_stage_reached=SimpleNamespace(name="IMPACT"),
            stage_results=[SimpleNamespace(success=True), SimpleNamespace(success=True)],
        )


class _FakeFoundationMind:
    def __init__(self) -> None:
        self.foundation_calls = 0
        self.full_calls = 0

    @staticmethod
    def _drop_requests_full_dikiwi(drop) -> bool:
        return bool((drop.metadata or {}).get("dikiwi_mode") == "full")

    async def process_input_foundation(self, drop):
        self.foundation_calls += 1
        return SimpleNamespace(
            pipeline_id="foundation-pipeline",
            final_stage_reached=SimpleNamespace(name="KNOWLEDGE"),
            stage_results=[
                SimpleNamespace(stage=SimpleNamespace(name="DATA"), success=True),
                SimpleNamespace(stage=SimpleNamespace(name="INFORMATION"), success=True),
                SimpleNamespace(stage=SimpleNamespace(name="KNOWLEDGE"), success=True),
            ],
        )

    async def process_input(self, drop):
        self.full_calls += 1
        return SimpleNamespace(
            pipeline_id="full-pipeline",
            final_stage_reached=SimpleNamespace(name="IMPACT"),
            stage_results=[SimpleNamespace(success=True)],
        )

    async def process_triggered_iwi(self, *, motive: str, workflow_run_id: str, node_ids: list[str]):
        self.full_calls += 1
        return SimpleNamespace(
            pipeline_id=f"pipeline-{workflow_run_id}",
            final_stage_reached=SimpleNamespace(name="IMPACT"),
            stage_results=[
                SimpleNamespace(success=True),
                SimpleNamespace(success=True),
                SimpleNamespace(success=True),
            ],
        )


def _foundation_drop(*, full: bool = False):
    from aily.gating.drainage import RainDrop, RainType, StreamType

    return RainDrop(
        id="drop-1",
        rain_type=RainType.DOCUMENT,
        content="# Canonical Markdown",
        source="test",
        stream_type=StreamType.EXTRACT_ANALYZE,
        metadata={"dikiwi_mode": "full"} if full else {},
    )


@pytest.mark.asyncio
async def test_main_ingestion_helper_uses_foundation_when_enabled(monkeypatch) -> None:
    original = main.SETTINGS.dikiwi_foundation_only_ingestion
    mind = _FakeFoundationMind()
    try:
        main.SETTINGS.dikiwi_foundation_only_ingestion = True
        monkeypatch.setattr(main, "dikiwi_mind", mind)

        result = await main._process_dikiwi_ingestion(_foundation_drop())
    finally:
        main.SETTINGS.dikiwi_foundation_only_ingestion = original

    assert result.final_stage_reached.name == "KNOWLEDGE"
    assert mind.foundation_calls == 1
    assert mind.full_calls == 0


@pytest.mark.asyncio
async def test_main_ingestion_helper_allows_manual_full_dikiwi(monkeypatch) -> None:
    original = main.SETTINGS.dikiwi_foundation_only_ingestion
    mind = _FakeFoundationMind()
    try:
        main.SETTINGS.dikiwi_foundation_only_ingestion = True
        monkeypatch.setattr(main, "dikiwi_mind", mind)

        result = await main._process_dikiwi_ingestion(_foundation_drop(full=True))
    finally:
        main.SETTINGS.dikiwi_foundation_only_ingestion = original

    assert result.final_stage_reached.name == "IMPACT"
    assert mind.foundation_calls == 0
    assert mind.full_calls == 1


@pytest.mark.asyncio
async def test_iwi_workflow_trigger_creates_run_and_executes_inline(monkeypatch, tmp_path: Path) -> None:
    store = WorkflowRunStore(tmp_path / "workflow-runs.db")
    await store.initialize()
    events: list[tuple[str, dict]] = []
    mind = _FakeFoundationMind()

    async def fake_emit(event_type: str, **payload):
        events.append((event_type, payload))

    try:
        monkeypatch.setattr(main, "workflow_run_store", store)
        monkeypatch.setattr(main, "dikiwi_mind", mind)
        monkeypatch.setattr(main, "emit_ui_event", fake_emit)

        response = await main._ui_iwi_workflow_trigger(
            {
                "motive": "Turn this topic into an impact analysis.",
                "node_ids": ["info-a", "info-b"],
                "run_inline": True,
            }
        )
        saved = await store.get_run(response["workflow_run_id"])

        assert response["workflow_kind"] == "triggered_iwi"
        assert saved is not None
        assert saved.status == "completed"
        assert saved.current_node == "IMPACT"
        assert saved.metadata["final_stage"] == "IMPACT"
        assert mind.full_calls == 1
        assert "workflow_run_queued" in [event_type for event_type, _ in events]
        assert "workflow_run_completed" in [event_type for event_type, _ in events]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_studio_url_processing_fetches_and_enters_dikiwi(monkeypatch, tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        source = await store.store_url(url="https://example.com/research", metadata={"intake": "studio_url"})
        monkeypatch.setattr(main, "source_store", store)
        monkeypatch.setattr(main, "ProcessingRouter", _FakeProcessingRouter)
        monkeypatch.setattr(main, "dikiwi_mind", _FakeDikiwiMind())
        main.ui_upload_tasks.clear()

        await main._process_ui_url(source["source_id"], "https://example.com/research")

        updated = await store.get_source(source["source_id"])
        assert updated is not None
        assert updated["status"] == "completed"
        assert updated["metadata"]["pipeline_id"] == "url-pipeline-1"
        assert updated["metadata"]["final_stage"] == "IMPACT"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_studio_retry_reprocesses_failed_url_source(monkeypatch, tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        source = await store.store_url(url="https://example.com/retry", metadata={"intake": "studio_url"})
        await store.update_status(source["source_id"], "failed", {"error": "transient"})
        failed_source = await store.get_source(source["source_id"])
        assert failed_source is not None

        monkeypatch.setattr(main, "source_store", store)
        monkeypatch.setattr(main, "ProcessingRouter", _FakeProcessingRouter)
        monkeypatch.setattr(main, "dikiwi_mind", _FakeDikiwiMind())
        main.ui_upload_tasks.clear()

        retry = await main._retry_source(failed_source)
        assert retry["started"] is True
        assert retry["job_id"]
        job = await store.claim_next_source_job(worker_id="test-worker")
        assert job is not None
        result = await main._process_url_source_job(job)
        await store.complete_source_job(job["job_id"])

        updated = await store.get_source(source["source_id"])
        assert result == "completed"
        assert updated is not None
        assert updated["status"] == "completed"
        assert updated["metadata"]["pipeline_id"] == "url-pipeline-1"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_process_source_job_with_foundation_graph_creates_workflow(monkeypatch, tmp_path: Path) -> None:
    source_store = SourceStore(tmp_path / "source.db", tmp_path / "objects", tmp_path / "markdown")
    workflow_store = WorkflowRunStore(tmp_path / "workflow-runs.db")
    await source_store.initialize()
    await workflow_store.initialize()
    events: list[tuple[str, dict]] = []
    original_data_dir = main.SETTINGS.aily_data_dir

    async def fake_emit(event_type: str, **payload):
        events.append((event_type, payload))

    try:
        main.SETTINGS.aily_data_dir = tmp_path / "aily-data"
        source = await source_store.store_text(
            text="Graph-backed intake text with enough content.",
            title="Graph Memo",
            metadata={"intake": "graph-test"},
        )
        job = await source_store.enqueue_source_job(
            source_id=source["source_id"],
            job_type="process_upload_source",
            payload={"upload_id": "upload-graph", "filename": "graph-memo.txt"},
        )
        claimed = await source_store.claim_next_source_job(worker_id="test-worker")
        assert claimed is not None

        monkeypatch.setattr(main, "source_store", source_store)
        monkeypatch.setattr(main, "workflow_run_store", workflow_store)
        monkeypatch.setattr(main, "ProcessingRouter", _FakeProcessingRouter)
        monkeypatch.setattr(main, "dikiwi_mind", _FakeFoundationMind())
        monkeypatch.setattr(main, "emit_ui_event", fake_emit)

        result = await main._process_source_job_with_foundation_graph(claimed)
        updated = await source_store.get_source(source["source_id"])
        markdown_package = await source_store.get_markdown_package(source["source_id"])
        runs = await workflow_store.list_runs()

        assert result == "completed"
        assert updated is not None
        assert updated["status"] == "completed"
        assert updated["metadata"]["pipeline_id"] == "foundation-pipeline"
        assert markdown_package is not None
        assert len(runs) == 1
        assert runs[0].workflow_kind == "source_foundation"
        assert runs[0].status == "completed"
        assert "workflow_run_started" in [event_type for event_type, _ in events]
        assert "workflow_run_completed" in [event_type for event_type, _ in events]
    finally:
        main.SETTINGS.aily_data_dir = original_data_dir
        await workflow_store.close()
        await source_store.close()


@pytest.mark.asyncio
async def test_handle_ui_url_enqueues_durable_source_job(monkeypatch, tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        monkeypatch.setattr(main, "source_store", store)
        monkeypatch.setattr(main.SETTINGS, "source_job_max_pending", 10)

        result = await main._handle_ui_url("https://example.com/durable")
        counts = await store.get_source_job_counts()

        assert result["processing"] is True
        assert result["job_id"]
        assert counts["queued"] == 1
        job = await store.claim_next_source_job(worker_id="test-worker")
        assert job is not None
        assert job["job_type"] == "process_url_source"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_process_url_source_job_fetches_and_enters_dikiwi(monkeypatch, tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        source = await store.store_url(url="https://example.com/research", metadata={"intake": "studio_url"})
        job = await store.enqueue_source_job(
            source_id=source["source_id"],
            job_type="process_url_source",
            payload={"upload_id": "url-test", "url": "https://example.com/research"},
        )
        claimed = await store.claim_next_source_job(worker_id="test-worker")
        assert claimed is not None
        monkeypatch.setattr(main, "source_store", store)
        monkeypatch.setattr(main, "ProcessingRouter", _FakeProcessingRouter)
        monkeypatch.setattr(main, "dikiwi_mind", _FakeDikiwiMind())

        result = await main._process_url_source_job(claimed)
        await store.complete_source_job(job["job_id"])

        updated = await store.get_source(source["source_id"])
        assert result == "completed"
        assert updated is not None
        assert updated["status"] == "completed"
        assert updated["metadata"]["pipeline_id"] == "url-pipeline-1"
    finally:
        await store.close()
