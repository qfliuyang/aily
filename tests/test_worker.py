import pytest
from unittest.mock import AsyncMock, patch, MagicMock

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
