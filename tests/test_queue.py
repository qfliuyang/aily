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


@pytest.mark.asyncio
async def test_complete_job(queue_db: QueueDB):
    job_id = await queue_db.enqueue("url_fetch", {"url": "https://example.com"})
    await queue_db.complete_job(job_id, success=True)
    job = await queue_db.get_job(job_id)
    assert job["status"] == "completed"
    assert job["error_message"] is None


@pytest.mark.asyncio
async def test_get_job(queue_db: QueueDB):
    job_id = await queue_db.enqueue("url_fetch", {"url": "https://example.com"})
    job = await queue_db.get_job(job_id)
    assert job is not None
    assert job["id"] == job_id
    assert job["type"] == "url_fetch"


@pytest.mark.asyncio
async def test_complete_job_with_error(queue_db: QueueDB):
    job_id = await queue_db.enqueue("url_fetch", {"url": "https://example.com"})
    await queue_db.complete_job(job_id, success=False, error_message="boom")
    job = await queue_db.get_job(job_id)
    assert job["status"] == "failed"
    assert job["error_message"] == "boom"


@pytest.mark.asyncio
async def test_get_raw_logs_within_hours(queue_db: QueueDB):
    log_id = await queue_db.insert_raw_log("https://example.com", "test")
    assert log_id is not None
    logs = await queue_db.get_raw_logs_within_hours(24)
    assert len(logs) == 1
    assert logs[0]["id"] == log_id
    assert logs[0]["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_get_urls_for_raw_logs(queue_db: QueueDB):
    log_id1 = await queue_db.insert_raw_log("https://first.com", "test")
    log_id2 = await queue_db.insert_raw_log("https://second.com", "test")
    urls = await queue_db.get_urls_for_raw_logs([log_id1, log_id2])
    assert urls == {
        log_id1: "https://first.com",
        log_id2: "https://second.com",
    }


@pytest.mark.asyncio
async def test_get_urls_for_raw_logs_empty(queue_db: QueueDB):
    urls = await queue_db.get_urls_for_raw_logs([])
    assert urls == {}
