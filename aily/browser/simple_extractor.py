#!/usr/bin/env python3
"""
Simple content extraction using Playwright directly.
No agent, no LLM - just navigate and extract.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def extract_page_content(
    url: str,
    use_personal_profile: bool = True,
    timeout: int = 60,
    llm_config: dict[str, Any] | None = None,
) -> dict:
    """
    Extract content from a URL using Playwright directly.

    This bypasses the browser-use Agent and just:
    1. Navigates to the URL
    2. Waits for content to load
    3. Extracts text from the page
    """
    from playwright.async_api import async_playwright

    logger.info("Extracting content from %s", url)
    _ = llm_config  # Reserved for compatibility with older callers.

    async with async_playwright() as p:
        browser = None
        context = None
        try:
            if use_personal_profile:
                import platform

                system = platform.system()
                if system == "Darwin":
                    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                    user_data_dir = str(Path.home() / "Library/Application Support/Google/Chrome")
                elif system == "Windows":
                    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                    user_data_dir = str(Path.home() / "AppData/Local/Google/Chrome/User Data")
                else:
                    chrome_path = "/usr/bin/google-chrome"
                    user_data_dir = str(Path.home() / ".config/google-chrome")

                browser_kwargs: dict[str, Any] = {
                    "headless": False,
                    "args": ["--profile-directory=Default"],
                }
                if Path(chrome_path).exists():
                    browser_kwargs["executable_path"] = chrome_path

                context = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    **browser_kwargs,
                )
            else:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )

            page = await context.new_page()
            logger.info("Navigating to %s", url)
            await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            await asyncio.sleep(3)

            content_selectors = [
                '[role="log"]',
                '[class*="chat"]',
                '[class*="message"]',
                '[class*="conversation"]',
                '[class*="bubble"]',
                "main",
                "article",
                '[role="main"]',
                "body",
            ]

            extracted_text = None
            used_selector = None
            for selector in content_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.inner_text()
                        if text and len(text.strip()) > 100:
                            extracted_text = text.strip()
                            used_selector = selector
                            logger.info("Found content using selector: %s", selector)
                            break
                except Exception:
                    logger.debug("Selector extraction failed for %s", selector, exc_info=True)

            title = await page.title()
            return {
                "status": "ok",
                "text": extracted_text or f"No substantial content found. Page title: {title}",
                "title": title,
                "url": url,
                "selector": used_selector,
            }
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()


if __name__ == "__main__":
    result = asyncio.run(
        extract_page_content(
            "https://monica.im/home/chat/Monica/monica?convId=conv%3Ab743d1ff-7dc1-4c59-8f0d-43d054fc15a7",
            use_personal_profile=True,
        )
    )
    print(result)
