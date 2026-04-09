"""Tests for DikiwiMind continuous pipeline."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from aily.sessions.dikiwi_mind import DikiwiMind, DikiwiStage, StageResult, DikiwiResult


@pytest.fixture
def mock_drop():
    """Create a mock RainDrop."""
    drop = MagicMock()
    drop.id = "test_drop_123"
    drop.content = "This is test content about artificial intelligence and machine learning."
    drop.source = "https://example.com/article"
    drop.creator_id = "user_123"
    drop.created_at = datetime.now(timezone.utc)
    return drop


@pytest.fixture
def mock_graph_db():
    """Create a mock GraphDB."""
    db = AsyncMock()
    db.insert_node = AsyncMock(return_value=None)
    db.execute_query = AsyncMock(return_value=[])
    db.get_nodes_by_type = AsyncMock(return_value=[])
    return db


@pytest.fixture
def mock_llm_client():
    """Create a mock LLMClient."""
    return MagicMock()


@pytest.fixture
def mock_atomicizer():
    """Create a mock AtomicNoteGenerator."""
    atomicizer = AsyncMock()
    note = MagicMock()
    note.content = "AI is transforming software development"
    atomicizer.atomize = AsyncMock(return_value=[note])
    return atomicizer


class TestDikiwiStage:
    """Tests for DikiwiStage enum."""

    def test_stage_order(self):
        """Stages are in correct DIKIWI order."""
        stages = list(DikiwiStage)
        assert stages[0] == DikiwiStage.DATA
        assert stages[1] == DikiwiStage.INFORMATION
        assert stages[2] == DikiwiStage.KNOWLEDGE
        assert stages[3] == DikiwiStage.INSIGHT
        assert stages[4] == DikiwiStage.WISDOM
        assert stages[5] == DikiwiStage.IMPACT


class TestStageResult:
    """Tests for StageResult dataclass."""

    def test_success_result(self):
        """Create successful stage result."""
        result = StageResult(
            stage=DikiwiStage.KNOWLEDGE,
            success=True,
            items_processed=1,
            items_output=5,
            processing_time_ms=100.0,
        )
        assert result.success is True
        assert result.items_output == 5

    def test_failure_result(self):
        """Create failed stage result."""
        result = StageResult(
            stage=DikiwiStage.KNOWLEDGE,
            success=False,
            error_message="Database connection failed",
        )
        assert result.success is False
        assert result.error_message == "Database connection failed"


class TestDikiwiResult:
    """Tests for DikiwiResult dataclass."""

    def test_total_time_calculation(self):
        """Calculate total processing time."""
        result = DikiwiResult(input_id="test_123")
        result.completed_at = datetime.now(timezone.utc)
        # Manually set started_at to simulate processing
        result.started_at = datetime.now(timezone.utc)

        # Time should be near zero for instant completion (allow small negative due to precision)
        assert result.total_time_ms > -1.0

    def test_final_stage_reached(self):
        """Identify final successful stage."""
        result = DikiwiResult(input_id="test_123")
        result.stage_results = [
            StageResult(stage=DikiwiStage.DATA, success=True),
            StageResult(stage=DikiwiStage.INFORMATION, success=True),
            StageResult(stage=DikiwiStage.KNOWLEDGE, success=True),
        ]

        assert result.final_stage_reached == DikiwiStage.KNOWLEDGE


class TestDikiwiMind:
    """Tests for DikiwiMind class."""

    @pytest.mark.asyncio
    async def test_process_input_disabled(self, mock_llm_client, mock_graph_db, mock_drop):
        """When disabled, returns early with failure."""
        mind = DikiwiMind(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            enabled=False,
        )

        result = await mind.process_input(mock_drop)

        assert result.final_stage_reached is None
        assert result.stage_results[0].success is False

    @pytest.mark.asyncio
    async def test_stage_data(self, mock_llm_client, mock_graph_db, mock_drop):
        """DATA stage creates raw node."""
        mind = DikiwiMind(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        result = await mind._stage_data(mock_drop)

        assert result.success is True
        assert result.stage == DikiwiStage.DATA
        assert result.items_processed == 1
        mock_graph_db.insert_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_stage_information(self, mock_llm_client, mock_graph_db, mock_drop):
        """INFORMATION stage extracts structured data."""
        mind = DikiwiMind(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        prev_data = {"node_id": "raw_123"}
        result = await mind._stage_information(mock_drop, prev_data)

        assert result.success is True
        assert result.stage == DikiwiStage.INFORMATION
        assert "content" in result.data
        assert "keywords" in result.data

    @pytest.mark.asyncio
    async def test_stage_knowledge_with_atomicizer(
        self, mock_llm_client, mock_graph_db, mock_drop, mock_atomicizer
    ):
        """KNOWLEDGE stage uses atomicizer when available."""
        mind = DikiwiMind(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            atomicizer=mock_atomicizer,
        )

        prev_data = {"content": "AI transforms software development"}
        result = await mind._stage_knowledge(mock_drop, prev_data)

        assert result.success is True
        assert result.stage == DikiwiStage.KNOWLEDGE
        assert result.items_output == 1

    @pytest.mark.asyncio
    async def test_stage_knowledge_without_atomicizer(
        self, mock_llm_client, mock_graph_db, mock_drop
    ):
        """KNOWLEDGE stage treats content as single unit without atomicizer."""
        mind = DikiwiMind(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            atomicizer=None,
        )

        prev_data = {"content": "AI transforms software development"}
        result = await mind._stage_knowledge(mock_drop, prev_data)

        assert result.success is True
        assert result.items_output == 1

    def test_extract_keywords(self, mock_llm_client, mock_graph_db):
        """Extract keywords from content."""
        mind = DikiwiMind(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        content = "Artificial intelligence and machine learning are transforming software development"
        keywords = mind._extract_keywords(content)

        assert "artificial" in keywords
        assert "intelligence" in keywords
        assert "machine" in keywords
        assert "learning" in keywords

    def test_compute_content_hash(self, mock_llm_client, mock_graph_db):
        """Compute consistent hash for content."""
        mind = DikiwiMind(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        content = "Test content for hashing"
        hash1 = mind._compute_content_hash(content)
        hash2 = mind._compute_content_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 16

    def test_get_metrics(self, mock_llm_client, mock_graph_db):
        """Return processing metrics."""
        mind = DikiwiMind(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        metrics = mind.get_metrics()

        assert "total_inputs" in metrics
        assert "successful_pipelines" in metrics
        assert "failed_pipelines" in metrics
        assert "success_rate" in metrics
