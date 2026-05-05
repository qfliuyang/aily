from __future__ import annotations

from pathlib import Path

import pytest

from aily.source_store import SourceJobCapacityError, SourceStore


@pytest.mark.asyncio
async def test_source_store_persists_upload_and_detects_duplicate(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        first = await store.store_upload(
            upload_id="upload-1",
            filename="note.txt",
            content_type="text/plain",
            data=b"same content",
        )
        second = await store.store_upload(
            upload_id="upload-2",
            filename="copy.txt",
            content_type="text/plain",
            data=b"same content",
        )

        assert first["duplicate"] is False
        assert second["duplicate"] is True
        assert first["source_id"] == second["source_id"]
        assert Path(first["storage_path"]).read_bytes() == b"same content"
        assert (await store.get_source_for_upload("upload-2"))["source_id"] == first["source_id"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_source_store_status_survives_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    object_dir = tmp_path / "objects"
    store = SourceStore(db_path, object_dir)
    await store.initialize()
    first = await store.store_upload(
        upload_id="upload-1",
        filename="note.txt",
        content_type="text/plain",
        data=b"content",
    )
    await store.update_status(first["source_id"], "completed", {"pipeline_id": "pipe-1"})
    await store.close()

    reopened = SourceStore(db_path, object_dir)
    await reopened.initialize()
    try:
        source = await reopened.get_source(first["source_id"])
        listing = await reopened.list_sources()

        assert source is not None
        assert source["status"] == "completed"
        assert source["metadata"]["pipeline_id"] == "pipe-1"
        assert listing["sources"][0]["source_id"] == first["source_id"]
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_source_store_persists_url_identity(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        first = await store.store_url(url="https://example.com/a")
        second = await store.store_url(url="https://example.com/a")

        assert first["duplicate"] is False
        assert second["duplicate"] is True
        assert first["source_id"] == second["source_id"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_source_store_reads_failed_upload_object_for_retry(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        stored = await store.store_upload(
            upload_id="upload-1",
            filename="note.txt",
            content_type="text/plain",
            data=b"retry content",
        )
        await store.update_status(stored["source_id"], "failed", {"error": "boom"})

        failed = await store.list_failed_sources()
        data = await store.read_stored_object(stored["source_id"])

        assert [source["source_id"] for source in failed] == [stored["source_id"]]
        assert data == b"retry content"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_source_store_claims_and_retries_source_jobs(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        stored = await store.store_upload(
            upload_id="upload-1",
            filename="note.txt",
            content_type="text/plain",
            data=b"queued content",
        )
        job = await store.enqueue_source_job(
            source_id=stored["source_id"],
            job_type="process_upload_source",
            payload={"upload_id": "upload-1"},
        )

        claimed = await store.claim_next_source_job(worker_id="worker-1")
        assert claimed is not None
        assert claimed["job_id"] == job["job_id"]
        assert claimed["attempt_count"] == 1
        assert claimed["payload"]["upload_id"] == "upload-1"

        await store.retry_source_job(claimed["job_id"], error="DATA stage timed out after 240.0s", delay_seconds=0)
        counts = await store.get_source_job_counts()
        assert counts["retry_pending"] == 1

        claimed_again = await store.claim_next_source_job(worker_id="worker-1")
        assert claimed_again is not None
        assert claimed_again["job_id"] == job["job_id"]
        assert claimed_again["attempt_count"] == 2

        await store.complete_source_job(job["job_id"])
        counts = await store.get_source_job_counts()
        assert counts["completed"] == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_source_store_marks_retry_pending_with_metadata(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        stored = await store.store_upload(
            upload_id="upload-1",
            filename="note.txt",
            content_type="text/plain",
            data=b"retry content",
        )

        await store.mark_retry_pending(
            stored["source_id"],
            error="LLM failed after 1 attempts",
            stage="DATA",
            provider="kimi",
            model="kimi-k2.6",
            pipeline_id="pipeline-1",
            retry_delay_seconds=10,
        )
        source = await store.get_source(stored["source_id"])

        assert source is not None
        assert source["status"] == "retry_pending"
        assert source["metadata"]["last_failed_stage"] == "DATA"
        assert source["metadata"]["last_error"] == "LLM failed after 1 attempts"
        assert source["metadata"]["attempt_count"] == 1
        assert source["metadata"]["pipeline_id"] == "pipeline-1"
        assert source["metadata"]["next_retry_at"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_source_store_cancel_jobs_also_cancels_sources(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        stored = await store.store_upload(
            upload_id="upload-1",
            filename="note.txt",
            content_type="text/plain",
            data=b"queued content",
        )
        await store.update_status(stored["source_id"], "queued")
        job = await store.enqueue_source_job(
            source_id=stored["source_id"],
            job_type="process_upload_source",
        )

        cancelled = await store.cancel_running_source_jobs()
        source = await store.get_source(stored["source_id"])
        counts = await store.get_source_job_counts()

        assert cancelled == [job["job_id"]]
        assert source is not None
        assert source["status"] == "cancelled"
        assert counts["cancelled"] == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_source_store_requeues_stale_running_jobs(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        stored = await store.store_upload(
            upload_id="upload-1",
            filename="note.txt",
            content_type="text/plain",
            data=b"queued content",
        )
        await store.update_status(stored["source_id"], "processing")
        await store.enqueue_source_job(
            source_id=stored["source_id"],
            job_type="process_upload_source",
        )
        claimed = await store.claim_next_source_job(worker_id="worker-1")
        assert claimed is not None

        db = store._check_db()
        await db.execute(
            "UPDATE source_jobs SET locked_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?",
            (claimed["job_id"],),
        )
        await db.commit()

        recovered = await store.requeue_stale_running_source_jobs(stale_after_seconds=60)
        counts = await store.get_source_job_counts()
        source = await store.get_source(stored["source_id"])

        assert recovered == 1
        assert counts["retry_pending"] == 1
        assert source is not None
        assert source["status"] == "retry_pending"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_source_store_enforces_source_job_pending_capacity(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        stored = await store.store_upload(
            upload_id="upload-1",
            filename="note.txt",
            content_type="text/plain",
            data=b"queued content",
        )
        await store.enqueue_source_job(
            source_id=stored["source_id"],
            job_type="process_upload_source",
            max_pending=1,
        )

        with pytest.raises(SourceJobCapacityError):
            await store.enqueue_source_job(
                source_id=stored["source_id"],
                job_type="process_upload_source",
                max_pending=1,
            )

        counts = await store.get_source_job_counts()
        assert counts["queued"] == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_source_store_lists_source_jobs_with_source_context(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        stored = await store.store_upload(
            upload_id="upload-1",
            filename="note.txt",
            content_type="text/plain",
            data=b"queued content",
        )
        job = await store.enqueue_source_job(
            source_id=stored["source_id"],
            job_type="process_upload_source",
            payload={"upload_id": "upload-1"},
        )

        ledger = await store.list_source_jobs(limit=10)

        assert ledger["total"] == 1
        assert ledger["jobs"][0]["job_id"] == job["job_id"]
        assert ledger["jobs"][0]["filename"] == "note.txt"
        assert ledger["jobs"][0]["source_status"] == "stored"
        assert ledger["jobs"][0]["payload"]["upload_id"] == "upload-1"
    finally:
        await store.close()
