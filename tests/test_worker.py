import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from aily.main import _dispatch_job


@pytest.mark.asyncio
async def test_dispatch_url_fetch():
    with patch("aily.main._process_url_job", new=AsyncMock()) as mock_url:
        job = {"type": "url_fetch", "payload": {"url": "https://example.com"}}
        await _dispatch_job(job)
        mock_url.assert_awaited_once_with(job)


@pytest.mark.asyncio
async def test_dispatch_daily_digest():
    with patch("aily.main._process_digest_job", new=AsyncMock()) as mock_digest:
        job = {"type": "daily_digest", "payload": {"open_id": "u1"}}
        await _dispatch_job(job)
        mock_digest.assert_awaited_once_with(job)


@pytest.mark.asyncio
async def test_dispatch_agent_request():
    with patch("aily.main._process_agent_job", new=AsyncMock()) as mock_agent:
        job = {"type": "agent_request", "payload": {"request": "hello"}}
        await _dispatch_job(job)
        mock_agent.assert_awaited_once_with(job)


@pytest.mark.asyncio
async def test_dispatch_unknown_job_type():
    job = {"type": "unknown", "payload": {}}
    with pytest.raises(ValueError, match="Unknown job type"):
        await _dispatch_job(job)


@pytest.mark.asyncio
async def test_worker_recovers_stale_primary_running_job(tmp_path: Path) -> None:
    from aily.queue.db import QueueDB
    from aily.queue.worker import JobWorker

    db = QueueDB(tmp_path / "queue.db")
    await db.initialize()
    processed: list[str] = []
    processed_event = asyncio.Event()

    async def processor(job: dict) -> None:
        processed.append(job["id"])
        processed_event.set()

    job_id = await db.enqueue("url_fetch", {"url": "https://example.com"})
    claimed = await db.dequeue()
    assert claimed is not None
    await db._db.execute(
        "UPDATE jobs SET locked_at = '2000-01-01 00:00:00' WHERE id = ?",
        (job_id,),
    )
    await db._db.commit()

    worker = JobWorker(db, processor, poll_interval=0.01, stale_running_seconds=60)
    await worker.start()
    await asyncio.wait_for(processed_event.wait(), timeout=1)
    await worker.stop()

    assert processed == [job_id]
    job = await db.get_job(job_id)
    assert job is not None
    assert job["status"] == "completed"
    await db.close()
