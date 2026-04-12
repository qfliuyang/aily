import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from aily.browser.fetcher import BrowserFetcher, FetchError
from aily.browser.manager import BrowserFetchError


@pytest.mark.asyncio
async def test_fetch_returns_text():
    fetcher = BrowserFetcher(profile_dir=Path("/tmp/profile"))
    with patch.object(fetcher._manager, "start", new_callable=AsyncMock) as mock_start:
        with patch.object(fetcher._manager, "fetch", new_callable=AsyncMock, return_value="hello world") as mock_fetch:
            text = await fetcher.fetch("https://example.com")
            assert text == "hello world"
            mock_start.assert_called_once()
            mock_fetch.assert_awaited_once_with("https://example.com", timeout=60)


@pytest.mark.asyncio
async def test_fetch_maps_browser_error_to_fetch_error():
    fetcher = BrowserFetcher()
    with patch.object(fetcher._manager, "start", new_callable=AsyncMock):
        with patch.object(fetcher._manager, "fetch", new_callable=AsyncMock, side_effect=BrowserFetchError("crashed")):
            with pytest.raises(FetchError, match="crashed"):
                await fetcher.fetch("https://example.com")


@pytest.mark.asyncio
async def test_fetch_maps_timeout_to_fetch_error():
    fetcher = BrowserFetcher()
    with patch.object(fetcher._manager, "start", new_callable=AsyncMock):
        with patch.object(fetcher._manager, "fetch", new_callable=AsyncMock, side_effect=TimeoutError("timed out")):
            with pytest.raises(FetchError, match="timed out"):
                await fetcher.fetch("https://example.com")
