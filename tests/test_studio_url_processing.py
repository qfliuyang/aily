from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import aily.main as main
from aily.processing.processors import ExtractedContent
from aily.source_store import SourceStore


class _FakeProcessingRouter:
    def __init__(self, *args, **kwargs) -> None:
        pass

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
