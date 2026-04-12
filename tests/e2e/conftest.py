"""E2E test configuration and fixtures.

Design principles:
1. ISOLATION: Each test gets its own temp DBs and directories
2. REAL COMPONENTS: No mocks - use actual GraphDB, QueueDB, etc.
3. VERIFIABILITY: Can assert on file contents, DB state, etc.
4. CLEANUP: Automatic cleanup after tests (unless debugging)
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

# =============================================================================
# TEST ISOLATION HELPERS
# =============================================================================

class E2EContext:
    """Context manager for E2E test isolation.

    Provides:
    - Temp directory for all test artifacts
    - Isolated SQLite databases
    - Test Obsidian vault directory
    - Cleanup on exit
    """

    def __init__(self, test_name: str) -> None:
        self.test_name = test_name
        self.temp_dir: Path | None = None
        self.queue_db_path: Path | None = None
        self.graph_db_path: Path | None = None
        self.obsidian_vault_path: Path | None = None

    async def __aenter__(self) -> "E2EContext":
        """Set up isolated test environment."""
        # Create temp directory with test name for debugging
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"aily_e2e_{self.test_name}_{timestamp}_"))

        # Set up database paths
        self.queue_db_path = self.temp_dir / "queue.db"
        self.graph_db_path = self.temp_dir / "graph.db"

        # Set up Obsidian vault simulation
        self.obsidian_vault_path = self.temp_dir / "vault"
        self.obsidian_vault_path.mkdir()

        # Create Aily subdirectories
        (self.obsidian_vault_path / "Aily" / "Ideas").mkdir(parents=True)
        (self.obsidian_vault_path / "Aily" / "Proposals" / "Innovation").mkdir(parents=True)
        (self.obsidian_vault_path / "Aily" / "Proposals" / "Business").mkdir(parents=True)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up test environment."""
        # Keep temp dir on failure for debugging (if env var set)
        keep_on_failure = os.getenv("E2E_KEEP_ON_FAILURE", "false").lower() == "true"

        if exc_type is not None and keep_on_failure:
            print(f"\n⚠️  Test failed. Keeping artifacts at: {self.temp_dir}")
            return

        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def get_obsidian_note(self, path: str) -> Path:
        """Get path to a note in the test vault."""
        return self.obsidian_vault_path / path

    def list_vault_files(self) -> list[str]:
        """List all files in the test vault."""
        files = []
        for f in self.obsidian_vault_path.rglob("*.md"):
            files.append(str(f.relative_to(self.obsidian_vault_path)))
        return sorted(files)


@pytest_asyncio.fixture
async def e2e_context(request) -> AsyncGenerator[E2EContext, None]:
    """Provide isolated E2E test context."""
    test_name = request.node.name.replace("test_", "")
    async with E2EContext(test_name) as ctx:
        yield ctx


# =============================================================================
# REAL COMPONENT FIXTURES
# =============================================================================

@pytest_asyncio.fixture
async def graph_db(e2e_context: E2EContext) -> AsyncGenerator["GraphDB", None]:
    """Real GraphDB with isolated test database."""
    from aily.graph.db import GraphDB

    db = GraphDB(e2e_context.graph_db_path)
    await db.initialize()

    try:
        yield db
    finally:
        await db.close()


@pytest_asyncio.fixture
async def queue_db(e2e_context: E2EContext) -> AsyncGenerator["QueueDB", None]:
    """Real QueueDB with isolated test database."""
    from aily.queue.db import QueueDB

    db = QueueDB(e2e_context.queue_db_path)
    await db.initialize()

    try:
        yield db
    finally:
        await db.close()


@pytest.fixture
def llm_client() -> MagicMock | "LLMClient":
    """LLM client - real if configured, mock if not.

    For E2E tests, we prefer real LLM calls but allow mock fallback
    to ensure tests can run in CI without API keys.
    """
    from aily.llm.client import LLMClient
    from aily.config import SETTINGS

    # Check if real LLM is configured
    if SETTINGS.llm_api_key and SETTINGS.llm_api_key != "test-key":
        return LLMClient(
            base_url=SETTINGS.llm_base_url,
            api_key=SETTINGS.llm_api_key,
            model=SETTINGS.llm_model,
        )

    # Return mock for CI/testing without API keys
    # But make it obvious it's a mock (fail on unexpected calls)
    mock = MagicMock(spec=LLMClient)
    mock.complete = MagicMock(side_effect=RuntimeError(
        "Real LLM not configured. Set LLM_API_KEY for E2E tests."
    ))
    return mock


@pytest_asyncio.fixture
async def obsidian_writer(e2e_context: E2EContext) -> "ObsidianWriter":
    """ObsidianWriter that writes to test vault directory.

    Uses direct file writing (no REST API) for test reliability.
    """
    from aily.writer.obsidian import ObsidianWriter

    class TestObsidianWriter(ObsidianWriter):
        """ObsidianWriter that writes directly to filesystem."""

        def __init__(self, vault_path: Path):
            self.vault_path = vault_path
            # Don't call super().__init__ to avoid REST API setup

        async def write_note(
            self,
            title: str,
            markdown: str,
            source_url: str | None = None,
        ) -> str:
            """Write note directly to filesystem."""
            # Sanitize title for filename
            safe_title = "".join(c for c in title if c.isalnum() or c in " -_").rstrip()
            filename = f"{safe_title}.md"
            filepath = self.vault_path / filename

            # Write content
            filepath.write_text(markdown, encoding="utf-8")

            return str(filepath.relative_to(self.vault_path))

    return TestObsidianWriter(e2e_context.obsidian_vault_path)


@pytest.fixture
def feishu_pusher() -> MagicMock:
    """Mock Feishu pusher that records messages for verification.

    For E2E tests, we don't send real messages but we verify
    the *intent* to send correct messages.
    """
    mock = MagicMock()
    mock.sent_messages: list[dict] = []

    async def mock_send_message(open_id: str, text: str) -> None:
        mock.sent_messages.append({
            "open_id": open_id,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    mock.send_message = mock_send_message
    return mock


# =============================================================================
# THREE-MIND SYSTEM FIXTURES
# =============================================================================

@pytest_asyncio.fixture
async def dikiwi_mind(
    llm_client,
    graph_db: "GraphDB",
) -> "DikiwiMind":
    """Real DikiwiMind with test databases."""
    from aily.sessions.dikiwi_mind import DikiwiMind

    return DikiwiMind(
        llm_client=llm_client,
        graph_db=graph_db,
        enabled=True,
    )


@pytest_asyncio.fixture
async def entrepreneur_scheduler(
    llm_client,
    graph_db: "GraphDB",
    obsidian_writer,
    feishu_pusher,
) -> "EntrepreneurScheduler":
    """Real EntrepreneurScheduler (not started)."""
    from aily.sessions.entrepreneur_scheduler import EntrepreneurScheduler

    return EntrepreneurScheduler(
        llm_client=llm_client,
        graph_db=graph_db,
        obsidian_writer=obsidian_writer,
        feishu_pusher=feishu_pusher,
        enabled=True,
    )


# =============================================================================
# VERIFICATION HELPERS
# =============================================================================

class VaultVerifier:
    """Helper to verify Obsidian vault state."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = vault_path

    def assert_note_exists(self, path: str) -> Path:
        """Assert that a note exists and return its path."""
        note_path = self.vault_path / path
        assert note_path.exists(), f"Note not found: {path}"
        return note_path

    def assert_note_contains(self, path: str, text: str) -> None:
        """Assert that a note contains specific text."""
        note_path = self.assert_note_exists(path)
        content = note_path.read_text(encoding="utf-8")
        assert text in content, f"Note {path} does not contain: {text}"

    def assert_directory_count(self, path: str, expected: int) -> None:
        """Assert directory has expected number of files."""
        dir_path = self.vault_path / path
        if not dir_path.exists():
            assert expected == 0, f"Directory {path} does not exist"
            return
        files = list(dir_path.glob("*.md"))
        assert len(files) == expected, f"Expected {expected} files in {path}, found {len(files)}"


class DatabaseVerifier:
    """Helper to verify database state."""

    def __init__(self, graph_db: "GraphDB", queue_db: "QueueDB") -> None:
        self.graph_db = graph_db
        self.queue_db = queue_db

    async def assert_node_count(self, expected: int) -> None:
        """Assert GraphDB has expected number of nodes."""
        # Use direct query since count method may not exist
        rows = await self.graph_db.execute_query("SELECT COUNT(*) as count FROM nodes")
        count = rows[0]["count"] if rows else 0
        assert count == expected, f"Expected {expected} nodes, found {count}"

    async def assert_job_count(self, status: str | None = None) -> int:
        """Get job count, optionally filtered by status."""
        if status:
            rows = await self.queue_db.execute(
                "SELECT COUNT(*) as count FROM jobs WHERE status = ?",
                (status,)
            )
        else:
            rows = await self.queue_db.execute("SELECT COUNT(*) as count FROM jobs")
        return rows[0]["count"] if rows else 0


@pytest.fixture
def vault_verifier(e2e_context: E2EContext) -> VaultVerifier:
    """Provide vault verification helper."""
    return VaultVerifier(e2e_context.obsidian_vault_path)


@pytest.fixture
def db_verifier(graph_db: "GraphDB", queue_db: "QueueDB") -> DatabaseVerifier:
    """Provide database verification helper."""
    return DatabaseVerifier(graph_db, queue_db)


# =============================================================================
# TEST DATA FACTORIES
# =============================================================================

class TestDrop:
    """Simple drop object for testing (mimics RainDrop dataclass)."""

    def __init__(
        self,
        id: str,
        type: str,
        content: str,
        source: str,
        creator_id: str,
        created_at: datetime,
    ):
        self.id = id
        self.type = type
        self.content = content
        self.source = source
        self.creator_id = creator_id
        self.created_at = created_at


class TestDataFactory:
    """Factory for creating test data."""

    @staticmethod
    def url_drop(url: str = "https://example.com/article", content: str | None = None) -> TestDrop:
        """Create a URL RainDrop."""
        return TestDrop(
            id=f"test_drop_{datetime.now(timezone.utc).timestamp()}",
            type="url",
            content=content or f"Check out this article: {url}",
            source=url,
            creator_id="test_user",
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def voice_drop(file_key: str = "test_voice_123") -> TestDrop:
        """Create a voice RainDrop."""
        return TestDrop(
            id=f"test_voice_{datetime.now(timezone.utc).timestamp()}",
            type="voice",
            content=f"Voice memo: {file_key}",
            source="feishu://voice",
            creator_id="test_user",
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def knowledge_item(label: str, source: str = "test") -> dict:
        """Create a knowledge item for GraphDB."""
        return {
            "id": f"node_{datetime.now(timezone.utc).timestamp()}",
            "type": "atomic_note",
            "label": label,
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


@pytest.fixture
def test_data() -> TestDataFactory:
    """Provide test data factory."""
    return TestDataFactory()
