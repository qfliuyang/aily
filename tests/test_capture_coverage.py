from __future__ import annotations

from pathlib import Path

import pytest

from aily.source_store import SourceStore


pytestmark = pytest.mark.contract


async def _queued_job(store: SourceStore, *, source_id: str, job_type: str, payload: dict) -> dict:
    await store.update_status(source_id, "queued", {"intake_verified": True})
    job = await store.enqueue_source_job(source_id=source_id, job_type=job_type, payload=payload)
    counts = await store.get_source_job_counts()
    jobs = await store.list_source_jobs(status="queued")

    assert counts["queued"] == 1
    assert jobs["total"] == 1
    assert jobs["jobs"][0]["job_id"] == job["job_id"]
    assert jobs["jobs"][0]["source_id"] == source_id
    assert jobs["jobs"][0]["payload"] == payload
    assert jobs["jobs"][0]["source_metadata"]["intake_verified"] is True
    return job


@pytest.mark.asyncio
async def test_file_capture_creates_durable_source_queue_item_and_duplicate_policy(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "sources.db", tmp_path / "objects")
    await store.initialize()
    try:
        first = await store.store_upload(
            upload_id="file-1",
            filename="capture.txt",
            content_type="text/plain",
            data=b"file capture content",
            metadata={"intake": "studio_upload"},
        )
        second = await store.store_upload(
            upload_id="file-2",
            filename="capture-copy.txt",
            content_type="text/plain",
            data=b"file capture content",
            metadata={"intake": "studio_upload"},
        )

        source = await store.get_source(first["source_id"])
        payload = {
            "upload_id": "file-1",
            "filename": "capture.txt",
            "content_type": "text/plain",
        }
        await _queued_job(store, source_id=first["source_id"], job_type="process_upload_source", payload=payload)

        assert first["duplicate"] is False
        assert second["duplicate"] is True
        assert second["source_id"] == first["source_id"]
        assert source is not None
        assert source["kind"] == "upload"
        assert source["metadata"]["intake"] == "studio_upload"
        assert await store.read_stored_object(first["source_id"]) == b"file capture content"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_url_capture_creates_durable_source_queue_item_and_duplicate_policy(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "sources.db", tmp_path / "objects")
    await store.initialize()
    try:
        first = await store.store_url(url="https://example.com/research", metadata={"intake": "studio_url"})
        second = await store.store_url(url="https://example.com/research", metadata={"intake": "studio_url"})

        source = await store.get_source(first["source_id"])
        payload = {"upload_id": f"url-{first['source_id']}", "url": "https://example.com/research"}
        await _queued_job(store, source_id=first["source_id"], job_type="process_url_source", payload=payload)

        assert first["duplicate"] is False
        assert second["duplicate"] is True
        assert second["source_id"] == first["source_id"]
        assert source is not None
        assert source["kind"] == "url"
        assert source["normalized_source"] == "https://example.com/research"
        assert source["metadata"]["intake"] == "studio_url"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_text_capture_creates_durable_source_queue_item_and_duplicate_policy(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "sources.db", tmp_path / "objects")
    await store.initialize()
    try:
        first = await store.store_text(
            title="Daily thought",
            text="A durable text capture should become a queued source.",
            metadata={"intake": "studio_text"},
        )
        second = await store.store_text(
            title="Different title should still deduplicate by text",
            text="A durable text capture should become a queued source.",
            metadata={"intake": "studio_text"},
        )

        source = await store.get_source(first["source_id"])
        payload = {
            "upload_id": f"text-{first['source_id']}",
            "filename": "Daily thought.txt",
            "content_type": "text/plain; charset=utf-8",
            "source_kind": "text",
        }
        await _queued_job(store, source_id=first["source_id"], job_type="process_upload_source", payload=payload)

        assert first["duplicate"] is False
        assert second["duplicate"] is True
        assert second["source_id"] == first["source_id"]
        assert source is not None
        assert source["kind"] == "text"
        assert source["metadata"]["intake"] == "studio_text"
        assert source["metadata"]["title"] == "Daily thought"
        assert await store.read_stored_object(first["source_id"]) == (
            b"A durable text capture should become a queued source."
        )
    finally:
        await store.close()
