"""
NO MOCK integration testing for Aily.

These tests hit REAL services:
- Real Feishu API (creates actual messages)
- Real Obsidian vault (writes actual files)
- Real browser fetching real websites
- Real LLM API calls
- Real SQLite databases

Tests are designed to EXPOSE problems, not hide them behind mocks.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio

# =============================================================================
# REAL SERVICE CONFIGURATION
# =============================================================================

# These MUST be set to run tests against real services
REQUIRED_ENV_VARS = [
    "FEISHU_APP_ID",
    "FEISHU_APP_SECRET",
    "OBSIDIAN_VAULT_PATH",
    "OBSIDIAN_REST_API_KEY",
    "LLM_API_KEY",
]

OPTIONAL_ENV_VARS = [
    "FEISHU_TEST_OPEN_ID",  # Target user for test messages
    "FEISHU_TEST_GROUP_CHAT_ID",  # Target group for tests
]


def check_real_services() -> dict[str, bool]:
    """Check which real services are configured."""
    return {
        "feishu": all(os.getenv(v) for v in ["FEISHU_APP_ID", "FEISHU_APP_SECRET"]),
        "obsidian": all(os.getenv(v) for v in ["OBSIDIAN_VAULT_PATH", "OBSIDIAN_REST_API_KEY"]),
        "llm": bool(os.getenv("LLM_API_KEY")),
        "browser": bool(os.getenv("BROWSER_SERVICE_URL")),
        "playwright": True,  # Local Playwright browser tests manage their own skips.
    }


@pytest.fixture(scope="session")
def service_availability() -> dict[str, bool]:
    """Report which real services are available."""
    availability = check_real_services()
    missing = [k for k, v in availability.items() if not v]
    if missing:
        print(f"\n⚠️  Missing real services: {', '.join(missing)}")
        print("Tests for these services will be SKIPPED")
        print("Set environment variables to enable full testing\n")
    return availability


# =============================================================================
# REAL FEISHU CLIENT
# =============================================================================

class RealFeishuClient:
    """
    Client that hits the REAL Feishu API.

    This creates actual messages in actual chats.
    Tests will pollute your Feishu history - that's the point.
    If something breaks, you'll see it in Feishu.
    """

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self) -> None:
        self.app_id = os.environ["FEISHU_APP_ID"]
        self.app_secret = os.environ["FEISHU_APP_SECRET"]
        self._token: str | None = None
        self._token_expires: datetime | None = None
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=30.0)

    async def _get_token(self) -> str:
        """Get tenant access token (real API call)."""
        if self._token and self._token_expires and datetime.now() < self._token_expires:
            return self._token

        resp = await self.client.post(
            "/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret}
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Feishu auth failed: {data}")

        self._token = data["tenant_access_token"]
        # Token expires in 7200 seconds, refresh after 7000
        self._token_expires = datetime.now() + __import__("datetime").timedelta(seconds=7000)
        return self._token

    async def send_message(self, open_id: str, text: str) -> dict[str, Any]:
        """Send a REAL message to a REAL user."""
        token = await self._get_token()

        resp = await self.client.post(
            "/im/v1/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"receive_id_type": "open_id"},
            json={
                "receive_id": open_id,
                "msg_type": "text",
                "content": {"text": f"[TEST] {text}\n\n{datetime.now(timezone.utc).isoformat()}"}
            }
        )
        resp.raise_for_status()
        return resp.json()

    async def send_to_group(self, chat_id: str, text: str) -> dict[str, Any]:
        """Send message to a REAL group chat."""
        token = await self._get_token()

        resp = await self.client.post(
            "/im/v1/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": chat_id,
                "msg_type": "text",
                "content": {"text": f"[TEST] {text}\n\n{datetime.now(timezone.utc).isoformat()}"}
            }
        )
        resp.raise_for_status()
        return resp.json()

    async def get_chat_history(self, chat_id: str, limit: int = 20) -> list[dict]:
        """Get REAL message history from a chat."""
        token = await self._get_token()

        resp = await self.client.get(
            f"/im/v1/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"container_id_type": "chat", "container_id": chat_id, "page_size": limit}
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("items", [])

    async def close(self) -> None:
        await self.client.aclose()


@pytest_asyncio.fixture
async def feishu_client(service_availability: dict) -> AsyncGenerator[RealFeishuClient | None, None]:
    """
    REAL Feishu client that sends actual messages.

    Skips if credentials not configured.
    """
    if not service_availability["feishu"]:
        pytest.skip("Feishu credentials not configured")

    client = RealFeishuClient()
    try:
        yield client
    finally:
        await client.close()


# =============================================================================
# REAL OBSIDIAN CLIENT
# =============================================================================

class RealObsidianClient:
    """
    Client that writes to the REAL Obsidian vault.

    Tests create actual files in your actual vault.
    They go in a `Aily Tests/` folder that you can delete later.
    """

    def __init__(self) -> None:
        self.vault_path = Path(os.environ["OBSIDIAN_VAULT_PATH"])
        self.api_key = os.environ["OBSIDIAN_REST_API_KEY"]
        self.port = int(os.getenv("OBSIDIAN_REST_API_PORT", "27123"))
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.test_folder = "Aily Tests"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0
        )

    async def write_note(self, filename: str, content: str) -> dict[str, Any]:
        """Write a REAL note to your REAL vault."""
        path = f"{self.test_folder}/{filename}"

        resp = await self.client.put(
            f"/vault/{path}",
            content=content.encode('utf-8'),
            headers={"Content-Type": "text/markdown"}
        )
        resp.raise_for_status()
        return {"path": path, "status": resp.status_code}

    async def read_note(self, filename: str) -> str:
        """Read a note from your vault."""
        path = f"{self.test_folder}/{filename}"
        resp = await self.client.get(f"/vault/{path}")
        resp.raise_for_status()
        return resp.text

    async def list_test_notes(self) -> list[str]:
        """List all notes in the test folder."""
        resp = await self.client.get(f"/vault/{self.test_folder}")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        return [f["path"] for f in data.get("files", [])]

    async def delete_note(self, filename: str) -> None:
        """Delete a test note."""
        path = f"{self.test_folder}/{filename}"
        await self.client.delete(f"/vault/{path}")

    async def cleanup_all_tests(self) -> int:
        """
        Delete ALL notes in the test folder.
        Call this after tests to clean up.
        """
        notes = await self.list_test_notes()
        count = 0
        for note in notes:
            await self.client.delete(f"/vault/{note}")
            count += 1
        return count

    def local_path(self, filename: str) -> Path:
        """Get the actual filesystem path to a test note."""
        return self.vault_path / self.test_folder / filename

    async def close(self) -> None:
        await self.client.aclose()


@pytest_asyncio.fixture
async def obsidian_client(service_availability: dict) -> AsyncGenerator[RealObsidianClient | None, None]:
    """
    REAL Obsidian client that writes actual files.

    Skips if Obsidian REST API not configured.
    """
    if not service_availability["obsidian"]:
        pytest.skip("Obsidian credentials not configured")

    client = RealObsidianClient()
    try:
        yield client
    finally:
        await client.close()


@pytest_asyncio.fixture
async def browser_client(service_availability: dict) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    HTTP client for the optional browser service.

    The service-backed tests require the integration docker stack or another
    compatible browser service. Local Playwright tests use browser_page instead.
    """
    base_url = os.getenv("BROWSER_SERVICE_URL")
    if not base_url:
        pytest.skip("BROWSER_SERVICE_URL not configured")

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        try:
            health = await client.get("/health")
        except httpx.HTTPError as exc:
            pytest.skip(f"Browser service unavailable at {base_url}: {exc}")
        if health.status_code >= 500:
            pytest.skip(f"Browser service unhealthy at {base_url}: HTTP {health.status_code}")
        yield client


@pytest.fixture(scope="session", autouse=True)
def cleanup_obsidian_tests(service_availability: dict) -> Generator[None, None, None]:
    """
    Cleanup hook: Remove all test notes after test session.

    This is destructive - it deletes files from your vault!
    """
    yield  # Run tests

    # Cleanup after tests
    if service_availability["obsidian"]:
        print("\n🧹 Cleaning up Obsidian test files...")
        import asyncio
        async def do_cleanup():
            client = RealObsidianClient()
            try:
                count = await client.cleanup_all_tests()
                print(f"   Deleted {count} test files from vault")
            finally:
                await client.close()

        try:
            asyncio.run(do_cleanup())
        except Exception as e:
            print(f"   ⚠️  Cleanup failed: {e}")


# =============================================================================
# REAL BROWSER
# =============================================================================

try:
    from playwright.async_api import async_playwright, Page
    from playwright_stealth import Stealth
    PLAYWRIGHT_IMPORT_ERROR: Exception | None = None
except ModuleNotFoundError as exc:
    async_playwright = None
    Page = object
    Stealth = None
    PLAYWRIGHT_IMPORT_ERROR = exc


@pytest_asyncio.fixture
async def browser_page() -> AsyncGenerator[Page, None]:
    """
    REAL browser page using actual Playwright with stealth mode.

    Fetches real websites over real network with anti-bot evasion.
    """
    if PLAYWRIGHT_IMPORT_ERROR is not None or async_playwright is None or Stealth is None:
        pytest.skip(f"Playwright integration dependencies not installed: {PLAYWRIGHT_IMPORT_ERROR}")

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.launch(headless=True)
    except Exception as exc:
        await playwright.stop()
        pytest.skip(f"Playwright browser not available: {exc}")
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()

    # Apply stealth to evade bot detection
    await Stealth().apply_stealth_async(page)

    try:
        yield page
    finally:
        await context.close()
        await browser.close()
        await playwright.stop()


# =============================================================================
# REAL DATABASE
# =============================================================================

@pytest.fixture
def real_database() -> Generator[Path, None, None]:
    """
    REAL SQLite database file on disk.

    Tests use actual file I/O, not in-memory.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        yield db_path
    finally:
        db_path.unlink(missing_ok=True)


@pytest.fixture
def database_connection(real_database: Path) -> Generator[sqlite3.Connection, None, None]:
    """Actual SQLite connection with real queries."""
    conn = sqlite3.connect(real_database)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# =============================================================================
# REAL AILY APPLICATION
# =============================================================================

@pytest_asyncio.fixture
async def aily_app(service_availability: dict) -> AsyncGenerator[Any, None]:
    """
    Start the REAL Aily application with REAL configuration.

    This is the actual FastAPI app with actual dependencies.
    """
    # Only run if we have enough services to start Aily
    if not service_availability["obsidian"]:
        pytest.skip("Cannot start Aily without Obsidian configuration")

    from aily.main import app
    from aily.config import SETTINGS

    # Use temp database paths for isolation
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"
        test_graph_path = Path(tmpdir) / "graph.db"

        # Override settings for test
        original_queue_db = SETTINGS.queue_db_path
        original_graph_db = SETTINGS.graph_db_path

        SETTINGS.queue_db_path = str(test_db_path)
        SETTINGS.graph_db_path = str(test_graph_path)

        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            try:
                yield client
            finally:
                # Restore settings
                SETTINGS.queue_db_path = original_queue_db
                SETTINGS.graph_db_path = original_graph_db


# =============================================================================
# TEST ID HELPERS
# =============================================================================

def generate_test_id(prefix: str = "test") -> str:
    """Generate a unique test ID for traceability."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    random_suffix = secrets.token_hex(4)
    return f"{prefix}-{timestamp}-{random_suffix}"


@pytest.fixture
def test_id() -> str:
    """Unique ID for this test run."""
    return generate_test_id()


# =============================================================================
# EXPOSURE HELPERS
# =============================================================================

class ProblemExposure:
    """
    Helper to expose and report problems during testing.

    Unlike normal testing where we expect success,
    this framework actively hunts for failures.
    """

    def __init__(self) -> None:
        self.problems: list[dict] = []

    def expose(self, category: str, description: str, details: dict | None = None) -> None:
        """Record a problem that was exposed."""
        problem = {
            "category": category,
            "description": description,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.problems.append(problem)

        # Print immediately so we see it even if test passes
        print(f"\n🔴 EXPOSED: {category}")
        print(f"   {description}")
        if details:
            for key, value in details.items():
                print(f"   {key}: {value}")

    def report(self) -> str:
        """Generate a report of all exposed problems."""
        if not self.problems:
            return "No problems exposed ✓"

        lines = [f"\n{'='*60}", "PROBLEM EXPOSURE REPORT", f"{'='*60}"]
        for i, p in enumerate(self.problems, 1):
            lines.append(f"\n{i}. [{p['category']}] {p['description']}")
        lines.append(f"\nTotal: {len(self.problems)} problems exposed")
        lines.append(f"{'='*60}")
        return "\n".join(lines)


@pytest.fixture
def exposure() -> ProblemExposure:
    """Problem exposure helper for tests."""
    return ProblemExposure()


# =============================================================================
# VISUAL TESTING (Screenshots & Video)
# =============================================================================

@pytest_asyncio.fixture
async def visual_browser_page(test_id: str) -> AsyncGenerator[tuple[Page, Path], None]:
    """
    Browser with video recording and screenshot capabilities.

    Yields (page, artifacts_dir) for visual test verification.
    Uses stealth mode to evade bot detection.
    """
    if PLAYWRIGHT_IMPORT_ERROR is not None or async_playwright is None or Stealth is None:
        pytest.skip(f"Playwright integration dependencies not installed: {PLAYWRIGHT_IMPORT_ERROR}")

    # Create artifacts directory for this test
    artifacts_dir = Path("test-artifacts") / test_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.launch(headless=True)
    except Exception as exc:
        await playwright.stop()
        pytest.skip(f"Playwright browser not available: {exc}")

    # Enable video recording with realistic user agent
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        record_video_dir=str(artifacts_dir),
        record_video_size={"width": 1920, "height": 1080},
    )

    page = await context.new_page()

    # Apply stealth to evade bot detection
    await Stealth().apply_stealth_async(page)

    try:
        yield page, artifacts_dir
    finally:
        # Close context to save video
        await context.close()
        await browser.close()
        await playwright.stop()


class VisualTestHelper:
    """Helper for capturing visual artifacts during tests."""

    def __init__(self, page: Page, artifacts_dir: Path, exposure: ProblemExposure):
        self.page = page
        self.artifacts_dir = artifacts_dir
        self.exposure = exposure
        self.screenshots: list[Path] = []

    async def screenshot(self, name: str, full_page: bool = True) -> Path:
        """Take a screenshot and save to artifacts directory."""
        screenshot_path = self.artifacts_dir / f"{name}.png"
        await self.page.screenshot(path=str(screenshot_path), full_page=full_page)
        self.screenshots.append(screenshot_path)
        self.exposure.expose("SCREENSHOT_CAPTURED", f"Screenshot: {name}", {
            "path": str(screenshot_path),
            "name": name,
        })
        return screenshot_path

    async def compare_visual_state(self, name: str, expected_text: str) -> bool:
        """Screenshot and check if expected text is visible."""
        await self.screenshot(name)
        content = await self.page.content()
        found = expected_text in content
        if not found:
            self.exposure.expose("VISUAL_MISMATCH", f"Expected text not found: {expected_text}", {
                "screenshot": name,
                "page_title": await self.page.title(),
            })
        return found

    def get_artifacts_report(self) -> dict:
        """Get report of all captured artifacts."""
        video_files = list(self.artifacts_dir.glob("*.webm"))
        return {
            "artifacts_dir": str(self.artifacts_dir),
            "screenshots": [str(s) for s in self.screenshots],
            "videos": [str(v) for v in video_files],
            "total_artifacts": len(self.screenshots) + len(video_files),
        }


@pytest.fixture
def visual_helper() -> type[VisualTestHelper]:
    """Visual test helper class."""
    return VisualTestHelper
