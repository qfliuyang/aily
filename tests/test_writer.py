import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import aiohttp

from aily.writer.obsidian import ObsidianWriter, ObsidianAPIError


@pytest.fixture
def writer():
    return ObsidianWriter("test-key", "/tmp/vault", port=27123)


def _mock_session(status: int, side_effect=None):
    mock_session_cls = MagicMock()
    mock_session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.raise_for_status = MagicMock()

    def make_put_cm(*args, **kwargs):
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    mock_session.put = MagicMock(side_effect=side_effect or make_put_cm)
    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_session_cls


@pytest.mark.asyncio
async def test_successful_write(writer: ObsidianWriter):
    with patch("aiohttp.ClientSession", _mock_session(200)):
        path = await writer.write_note("Test Note", "# Hello", "https://example.com")
        assert path == "Aily Drafts/Test Note.md"


@pytest.mark.asyncio
async def test_404_raises_actionable_error(writer: ObsidianWriter):
    with patch("aiohttp.ClientSession", _mock_session(404)):
        with pytest.raises(ObsidianAPIError) as exc_info:
            await writer.write_note("Test", "body", "https://example.com")
        assert "Obsidian Local REST API plugin is not running" in str(exc_info.value)


@pytest.mark.asyncio
async def test_connection_refused_retries_then_raises(writer: ObsidianWriter):
    refusal = aiohttp.ClientConnectionError("connection refused")
    mock_cls = _mock_session(200, side_effect=[refusal, refusal])
    with patch("aiohttp.ClientSession", mock_cls):
        with pytest.raises(ObsidianAPIError) as exc_info:
            await writer.write_note("Test", "body", "https://example.com")
        assert "Obsidian Local REST API plugin is not running" in str(exc_info.value)
        # Verify two calls (initial + one retry)
        mock_session = await mock_cls.return_value.__aenter__()
        assert mock_session.put.call_count == 2
