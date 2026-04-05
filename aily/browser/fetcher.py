from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

_BROWSER_SEMAPHORE = asyncio.Semaphore(1)


class FetchError(Exception):
    pass


class BrowserFetcher:
    def __init__(self, profile_dir: Path | None = None) -> None:
        self.profile_dir = profile_dir or (Path.home() / ".aily" / "browser_profile")
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    async def fetch(self, url: str, timeout: int = 60) -> str:
        async with _BROWSER_SEMAPHORE:
            try:
                return await asyncio.wait_for(
                    self._fetch_text(url), timeout=timeout
                )
            except asyncio.TimeoutError as exc:
                raise FetchError(f"Timeout fetching {url}") from exc
            except Exception as exc:
                raise FetchError(str(exc)) from exc

    async def _fetch_text(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=True,
            )
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="networkidle")
                text = await page.inner_text("body")
                return text or ""
            finally:
                await browser.close()
