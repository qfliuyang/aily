from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import aily.main as main
from aily.source_store import SourceStore
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter


pytestmark = pytest.mark.contract


async def _wait_for_source_status(store: SourceStore, source_id: str, status: str) -> dict:
    async def _poll() -> dict:
        while True:
            source = await store.get_source(source_id)
            if source and source["status"] == status:
                return source
            await asyncio.sleep(0.05)

    return await asyncio.wait_for(_poll(), timeout=5)


async def _run_source_worker_until_status(
    store: SourceStore,
    source_id: str,
    status: str,
) -> dict:
    stop = asyncio.Event()
    original_store = main.source_store
    original_stop = main.source_worker_stop
    main.source_store = store
    main.source_worker_stop = stop
    worker = asyncio.create_task(main._source_worker_loop("chaos-readiness-worker"))
    try:
        return await _wait_for_source_status(store, source_id, status)
    finally:
        stop.set()
        await asyncio.wait_for(worker, timeout=3)
        main.source_store = original_store
        main.source_worker_stop = original_stop


@pytest.mark.asyncio
async def test_chaos_provider_outage_becomes_visible_failure_without_losing_upload(
    tmp_path: Path,
) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    original_mind = main.dikiwi_mind
    try:
        stored = await store.store_upload(
            upload_id="provider-outage-upload",
            filename="provider-outage.txt",
            content_type="text/plain",
            data=b"provider outage should preserve this source",
        )
        await store.enqueue_source_job(
            source_id=stored["source_id"],
            job_type="process_upload_source",
            payload={"upload_id": "provider-outage-upload", "filename": "provider-outage.txt"},
        )
        main.dikiwi_mind = None

        failed = await _run_source_worker_until_status(store, stored["source_id"], "failed")
        counts = await store.get_source_job_counts()
        preserved = await store.read_stored_object(stored["source_id"])

        assert failed["metadata"]["error"] == "DIKIWI Mind is not initialized"
        assert preserved == b"provider outage should preserve this source"
        assert counts["failed"] == 1
    finally:
        main.dikiwi_mind = original_mind
        await store.close()


@pytest.mark.asyncio
async def test_chaos_bad_url_fails_closed_and_is_queryable(
    tmp_path: Path,
) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    original_private_network = main.SETTINGS.url_intake_allow_private_network
    try:
        stored = await store.store_url(url="http://127.0.0.1:9/private")
        await store.enqueue_source_job(
            source_id=stored["source_id"],
            job_type="process_url_source",
            payload={"upload_id": "bad-url", "url": "http://127.0.0.1:9/private"},
        )
        main.SETTINGS.url_intake_allow_private_network = False

        failed = await _run_source_worker_until_status(store, stored["source_id"], "failed")
        counts = await store.get_source_job_counts()

        assert "non-public address" in failed["metadata"]["error"]
        assert counts["failed"] == 1
    finally:
        main.SETTINGS.url_intake_allow_private_network = original_private_network
        await store.close()


@pytest.mark.asyncio
async def test_chaos_bad_file_missing_object_becomes_visible_failure(
    tmp_path: Path,
) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        stored = await store.store_upload(
            upload_id="bad-file-upload",
            filename="missing-object.pdf",
            content_type="application/pdf",
            data=b"%PDF-bad-file",
        )
        Path(stored["storage_path"]).unlink()
        await store.enqueue_source_job(
            source_id=stored["source_id"],
            job_type="process_upload_source",
            payload={"upload_id": "bad-file-upload", "filename": "missing-object.pdf"},
        )

        failed = await _run_source_worker_until_status(store, stored["source_id"], "failed")
        counts = await store.get_source_job_counts()

        assert "Stored object missing" in failed["metadata"]["error"]
        assert counts["failed"] == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_chaos_duplicate_submission_does_not_create_second_source(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        first = await store.store_upload(
            upload_id="dup-1",
            filename="first.txt",
            content_type="text/plain",
            data=b"same chaos content",
        )
        second = await store.store_upload(
            upload_id="dup-2",
            filename="second.txt",
            content_type="text/plain",
            data=b"same chaos content",
        )
        listing = await store.list_sources()

        assert first["duplicate"] is False
        assert second["duplicate"] is True
        assert second["source_id"] == first["source_id"]
        assert len(listing["sources"]) == 1
    finally:
        await store.close()


def test_chaos_obsidian_unavailable_fails_before_silent_write(tmp_path: Path) -> None:
    unavailable_vault = tmp_path / "vault-is-a-file"
    unavailable_vault.write_text("not a directory", encoding="utf-8")

    with pytest.raises(OSError):
        DikiwiObsidianWriter(vault_path=unavailable_vault)

    assert unavailable_vault.read_text(encoding="utf-8") == "not a directory"


@pytest.mark.asyncio
async def test_chaos_worker_restart_requeues_stale_running_source_job(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        stored = await store.store_upload(
            upload_id="restart-upload",
            filename="restart.txt",
            content_type="text/plain",
            data=b"worker restart source",
        )
        await store.update_status(stored["source_id"], "processing")
        job = await store.enqueue_source_job(
            source_id=stored["source_id"],
            job_type="process_upload_source",
            payload={"upload_id": "restart-upload"},
        )
        claimed = await store.claim_next_source_job(worker_id="dead-worker")
        assert claimed is not None
        assert claimed["job_id"] == job["job_id"]

        db = store._check_db()
        await db.execute(
            "UPDATE source_jobs SET locked_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?",
            (job["job_id"],),
        )
        await db.commit()

        recovered = await store.requeue_stale_running_source_jobs(stale_after_seconds=60)
        counts = await store.get_source_job_counts()
        source = await store.get_source(stored["source_id"])

        assert recovered == 1
        assert counts["retry_pending"] == 1
        assert source is not None
        assert source["status"] == "retry_pending"
        assert source["metadata"]["last_error"] == "stale worker lock recovered"
    finally:
        await store.close()
