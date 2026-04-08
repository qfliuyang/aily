"""
Browser Service

Real Playwright browser automation as a service.
Provides HTTP endpoints for fetching and extracting content from web pages.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global browser instance
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None


class FetchRequest(BaseModel):
    """Request to fetch a URL."""
    url: str
    wait_for: Optional[str] = None  # CSS selector to wait for
    timeout: int = 30000  # ms
    javascript: bool = True


class FetchResponse(BaseModel):
    """Response from fetch operation."""
    url: str
    title: str
    text: str
    html: str
    status: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage browser lifecycle."""
    global _browser, _context

    logger.info("Starting browser service...")
    playwright = await async_playwright().start()
    _browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ]
    )
    _context = await _browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    logger.info("Browser service ready")

    yield

    logger.info("Shutting down browser service...")
    if _context:
        await _context.close()
    if _browser:
        await _browser.close()
    await playwright.stop()


app = FastAPI(title="Browser Service", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy" if _browser else "initializing",
        "service": "browser-service",
        "browser_connected": _browser is not None and _browser.is_connected(),
    }


@app.post("/fetch", response_model=FetchResponse)
async def fetch_page(request: FetchRequest) -> FetchResponse:
    """
    Fetch a web page and extract content.

    This is the real deal - actual Playwright browser fetching pages.
    """
    if not _context:
        raise HTTPException(status_code=503, detail="Browser not ready")

    page: Optional[Page] = None
    try:
        page = await _context.new_page()

        logger.info(f"Fetching: {request.url}")

        # Navigate to page
        response = await page.goto(
            request.url,
            wait_until="networkidle",
            timeout=request.timeout,
        )

        if not response:
            raise HTTPException(status_code=500, detail="No response from page")

        status = response.status

        # Wait for specific element if requested
        if request.wait_for:
            try:
                await page.wait_for_selector(
                    request.wait_for,
                    timeout=10000,
                )
            except Exception as e:
                logger.warning(f"Wait for selector failed: {e}")

        # Extract content
        title = await page.title()
        html = await page.content()

        # Get text content (visible text only)
        text = await page.evaluate("""
            () => {
                // Remove script and style elements
                const scripts = document.querySelectorAll('script, style, nav, footer, header');
                scripts.forEach(el => el.remove());

                // Get main content if available, otherwise body
                const main = document.querySelector('main, article, [role="main"], .content, #content');
                if (main) {
                    return main.innerText;
                }
                return document.body.innerText;
            }
        """)

        logger.info(f"Fetched {request.url}: {status}, title='{title[:50]}...'")

        return FetchResponse(
            url=request.url,
            title=title,
            text=text[:50000],  # Limit text size
            html=html[:100000],  # Limit HTML size
            status=status,
        )

    except Exception as e:
        logger.error(f"Failed to fetch {request.url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if page:
            await page.close()


@app.post("/fetch/text")
async def fetch_text_only(request: FetchRequest) -> dict:
    """Fetch only the text content (lighter response)."""
    result = await fetch_page(request)
    return {
        "url": result.url,
        "title": result.title,
        "text": result.text,
        "status": result.status,
    }


@app.get("/status")
async def get_status() -> dict:
    """Get detailed browser status."""
    if not _browser:
        return {"status": "not_initialized"}

    contexts = _browser.contexts
    pages = sum(len(ctx.pages) for ctx in contexts)

    return {
        "status": "ready" if _browser.is_connected() else "disconnected",
        "connected": _browser.is_connected(),
        "contexts": len(contexts),
        "pages": pages,
    }
