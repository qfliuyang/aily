import json
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from aily.queue.db import QueueDB
from aily.queue.worker import JobWorker
from aily.main import process_job


@pytest.fixture
async def e2e_db(tmp_path: Path):
    db = QueueDB(tmp_path / "e2e.db")
    await db.initialize()
    return db


@pytest.mark.asyncio
async def test_full_pipeline_success(e2e_db: QueueDB):
    job_id = await e2e_db.enqueue("url_fetch", {"url": "https://kimi.moonshot.cn/share/abc", "open_id": "u1"})

    with patch("aily.main.fetcher.fetch", new_callable=AsyncMock) as mock_fetch, \
         patch("aily.main.writer.write_note", new_callable=AsyncMock) as mock_write, \
         patch("aily.main.pusher.send_message", new_callable=AsyncMock) as mock_push:
        mock_fetch.return_value = "<html><title>Report</title><body>Content</body></html>"
        mock_write.return_value = "Aily Drafts/Report.md"
        mock_push.return_value = True

        job = await e2e_db.dequeue()
        assert job is not None
        await process_job(job)
        await e2e_db.complete_job(job["id"], success=True)

        # Verify job completed
        job_state = await e2e_db.get_job(job_id)
        assert job_state is not None
        assert job_state["status"] == "completed"

    mock_fetch.assert_awaited_once_with("https://kimi.moonshot.cn/share/abc")
    mock_write.assert_awaited_once()
    mock_push.assert_awaited_once_with("u1", "Saved to Obsidian: Aily Drafts/Report.md")
