from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from aily.queue.db import QueueDB
from aily.queue.worker import JobWorker


pytestmark = pytest.mark.contract


async def _wait_for_job_status(db: QueueDB, job_id: str, status: str) -> dict:
    async def _poll() -> dict:
        while True:
            job = await db.get_job(job_id)
            if job and job["status"] == status:
                return job
            await asyncio.sleep(0.01)

    return await asyncio.wait_for(_poll(), timeout=2)


@pytest.mark.asyncio
async def test_jobworker_restart_processes_preexisting_pending_job(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.db"
    first_db = QueueDB(db_path)
    await first_db.initialize()
    job_id = await first_db.enqueue("url_fetch", {"url": "https://example.com/restart"})
    await first_db.close()

    restarted_db = QueueDB(db_path)
    await restarted_db.initialize()
    processed: list[str] = []
    processed_event = asyncio.Event()

    async def processor(job: dict) -> None:
        processed.append(job["id"])
        processed_event.set()

    worker = JobWorker(restarted_db, processor, poll_interval=0.01)
    await worker.start()
    try:
        await asyncio.wait_for(processed_event.wait(), timeout=2)
        completed = await _wait_for_job_status(restarted_db, job_id, "completed")
    finally:
        await worker.stop()
        await restarted_db.close()

    assert processed == [job_id]
    assert completed["retry_count"] == 0
    assert completed["error_message"] is None


@pytest.mark.asyncio
async def test_jobworker_failed_job_preserves_error_and_retry_count(tmp_path: Path) -> None:
    db = QueueDB(tmp_path / "queue.db")
    await db.initialize()
    attempts: list[int] = []
    job_id = await db.enqueue("url_fetch", {"url": "not-a-valid-url"})

    async def processor(job: dict) -> None:
        attempts.append(int(job["retry_count"]))
        raise ValueError("bad input visible failure")

    worker = JobWorker(db, processor, poll_interval=0.01, max_retries=3)
    await worker.start()
    try:
        failed = await _wait_for_job_status(db, job_id, "failed")
    finally:
        await worker.stop()
        await db.close()

    assert attempts == [0, 1, 2]
    assert failed["retry_count"] == 3
    assert failed["error_message"] == "bad input visible failure"


@pytest.mark.asyncio
async def test_jobworker_retry_pending_state_preserves_last_error(tmp_path: Path) -> None:
    db = QueueDB(tmp_path / "queue.db")
    await db.initialize()
    job_id = await db.enqueue("url_fetch", {"url": "https://example.com/transient"})
    job = await db.dequeue()
    assert job is not None

    will_retry = await db.retry_job(job_id, max_retries=3, error_message="transient provider outage")
    retry_job = await db.get_job(job_id)

    assert will_retry is True
    assert retry_job is not None
    assert retry_job["status"] == "pending"
    assert retry_job["retry_count"] == 1
    assert retry_job["error_message"] == "transient provider outage"
    await db.close()


@pytest.mark.asyncio
async def test_jobworker_recovers_stale_running_job_without_silent_loss(tmp_path: Path) -> None:
    db = QueueDB(tmp_path / "queue.db")
    await db.initialize()
    job_id = await db.enqueue("url_fetch", {"url": "https://example.com/stale"})
    claimed = await db.dequeue()
    assert claimed is not None
    assert claimed["id"] == job_id
    await db._db.execute(
        "UPDATE jobs SET locked_at = '2000-01-01 00:00:00' WHERE id = ?",
        (job_id,),
    )
    await db._db.commit()

    processed: list[str] = []
    processed_event = asyncio.Event()

    async def processor(job: dict) -> None:
        processed.append(job["id"])
        processed_event.set()

    worker = JobWorker(db, processor, poll_interval=0.01, stale_running_seconds=60)
    await worker.start()
    try:
        await asyncio.wait_for(processed_event.wait(), timeout=2)
        completed = await _wait_for_job_status(db, job_id, "completed")
    finally:
        await worker.stop()
        await db.close()

    assert processed == [job_id]
    assert completed["status"] == "completed"
    assert completed["error_message"] == "stale worker lock recovered"
