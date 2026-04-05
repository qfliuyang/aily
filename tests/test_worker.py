import pytest
from unittest.mock import AsyncMock

from aily.queue.db import QueueDB
from aily.queue.worker import JobWorker


@pytest.fixture
async def worker_db(tmp_path):
    db = QueueDB(tmp_path / "worker.db")
    await db.initialize()
    return db


@pytest.mark.asyncio
async def test_worker_processes_job(worker_db):
    processor = AsyncMock()
    worker = JobWorker(worker_db, processor, poll_interval=0.01)
    await worker.start()

    job_id = await worker_db.enqueue("url_fetch", {"url": "https://example.com"})

    # Wait for the processor to be called
    for _ in range(50):
        if processor.await_count >= 1:
            break
        import asyncio
        await asyncio.sleep(0.01)

    await worker.stop()
    assert processor.await_count >= 1


@pytest.mark.asyncio
async def test_worker_stop_cancels_loop(worker_db):
    worker = JobWorker(worker_db, AsyncMock(), poll_interval=0.1)
    await worker.start()
    assert worker._task is not None
    await worker.stop()
    assert worker._task.done()


@pytest.mark.asyncio
async def test_worker_marks_job_complete(worker_db):
    processor = AsyncMock()
    worker = JobWorker(worker_db, processor, poll_interval=0.01)
    await worker.start()

    job_id = await worker_db.enqueue("url_fetch", {"url": "https://example.com"})

    for _ in range(50):
        job = await worker_db.get_job(job_id)
        if job and job["status"] == "completed":
            break
        import asyncio
        await asyncio.sleep(0.01)

    await worker.stop()
    job = await worker_db.get_job(job_id)
    assert job["status"] == "completed"
