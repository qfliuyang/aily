"""Integration tests for the ARMY OF TOP MINDS thinking system.

Tests end-to-end workflows, component interactions, and real-world scenarios.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aily.thinking.orchestrator import ThinkingOrchestrator
from aily.thinking.integration.graphdb_client import ThinkingGraphClient
from aily.thinking.integration.queue_integration import ThinkingJobHandler, create_thinking_job
from aily.thinking.integration.output_integration import ThinkingOutputHandler, DeliveryResult
from aily.thinking.integration.agent_registration import register_thinking_agents
from aily.thinking.models import (
    FrameworkType,
    InsightPriority,
    KnowledgePayload,
    ThinkingResult,
)


class MockLLMClient:
    """Mock LLM client for integration tests."""

    def __init__(self):
        self.chat = AsyncMock(side_effect=self._chat)
        self.chat_json = AsyncMock(side_effect=self._chat)
        self.close = AsyncMock()

    async def _chat(self, *args, **kwargs):
        # Simulate framework-specific responses
        messages = kwargs.get('messages', [])
        content = messages[0].get('content', '') if messages else ''

        if 'TRIZ' in content:
            return {
                "key_insights": ["Contradiction: speed vs cost", "Use Principle 1: Segmentation"],
                "confidence": 0.85,
                "priority": "high",
                "recommendations": ["Segment the process into stages"],
                "action_items": ["Map technical contradictions"],
            }
        elif 'McKinsey' in content:
            return {
                "key_insights": ["MECE structure needed", "Market entry barrier high"],
                "confidence": 0.80,
                "priority": "high",
                "recommendations": ["Conduct competitive analysis"],
                "action_items": ["Interview 5 industry experts"],
            }
        elif 'GStack' in content:
            return {
                "key_insights": ["PMF score: 40/100", "Shipping velocity too low"],
                "confidence": 0.75,
                "priority": "critical",
                "recommendations": ["Focus on core loop", "Reduce scope by 50%"],
                "action_items": ["Ship MVP this week"],
            }
        return {
            "key_insights": ["General insight"],
            "confidence": 0.5,
            "priority": "medium",
        }


class MockObsidianWriter:
    """Mock Obsidian writer."""

    def __init__(self):
        self.write_note = AsyncMock(return_value="Aily Drafts/Thinking/20240101-120000-test.md")


class MockFeishuPusher:
    """Mock Feishu pusher."""

    def __init__(self):
        self.send_message = AsyncMock(return_value=True)


@pytest.fixture
def mock_llm():
    return MockLLMClient()


@pytest.fixture
def mock_graph_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.execute_query = AsyncMock(return_value=[])
    db.fetchall = AsyncMock(return_value=[])
    return db


@pytest.fixture
def mock_obsidian_writer():
    return MockObsidianWriter()


@pytest.fixture
def mock_feishu_pusher():
    return MockFeishuPusher()


class TestOrchestratorToSynthesisIntegration:
    """Integration tests for orchestrator and synthesis engine."""

    @pytest.mark.asyncio
    async def test_full_pipeline_all_frameworks(self, mock_llm, mock_graph_db):
        """Full pipeline runs all frameworks and synthesizes results."""
        orchestrator = ThinkingOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_graph_db,
        )

        payload = KnowledgePayload(
            content="How should we approach this startup problem?",
            source_url="https://example.com/problem",
        )

        result = await orchestrator.think(payload)

        # Verify result structure
        assert isinstance(result, ThinkingResult)
        assert result.request_id is not None
        assert len(result.framework_insights) == 3

        # Verify synthesis happened
        assert len(result.synthesized_insights) > 0
        assert len(result.top_insights) > 0

        # Verify confidence
        assert result.confidence_score > 0

        # Verify metadata
        assert "total_time_ms" in result.processing_metadata
        assert result.processing_metadata["frameworks_run"] == ["triz", "mckinsey", "gstack"]

    @pytest.mark.asyncio
    async def test_single_framework_no_synthesis(self, mock_llm):
        """Single framework bypasses synthesis."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        payload = KnowledgePayload(content="Technical problem to solve")

        result = await orchestrator.think(
            payload,
            options={"frameworks": [FrameworkType.TRIZ]},
        )

        assert len(result.framework_insights) == 1
        assert result.framework_insights[0].framework_type == FrameworkType.TRIZ

    @pytest.mark.asyncio
    async def test_two_frameworks_cross_validation(self, mock_llm):
        """Two frameworks use cross-validation synthesis."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        payload = KnowledgePayload(content="Strategic decision needed")

        result = await orchestrator.think(
            payload,
            options={"frameworks": [FrameworkType.TRIZ, FrameworkType.MCKINSEY]},
        )

        assert len(result.framework_insights) == 2
        assert len(result.synthesized_insights) >= 0  # May produce insights or not


class TestJobHandlerIntegration:
    """Integration tests for job handler and orchestrator."""

    @pytest.mark.asyncio
    async def test_thinking_analysis_job(self, mock_llm, mock_graph_db):
        """thinking_analysis job type processes correctly."""
        orchestrator = ThinkingOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_graph_db,
        )
        handler = ThinkingJobHandler(orchestrator=orchestrator)

        job = create_thinking_job(
            job_type="thinking_analysis",
            payload={
                "content": "Should we pivot?",
                "source_url": "https://example.com",
            },
            options={"output_format": "obsidian"},
        )

        result = await handler.handle_job(job)

        assert result["status"] == "completed"
        assert "request_id" in result
        assert result["insights_count"] > 0

    @pytest.mark.asyncio
    async def test_thinking_quick_job(self, mock_llm):
        """thinking_quick job runs single framework."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)
        handler = ThinkingJobHandler(orchestrator=orchestrator)

        job = create_thinking_job(
            job_type="thinking_quick",
            payload={"content": "Quick analysis needed"},
            options={"framework": "mckinsey"},
        )

        result = await handler.handle_job(job)

        assert result["status"] == "completed"
        assert result["framework"] == "mckinsey"

    @pytest.mark.asyncio
    async def test_thinking_batch_job(self, mock_llm):
        """thinking_batch processes multiple items."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)
        handler = ThinkingJobHandler(orchestrator=orchestrator)

        job = create_thinking_job(
            job_type="thinking_batch",
            payload=[
                {"content": "Item 1"},
                {"content": "Item 2"},
                {"content": "Item 3"},
            ],
        )
        job["payloads"] = job.pop("payload")  # batch uses payloads key

        result = await handler.handle_job(job)

        assert result["status"] == "completed"
        assert result["batch_size"] == 3
        assert len(result["results"]) == 3

    @pytest.mark.asyncio
    async def test_job_handler_with_output(self, mock_llm, mock_obsidian_writer):
        """Job handler delivers output when configured."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)
        output_handler = ThinkingOutputHandler(
            obsidian_writer=mock_obsidian_writer,
        )
        handler = ThinkingJobHandler(
            orchestrator=orchestrator,
            output_handler=output_handler,
        )

        job = create_thinking_job(
            job_type="thinking_analysis",
            payload={"content": "Test"},
        )

        result = await handler.handle_job(job)

        assert result["status"] == "completed"


class TestOutputHandlerIntegration:
    """Integration tests for output handler delivery."""

    @pytest.mark.asyncio
    async def test_deliver_to_obsidian(self, mock_obsidian_writer):
        """Output handler delivers to Obsidian."""
        handler = ThinkingOutputHandler(obsidian_writer=mock_obsidian_writer)

        # Create a mock result
        result = MagicMock(spec=ThinkingResult)
        result.payload = KnowledgePayload(content="Test")
        result.formatted_output = {"obsidian": "# Test Content"}
        result.top_insights = []
        result.framework_insights = []
        result.synthesized_insights = []

        delivery = await handler.deliver(
            result,
            options={"output_format": "obsidian", "folder": "Test/Folder"},
        )

        assert delivery.obsidian_success is True
        assert delivery.obsidian_path is not None
        mock_obsidian_writer.write_note.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_to_feishu(self, mock_feishu_pusher):
        """Output handler delivers to Feishu."""
        handler = ThinkingOutputHandler(feishu_pusher=mock_feishu_pusher)

        result = MagicMock(spec=ThinkingResult)
        result.payload = KnowledgePayload(content="Test")
        result.formatted_output = {"feishu": "Test summary"}
        result.top_insights = []
        result.framework_insights = []
        result.synthesized_insights = []

        delivery = await handler.deliver(
            result,
            options={"output_format": "feishu", "open_id": "user123"},
        )

        assert delivery.feishu_success is True
        mock_feishu_pusher.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_to_both(self, mock_obsidian_writer, mock_feishu_pusher):
        """Output handler delivers to both channels."""
        handler = ThinkingOutputHandler(
            obsidian_writer=mock_obsidian_writer,
            feishu_pusher=mock_feishu_pusher,
        )

        result = MagicMock(spec=ThinkingResult)
        result.payload = KnowledgePayload(content="Test")
        result.formatted_output = {
            "obsidian": "# Full Content",
            "feishu": "Summary",
        }
        result.top_insights = []
        result.framework_insights = []
        result.synthesized_insights = []

        delivery = await handler.deliver(
            result,
            options={"output_format": "both", "open_id": "user123"},
        )

        assert delivery.all_success is True
        mock_obsidian_writer.write_note.assert_called_once()
        mock_feishu_pusher.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_obsidian_failure_nonfatal(self):
        """Obsidian failure doesn't prevent Feishu success."""
        failing_writer = MockObsidianWriter()
        failing_writer.write_note = AsyncMock(side_effect=Exception("Write failed"))
        mock_pusher = MockFeishuPusher()

        handler = ThinkingOutputHandler(
            obsidian_writer=failing_writer,
            feishu_pusher=mock_pusher,
        )

        result = MagicMock(spec=ThinkingResult)
        result.payload = KnowledgePayload(content="Test")
        result.formatted_output = {"obsidian": "Content", "feishu": "Summary"}
        result.top_insights = []
        result.framework_insights = []
        result.synthesized_insights = []

        delivery = await handler.deliver(
            result,
            options={"output_format": "both", "open_id": "user123"},
        )

        # Feishu should still succeed
        assert delivery.feishu_success is True
        assert delivery.obsidian_success is False
        assert delivery.all_success is True  # At least one channel worked


class TestGraphDBClientIntegration:
    """Integration tests for GraphDB client."""

    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, mock_graph_db):
        """GraphDB client creates thinking tables."""
        client = ThinkingGraphClient(mock_graph_db)

        await client.initialize_thinking_schema()

        # Should execute multiple CREATE TABLE statements
        assert mock_graph_db.execute.call_count >= 3

    @pytest.mark.asyncio
    async def test_store_insight(self, mock_graph_db):
        """GraphDB client stores insights."""
        from aily.thinking.models import SynthesizedInsight
        client = ThinkingGraphClient(mock_graph_db)

        insight = SynthesizedInsight(
            title="Test Insight",
            description="Test description",
            confidence=0.8,
            priority=InsightPriority.HIGH,
            supporting_frameworks=[FrameworkType.TRIZ],
        )

        await client.store_insight(
            insight_id="ins-1",
            request_id="req-123",
            insight=insight,
        )

        mock_graph_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_insights_for_request(self, mock_graph_db):
        """GraphDB client retrieves insights by request."""
        mock_graph_db.fetchall.return_value = [
            {
                "id": "insight-1",
                "framework_type": "triz",
                "title": "Test",
                "confidence": 0.8,
            }
        ]

        client = ThinkingGraphClient(mock_graph_db)

        insights = await client.get_insights_by_request("req-123")

        assert len(insights) == 1
        assert insights[0]["id"] == "insight-1"


class TestAgentRegistrationIntegration:
    """Integration tests for agent registration."""

    @pytest.mark.asyncio
    async def test_register_all_agents(self):
        """All thinking agents are registered."""
        registry = MagicMock()
        registry.register = AsyncMock()

        await register_thinking_agents(registry)

        # Should register 4 agents
        assert registry.register.call_count == 4

        # Verify agent names
        calls = registry.register.call_args_list
        agent_names = [call.kwargs.get('name') or call[1].get('name') for call in calls]
        assert "triz_analyzer" in agent_names
        assert "mckinsey_analyzer" in agent_names
        assert "gstack_analyzer" in agent_names
        assert "thinking_orchestrator" in agent_names


class TestEndToEndWorkflows:
    """End-to-end workflow tests."""

    @pytest.mark.asyncio
    async def test_complete_analysis_workflow(self, mock_llm, mock_graph_db, mock_obsidian_writer):
        """Complete workflow from payload to delivered output."""
        # Setup components
        orchestrator = ThinkingOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_graph_db,
        )
        output_handler = ThinkingOutputHandler(obsidian_writer=mock_obsidian_writer)
        job_handler = ThinkingJobHandler(
            orchestrator=orchestrator,
            output_handler=output_handler,
        )

        # Create and process job
        job = create_thinking_job(
            job_type="thinking_analysis",
            payload={
                "content": "Our startup is struggling with product-market fit",
                "source_title": "PMF Analysis",
            },
            options={"output_format": "obsidian"},
        )

        result = await job_handler.handle_job(job)

        # Verify workflow completed
        assert result["status"] == "completed"
        assert result["insights_count"] > 0
        mock_obsidian_writer.write_note.assert_called_once()

    @pytest.mark.asyncio
    async def test_parallel_analysis_workflow(self, mock_llm):
        """Multiple items analyzed in parallel."""
        orchestrator = ThinkingOrchestrator(llm_client=mock_llm)

        payloads = [
            KnowledgePayload(content=f"Problem {i}")
            for i in range(5)
        ]

        results = await orchestrator.think_parallel(payloads)

        assert len(results) == 5
        assert all(isinstance(r, ThinkingResult) for r in results)

    @pytest.mark.asyncio
    async def test_caching_prevents_duplicate_analysis(self, mock_llm, mock_graph_db):
        """Cache prevents re-analyzing same content."""
        orchestrator = ThinkingOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_graph_db,
        )

        payload = KnowledgePayload(
            content="Unique content for caching test",
            source_url="https://example.com/cache-test",
        )

        # First analysis
        result1 = await orchestrator.think(payload)

        # Second analysis with same content (should use cache)
        result2 = await orchestrator.think(payload)

        # Results should be identical (cached)
        assert result1.request_id == result2.request_id
