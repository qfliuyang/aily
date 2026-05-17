from __future__ import annotations

from pathlib import Path

import pytest

from aily.inbox import WatchedInboxService
from aily.source_store import SourceStore


pytestmark = pytest.mark.contract


async def test_watched_inbox_registers_file_and_queues_source_job(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        inbox = tmp_path / "Inbox"
        source_file = inbox / "brief.md"
        inbox.mkdir()
        source_file.write_text("# Brief\n\nA useful source.", encoding="utf-8")
        service = WatchedInboxService(
            source_store=store,
            inbox_path=inbox,
            file_stable_seconds=0,
            max_pending_jobs=10,
        )

        results = await service.scan_once()
        jobs = await store.list_source_jobs(status="queued")
        source = await store.get_source(results[0].source_id)

        assert len(results) == 1
        assert results[0].source_type == "file"
        assert results[0].queued is True
        assert source is not None
        assert source["kind"] == "upload"
        assert source["status"] == "queued"
        assert source["metadata"]["intake"] == "watched_inbox"
        assert source["metadata"]["origin_path"] == str(source_file)
        assert jobs["total"] == 1
        assert jobs["jobs"][0]["job_type"] == "process_upload_source"
        assert jobs["jobs"][0]["payload"]["origin_path"] == str(source_file)
    finally:
        await store.close()


async def test_watched_inbox_registers_url_pointer_file(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        inbox = tmp_path / "Inbox"
        url_file = inbox / "market-research.url"
        inbox.mkdir()
        url_file.write_text("[InternetShortcut]\nURL=https://example.com/research\n", encoding="utf-8")
        service = WatchedInboxService(
            source_store=store,
            inbox_path=inbox,
            file_stable_seconds=0,
            max_pending_jobs=10,
        )

        results = await service.scan_once()
        jobs = await store.list_source_jobs(status="queued")
        source = await store.get_source(results[0].source_id)

        assert len(results) == 1
        assert results[0].source_type == "url"
        assert results[0].queued is True
        assert source is not None
        assert source["kind"] == "url"
        assert source["normalized_source"] == "https://example.com/research"
        assert source["metadata"]["source_kind"] == "url_pointer"
        assert jobs["jobs"][0]["job_type"] == "process_url_source"
        assert jobs["jobs"][0]["payload"]["url"] == "https://example.com/research"
    finally:
        await store.close()


async def test_watched_inbox_duplicate_source_is_not_requeued_after_restart(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        inbox = tmp_path / "Inbox"
        source_file = inbox / "same.txt"
        inbox.mkdir()
        source_file.write_text("same durable content", encoding="utf-8")
        first_service = WatchedInboxService(
            source_store=store,
            inbox_path=inbox,
            file_stable_seconds=0,
            max_pending_jobs=10,
        )
        first_results = await first_service.scan_once()
        await store.update_status(first_results[0].source_id, "completed", {"pipeline_id": "pipe-1"})
        queued = await store.list_source_jobs(status="queued")
        await store.complete_source_job(queued["jobs"][0]["job_id"])

        restarted_service = WatchedInboxService(
            source_store=store,
            inbox_path=inbox,
            file_stable_seconds=0,
            max_pending_jobs=10,
        )
        second_results = await restarted_service.scan_once()
        counts = await store.get_source_job_counts()

        assert len(second_results) == 1
        assert second_results[0].duplicate is True
        assert second_results[0].queued is False
        assert second_results[0].source_id == first_results[0].source_id
        assert counts["queued"] == 0
        assert counts["completed"] == 1
    finally:
        await store.close()
