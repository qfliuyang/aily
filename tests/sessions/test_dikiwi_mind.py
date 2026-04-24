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
    drop.content = (
        "Artificial intelligence and machine learning are transforming industries worldwide. "
        "Organizations are investing heavily in AI infrastructure, talent acquisition, and research "
        "and development to stay competitive in an increasingly automated landscape.\n\n"
        "Recent advances in large language models have demonstrated remarkable capabilities in "
        "natural language understanding, code generation, and complex reasoning tasks. These "
        "breakthroughs are driving adoption across healthcare, finance, education, and manufacturing "
        "sectors, creating both opportunities and challenges for policymakers and business leaders."
    )
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
    async def test_stage_data(self, mock_graph_db, mock_drop):
        """DATA stage extracts data points (LLM fallback path)."""
        llm = AsyncMock()
        llm.chat_json = AsyncMock(return_value={"data_points": [
            {"content": "AI improves productivity", "context": "test", "confidence": 0.9}
        ]})
        mind = DikiwiMind(
            llm_client=llm,
            graph_db=mock_graph_db,
        )

        result = await mind._stage_data(mock_drop)

        assert result.success is True
        assert result.stage == DikiwiStage.DATA
        assert result.items_processed == 1
        assert "data_points" in result.data

    @pytest.mark.asyncio
    async def test_stage_information(self, mock_graph_db):
        """INFORMATION stage classifies data points into info nodes using batch call."""
        from aily.sessions.dikiwi_mind import DataPoint
        llm = AsyncMock()
        llm.chat_json = AsyncMock(return_value={
            "classifications": [
                {"index": 0, "tags": ["AI", "productivity"], "info_type": "fact", "domain": "technology", "confidence": 0.9}
            ]
        })
        mind = DikiwiMind(llm_client=llm, graph_db=mock_graph_db)
        data_points = [DataPoint(id="dp_1", content="AI improves productivity", source="test")]

        result = await mind._stage_information(data_points, "test")

        assert result.success is True
        assert result.stage == DikiwiStage.INFORMATION
        assert "information_nodes" in result.data
        assert len(result.data["information_nodes"]) == 1
        assert result.data["information_nodes"][0].data_point_ids == ["dp_1"]

    @pytest.mark.asyncio
    async def test_stage_knowledge_batch(self, mock_graph_db):
        """KNOWLEDGE stage maps relations in one batch call."""
        from aily.sessions.dikiwi_mind import InformationNode
        llm = AsyncMock()
        llm.chat_json = AsyncMock(return_value={
            "links": [{"node_a_index": 0, "node_b_index": 1, "relation_type": "leads_to", "strength": 0.8}]
        })
        mind = DikiwiMind(llm_client=llm, graph_db=mock_graph_db)
        nodes = [
            InformationNode(id="info_1", data_point_id="dp_1", content="A", domain="tech"),
            InformationNode(id="info_2", data_point_id="dp_2", content="B", domain="tech"),
        ]

        result = await mind._stage_knowledge(nodes, "test")

        assert result.success is True
        assert result.stage == DikiwiStage.KNOWLEDGE
        assert result.items_output == 1

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

    def test_client_for_stage_uses_resolver(self, mock_graph_db):
        clients = {
            "dikiwi.data": object(),
            "dikiwi.insight": object(),
        }

        def resolver(workload: str):
            return clients.get(workload)

        shared_client = object()
        mind = DikiwiMind(
            llm_client=shared_client,
            llm_client_resolver=resolver,
            graph_db=mock_graph_db,
        )

        assert mind._client_for_stage(DikiwiStage.DATA) is clients["dikiwi.data"]
        assert mind._client_for_stage(DikiwiStage.INSIGHT) is clients["dikiwi.insight"]
        assert mind._client_for_stage(DikiwiStage.WISDOM) is shared_client
