import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from aily.browser.fetcher import BrowserFetcher, FetchError


def _build_mock_playwright(inner_text: str):
    """Return a mock for async_playwright that yields a page with given inner_text."""
    async def _mock_playwright():
        pass

    mock_pw = AsyncMock()
    mock_p = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_page.inner_text = AsyncMock(return_value=inner_text)
    mock_page.goto = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()
    mock_p.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)
    mock_pw.__aenter__ = AsyncMock(return_value=mock_p)
    mock_pw.__aexit__ = AsyncMock(return_value=False)
    return mock_pw


@pytest.mark.asyncio
async def test_fetch_local_html(tmp_path: Path):
    html = "<html><head><title>Local Page</title></head><body><p>Hello 世界</p></body></html>"
    html_path = tmp_path / "test.html"
    html_path.write_text(html, encoding="utf-8")

    fetcher = BrowserFetcher(profile_dir=tmp_path / "profile")
    mock_pw = _build_mock_playwright("Hello 世界")
    with patch("aily.browser.fetcher.async_playwright", return_value=mock_pw):
        text = await fetcher.fetch(f"file://{html_path}")
        assert "Hello 世界" in text


@pytest.mark.asyncio
async def test_timeout_raises_fetch_error():
    fetcher = BrowserFetcher()
    mock_pw = AsyncMock()
    mock_pw.__aenter__ = AsyncMock(side_effect=Exception("browser crashed"))
    mock_pw.__aexit__ = AsyncMock(return_value=False)
    with patch("aily.browser.fetcher.async_playwright", return_value=mock_pw):
        with pytest.raises(FetchError):
            await fetcher.fetch("https://example.com", timeout=1)


@pytest.mark.asyncio
async def test_empty_content_returns_empty_string():
    fetcher = BrowserFetcher()
    mock_pw = _build_mock_playwright("")
    with patch("aily.browser.fetcher.async_playwright", return_value=mock_pw):
        text = await fetcher.fetch("https://example.com")
        assert text == ""
