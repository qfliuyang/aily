import pytest
from pathlib import Path

from aily.queue.db import QueueDB


@pytest.fixture
async def queue_db(tmp_path: Path):
    db = QueueDB(tmp_path / "test.db")
    await db.initialize()
    return db


@pytest.mark.asyncio
async def test_enqueue(queue_db: QueueDB):
    job_id = await queue_db.enqueue("url_fetch", {"url": "https://example.com"})
    assert job_id
    job = await queue_db.dequeue()
    assert job is not None
    assert job["type"] == "url_fetch"
    assert job["payload"]["url"] == "https://example.com"
    assert job["status"] == "running"  # dequeued marks running


@pytest.mark.asyncio
async def test_dequeue_oldest_pending(queue_db: QueueDB):
    id1 = await queue_db.enqueue("url_fetch", {"url": "https://first.com"})
    id2 = await queue_db.enqueue("url_fetch", {"url": "https://second.com"})
    job = await queue_db.dequeue()
    assert job is not None
    assert job["id"] == id1


@pytest.mark.asyncio
async def test_retry_and_max_fail(queue_db: QueueDB):
    job_id = await queue_db.enqueue("url_fetch", {"url": "https://example.com"})
    job = await queue_db.dequeue()
    assert job is not None

    # 1st retry
    assert await queue_db.retry_job(job_id) is True
    job = await queue_db.dequeue()
    assert job is not None
    assert job["retry_count"] == 1

    # 2nd retry
    assert await queue_db.retry_job(job_id) is True
    job = await queue_db.dequeue()
    assert job["retry_count"] == 2

    # 3rd retry -> fail
    assert await queue_db.retry_job(job_id) is False
    # status should be failed
    next_job = await queue_db.dequeue()
    assert next_job is None
