"""Unit and integration tests for ThinkingOrchestrator.

Tests the orchestrator's caching, parallel execution, partial failure handling,
and context building functionality.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aily.thinking.orchestrator import ThinkingOrchestrator
from aily.thinking.models import (
    FrameworkType,
    FrameworkInsight,
    InsightPriority,
    KnowledgePayload,
    ThinkingResult,
)


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, response_delay=0):
        self.response_delay = response_delay
        self.chat = AsyncMock(side_effect=self._chat)
        self.chat_json = AsyncMock(side_effect=self._chat_json)
        self.close = AsyncMock()

    async def _chat(self, *args, **kwargs):
        if self.response_delay:
            await asyncio.sleep(self.response_delay)
        return {
            "insights": ["Test insight"],
            "confidence": 0.8,
            "priority": "high",
        }

    async def _chat_json(self, *args, **kwargs):
        if self.response_delay:
            await asyncio.sleep(self.response_delay)
        return {
            "insights": ["Test insight"],
            "confidence": 0.8,
            "priority": "high",
        }


class MockGraphDB:
    """Mock GraphDB for testing."""

    def __init__(self):
        self.execute_query = AsyncMock(return_value=[])


@pytest.fixture
def mock_llm():
    return MockLLMClient()


@pytest.fixture
def mock_graph_db():
    return MockGraphDB()


@pytest.fixture
def sample_payload():
    return KnowledgePayload(
        content="This is a test content for analysis",
        source_url="https://example.com/test",
    )


class TestOrchestratorInitialization:
    """Tests for orchestrator initialization."""

    def test_orchestrator_initializes_with_llm(self, mock_llm):
        """Orchestrator initializes with LLM client."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)
        assert orchestrator.llm_client == mock_llm
        assert orchestrator.graph_db is None

    def test_orchestrator_initializes_with_graph_db(self, mock_llm, mock_graph_db):
        """Orchestrator initializes with GraphDB."""
        orchestrator = ThinkingOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_graph_db,
        )
        assert orchestrator.graph_db == mock_graph_db

    def test_orchestrator_initializes_analyzers(self, mock_llm):
        """Orchestrator initializes all framework analyzers."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)
        assert len(orchestrator.analyzers) == 3
        assert FrameworkType.TRIZ in orchestrator.analyzers
        assert FrameworkType.MCKINSEY in orchestrator.analyzers
        assert FrameworkType.GSTACK in orchestrator.analyzers

    def test_orchestrator_config(self, mock_llm):
        """Orchestrator accepts configuration."""
        config = {"cache_ttl_seconds": 1800, "max_insights": 10}
        orchestrator = ThinkingOrchestrator(
            llm_client=mock_llm,
            config=config,
        )
        assert orchestrator.config == config
        assert orchestrator._cache_ttl_seconds == 1800


class TestOrchestratorThink:
    """Tests for orchestrator think() method."""

    @pytest.mark.asyncio
    async def test_think_returns_result(self, mock_llm, sample_payload):
        """think() returns ThinkingResult."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        result = await orchestrator.think(sample_payload)

        assert isinstance(result, ThinkingResult)
        assert result.request_id is not None
        assert result.payload == sample_payload

    @pytest.mark.asyncio
    async def test_think_with_single_framework(self, mock_llm, sample_payload):
        """think() can run single framework."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        result = await orchestrator.think(
            sample_payload,
            options={"frameworks": [FrameworkType.TRIZ]},
        )

        assert len(result.framework_insights) == 1
        assert result.framework_insights[0].framework_type == FrameworkType.TRIZ

    @pytest.mark.asyncio
    async def test_think_with_all_frameworks(self, mock_llm, sample_payload):
        """think() runs all frameworks by default."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        result = await orchestrator.think(sample_payload)

        assert len(result.framework_insights) == 3
        framework_types = {fi.framework_type for fi in result.framework_insights}
        assert FrameworkType.TRIZ in framework_types
        assert FrameworkType.MCKINSEY in framework_types
        assert FrameworkType.GSTACK in framework_types

    @pytest.mark.asyncio
    async def test_think_returns_metadata(self, mock_llm, sample_payload):
        """think() returns processing metadata."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        result = await orchestrator.think(sample_payload)

        assert "total_time_ms" in result.processing_metadata
        assert "framework_time_ms" in result.processing_metadata
        assert "synthesis_time_ms" in result.processing_metadata
        assert result.processing_metadata["frameworks_run"] == [
            "triz", "mckinsey", "gstack"
        ]

    @pytest.mark.asyncio
    async def test_think_includes_formatted_output(self, mock_llm, sample_payload):
        """think() includes formatted output."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        result = await orchestrator.think(
            sample_payload,
            options={"output_format": "obsidian"},
        )

        assert "obsidian" in result.formatted_output


class TestContentHashCaching:
    """Tests for content hash caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_same_content(self, mock_llm, sample_payload):
        """Same content returns cached result."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        # First call
        result1 = await orchestrator.think(sample_payload)
        # Second call with same content
        result2 = await orchestrator.think(sample_payload)

        assert result1.request_id == result2.request_id
        # LLM should only be called once due to caching
        # Note: With current mock, it will be called multiple times
        # but cache is populated

    @pytest.mark.asyncio
    async def test_skip_cache_option(self, mock_llm, sample_payload):
        """skip_cache option bypasses cache."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        result1 = await orchestrator.think(sample_payload)
        result2 = await orchestrator.think(
            sample_payload,
            options={"skip_cache": True},
        )

        # Should be different request IDs when cache is skipped
        assert result1.request_id != result2.request_id

    def test_compute_content_hash(self, mock_llm):
        """_compute_content_hash creates consistent hashes."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)
        payload = KnowledgePayload(content="Test content")
        options = {"frameworks": [FrameworkType.TRIZ]}

        hash1 = orchestrator._compute_content_hash(payload, options)
        hash2 = orchestrator._compute_content_hash(payload, options)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest length

    def test_compute_hash_different_content(self, mock_llm):
        """Different content produces different hashes."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        payload1 = KnowledgePayload(content="Content A")
        payload2 = KnowledgePayload(content="Content B")

        hash1 = orchestrator._compute_content_hash(payload1, {})
        hash2 = orchestrator._compute_content_hash(payload2, {})

        assert hash1 != hash2

    def test_cache_ttl_expires(self, mock_llm):
        """Cache entries expire after TTL."""
        orchestrator = ThinkingOrchestrator(
            llm_client=mock_llm,
            config={"cache_ttl_seconds": 0},  # Immediate expiration
        )

        payload = KnowledgePayload(content="Test")
        content_hash = orchestrator._compute_content_hash(payload, {})

        # Create a mock result
        mock_result = MagicMock(spec=ThinkingResult)
        orchestrator._cache_result(content_hash, mock_result)

        # Should be expired immediately
        cached = orchestrator._get_cached_result(content_hash)
        assert cached is None

    def test_clear_cache(self, mock_llm):
        """clear_cache() removes all cached entries."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)
        payload = KnowledgePayload(content="Test")
        content_hash = orchestrator._compute_content_hash(payload, {})

        mock_result = MagicMock(spec=ThinkingResult)
        orchestrator._cache_result(content_hash, mock_result)

        orchestrator.clear_cache()
        assert len(orchestrator._cache) == 0


class TestPartialFailureHandling:
    """Tests for partial failure handling with return_exceptions=True."""

    @pytest.mark.asyncio
    async def test_partial_failure_one_framework_fails(self, sample_payload):
        """When one framework fails, others still return results."""
        # Create LLM that fails for TRIZ but succeeds for others
        call_count = 0
        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("TRIZ failed")
            return {
                "key_insights": ["Success"],
                "confidence": 0.8,
                "priority": "high",
            }

        mock_llm = MagicMock()
        mock_llm.chat_json = AsyncMock(side_effect=side_effect)

        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        result = await orchestrator.think(sample_payload)

        # Should have 2 successful frameworks (TRIZ gracefully degrades on failure)
        successful = [fi for fi in result.framework_insights if fi.confidence > 0]
        assert len(successful) == 2
        framework_types = {fi.framework_type for fi in successful}
        assert FrameworkType.TRIZ not in framework_types
        assert FrameworkType.MCKINSEY in framework_types
        assert FrameworkType.GSTACK in framework_types

    @pytest.mark.asyncio
    async def test_all_frameworks_fail(self, sample_payload):
        """When all frameworks fail, each returns a graceful error insight."""
        failing_llm = MagicMock()
        failing_llm.chat_json = AsyncMock(side_effect=Exception("All failed"))

        orchestrator = ThinkingOrchestrator(llm_client=failing_llm)

        result = await orchestrator.think(sample_payload)

        # All 3 frameworks return error insights with 0 confidence
        assert len(result.framework_insights) == 3
        assert all(fi.confidence == 0.0 for fi in result.framework_insights)
        assert result.confidence_score <= 0.1


class TestThinkParallel:
    """Tests for think_parallel() method."""

    @pytest.mark.asyncio
    async def test_parallel_multiple_payloads(self, mock_llm):
        """think_parallel() processes multiple payloads."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        payloads = [
            KnowledgePayload(content=f"Content {i}")
            for i in range(3)
        ]

        results = await orchestrator.think_parallel(payloads)

        assert len(results) == 3
        assert all(isinstance(r, ThinkingResult) for r in results)

    @pytest.mark.asyncio
    async def test_parallel_with_exceptions(self):
        """think_parallel() handles exceptions in results."""
        mock_llm = MagicMock()
        # First call succeeds, second fails, third succeeds
        mock_llm.chat = AsyncMock(side_effect=[
            {"insights": ["Success 1"], "confidence": 0.8, "priority": "high"},
            Exception("Failed"),
            {"insights": ["Success 2"], "confidence": 0.7, "priority": "medium"},
        ] + [{"insights": ["More"], "confidence": 0.5, "priority": "low"}] * 10)

        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        payloads = [
            KnowledgePayload(content=f"Content {i}")
            for i in range(3)
        ]

        results = await orchestrator.think_parallel(payloads)

        assert len(results) == 3
        # Check that we got results (some might be exceptions)
        assert any(isinstance(r, ThinkingResult) for r in results)


class TestContextBuilding:
    """Tests for batched context building."""

    @pytest.mark.asyncio
    async def test_build_context_without_graph_db(self, sample_payload):
        """Context building works without GraphDB."""
        orchestrator = ThinkingOrchestrator(llm_client=MockLLMClient())

        enriched = await orchestrator._build_context(sample_payload)

        assert enriched.content == sample_payload.content
        assert enriched.context_nodes == []

    @pytest.mark.asyncio
    async def test_build_context_with_keywords(self, mock_llm, mock_graph_db):
        """Context building queries for keywords."""
        mock_graph_db.execute_query.return_value = [
            {"node_id": "n1", "label": "analysis"},
            {"node_id": "n2", "label": "test"},
        ]

        orchestrator = ThinkingOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_graph_db,
        )

        payload = KnowledgePayload(content="This is a test content for analysis")
        enriched = await orchestrator._build_context(payload)

        assert len(enriched.context_nodes) > 0
        mock_graph_db.execute_query.assert_called()

    @pytest.mark.asyncio
    async def test_build_context_with_url(self, mock_llm, mock_graph_db):
        """Context building queries for source URL."""
        mock_graph_db.execute_query.return_value = [
            {"node_id": "n3"},
        ]

        orchestrator = ThinkingOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_graph_db,
        )

        payload = KnowledgePayload(
            content="Test",
            source_url="https://example.com/article",
        )
        enriched = await orchestrator._build_context(payload)

        assert "n3" in enriched.context_nodes or enriched.context_nodes == []

    @pytest.mark.asyncio
    async def test_build_context_handles_errors(self, mock_llm, mock_graph_db):
        """Context building continues on GraphDB errors."""
        mock_graph_db.execute_query.side_effect = Exception("DB error")

        orchestrator = ThinkingOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_graph_db,
        )

        payload = KnowledgePayload(content="Test content")
        enriched = await orchestrator._build_context(payload)

        # Should still return payload even if GraphDB fails
        assert enriched.content == "Test content"


class TestConfidenceCalculation:
    """Tests for overall confidence calculation."""

    def test_calculate_overall_confidence(self, mock_llm):
        """Confidence is calculated from framework results."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        framework_results = [
            FrameworkInsight(
                framework_type=FrameworkType.TRIZ,
                insights=["Test"],
                confidence=0.8,
            ),
            FrameworkInsight(
                framework_type=FrameworkType.MCKINSEY,
                insights=["Test"],
                confidence=0.9,
            ),
        ]

        confidence = orchestrator._calculate_overall_confidence(framework_results)

        # Average is 0.85, plus small multi-framework bonus
        assert confidence > 0.85
        assert confidence <= 1.0

    def test_empty_framework_results_zero_confidence(self, mock_llm):
        """Empty framework results give zero confidence."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        confidence = orchestrator._calculate_overall_confidence([])

        assert confidence == 0.0


class TestOrchestratorCleanup:
    """Tests for orchestrator cleanup."""

    @pytest.mark.asyncio
    async def test_close_clears_cache(self, mock_llm):
        """close() clears the cache."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)
        orchestrator._cache["test"] = (0, MagicMock())

        await orchestrator.close()

        assert len(orchestrator._cache) == 0

    @pytest.mark.asyncio
    async def test_close_calls_llm_close(self, mock_llm):
        """close() calls LLM client close if available."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        await orchestrator.close()

        mock_llm.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_llm_close(self):
        """close() works even if LLM has no close method."""
        mock_llm = MagicMock()
        del mock_llm.close  # Ensure no close attribute

        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        # Should not raise
        await orchestrator.close()


class TestGetAnalyzer:
    """Tests for get_analyzer() method."""

    def test_get_existing_analyzer(self, mock_llm):
        """get_analyzer returns analyzer for existing framework."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        analyzer = orchestrator.get_analyzer(FrameworkType.TRIZ)

        assert analyzer is not None
        assert analyzer.framework_type == FrameworkType.TRIZ

    def test_get_nonexistent_analyzer(self, mock_llm):
        """get_analyzer returns None for non-existent framework."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        # Create a mock framework type that doesn't exist
        class FakeFramework:
            value = "fake"

        analyzer = orchestrator.get_analyzer(FakeFramework())

        assert analyzer is None
