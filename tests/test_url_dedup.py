import pytest
from aily.queue.db import QueueDB


@pytest.fixture
async def queue_db(tmp_path):
    db = QueueDB(tmp_path / "aily_queue.db")
    await db.initialize()
    try:
        yield db
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_duplicate_url_returns_none(queue_db):
    url = "https://example.com/article"
    first = await queue_db.insert_raw_log(url)
    assert first is not None
    second = await queue_db.insert_raw_log(url)
    assert second is None


@pytest.mark.asyncio
async def test_different_urls_get_unique_hashes(queue_db):
    url1 = "https://example.com/a"
    url2 = "https://example.com/b"
    assert await queue_db.insert_raw_log(url1) is not None
    assert await queue_db.insert_raw_log(url2) is not None
