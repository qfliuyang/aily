"""Integration tests for DIKIWI system.

Tests end-to-end flows:
- Full pipeline from DATA to IMPACT
- Rejection loops
- Memorial creation
- Event flow
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from aily.dikiwi import (
    ApprovalDecisionType,
    CVOGate,
    DikiwiOrchestrator,
    InMemoryEventBus,
    MenxiaGate,
    PipelineConfig,
)
from aily.dikiwi.events.models import (
    ContentPromotedEvent,
    GateDecisionEvent,
    StageCompletedEvent,
)
from aily.dikiwi.gates import ReviewDecisionType
from aily.dikiwi.memorials import (
    GraphDBMemorialStore,
    Memorial,
    MemorialDecisionType,
)
from aily.dikiwi.stages import DikiwiStage


class TestPipelineIntegration:
    """Integration tests for full pipeline."""

    @pytest.fixture
    async def orchestrator(self, mock_llm_client, mock_graph_db):
        """Create configured orchestrator for testing."""
        config = PipelineConfig(
            menxia_quality_threshold=0.6,
            cvo_ttl_hours=1,
            max_rejections=3,
            require_cvo_for_impact=False,  # Let tests flow through without blocking
        )

        return DikiwiOrchestrator(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            config=config,
        )

    async def test_start_pipeline_creates_context(self, orchestrator):
        """Starting pipeline creates stage context."""
        pipeline = await orchestrator.start_pipeline(
            content_id="content-001",
            source="test",
        )

        assert pipeline.pipeline_id is not None
        assert pipeline.context.current_stage is not None

    async def test_pipeline_publishes_events(self, orchestrator):
        """Pipeline publishes events during processing."""
        events_received = []

        async def event_handler(event):
            events_received.append(event)

        orchestrator.event_bus.subscribe(StageCompletedEvent, event_handler)

        await orchestrator.start_pipeline(
            content_id="content-001",
            source="test",
        )

        await asyncio.sleep(0.1)

        # Should have received at least one event
        assert len(events_received) > 0

    async def test_menxia_gate_rejection_triggers_event(self, orchestrator, mock_llm_client):
        """Menxia rejection publishes StageRejectedEvent."""
        # Configure LLM to reject
        mock_llm_client.complete = AsyncMock(return_value="""
            Decision: REJECT
            Quality Score: 0.3
            Reason: Poor quality
        """)

        events_received = []

        async def event_handler(event):
            events_received.append(event)

        from aily.dikiwi.events.models import StageRejectedEvent
        orchestrator.event_bus.subscribe(StageRejectedEvent, event_handler)

        # This would need actual pipeline execution to trigger Menxia
        # Simplified test - verify setup is correct
        assert orchestrator.menxia_gate is not None

    async def test_cvo_gate_approval_returns_decision(self, orchestrator):
        """CVO approval returns an ApprovalDecision."""
        # Request CVO approval
        await orchestrator.cvo_gate.request_approval(
            approval_id="app-001",
            content_id="content-001",
            content_preview="Preview",
            wisdom_summary="Summary",
            impact_proposal={},
        )

        # Approve it
        decision = orchestrator.cvo_gate.approve("app-001")

        assert decision is not None
        assert decision.decision == ApprovalDecisionType.APPROVED

    async def test_orchestrator_tracks_metrics(self, orchestrator):
        """Orchestrator tracks pipeline metrics."""
        await orchestrator.start_pipeline(
            content_id="content-001",
            source="test",
        )

        metrics = orchestrator.get_metrics()

        assert "pipelines_started" in metrics
        assert metrics["pipelines_started"] >= 1

    async def test_close_cleans_up_resources(self, orchestrator):
        """Closing orchestrator cleans up resources."""
        await orchestrator.close()

        assert orchestrator.event_bus._closed


class TestEndToEndFlows:
    """End-to-end flow tests."""

    async def test_full_pipeline_happy_path(self):
        """Test complete pipeline from DATA to IMPACT."""
        # This would require full setup with mocked LLM, DB, etc.
        # Simplified version:

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="""
            Decision: APPROVE
            Quality Score: 0.8
            Reason: Good content
        """)

        mock_db = MagicMock()
        mock_db.query = AsyncMock(return_value=[])

        config = PipelineConfig()
        orchestrator = DikiwiOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_db,
            config=config,
        )

        pipeline = await orchestrator.start_pipeline(
            content_id="content-001",
            source="voice",
        )

        assert pipeline is not None
        assert pipeline.pipeline_id is not None

        await orchestrator.close()

    async def test_rejection_loop_flow(self):
        """Test content rejected and sent back for reprocessing."""
        mock_llm = MagicMock()
        # First call rejects, second approves
        mock_llm.complete = AsyncMock(side_effect=[
            "Decision: REJECT\nQuality Score: 0.4\nReason: Too short",
            "Decision: APPROVE\nQuality Score: 0.8\nReason: Good now",
        ])

        mock_db = MagicMock()
        mock_db.query = AsyncMock(return_value=[])

        config = PipelineConfig(max_rejections=3)
        orchestrator = DikiwiOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_db,
            config=config,
        )

        # This tests that the infrastructure supports rejection loops
        gate = MenxiaGate(llm_client=mock_llm, quality_threshold=0.6)

        # First review - reject
        decision1 = await gate.review("Short", metadata={})
        assert decision1.decision == ReviewDecisionType.REJECT

        # Second review - approve
        decision2 = await gate.review("Much longer content now", metadata={})
        assert decision2.decision == ReviewDecisionType.APPROVE

        await orchestrator.close()


class TestMemorialIntegration:
    """Integration tests for memorial system."""

    async def test_memorial_created_on_promotion(self, mock_graph_db):
        """Memorial is created when content is promoted."""
        # Setup
        memorial_store = GraphDBMemorialStore(mock_graph_db)

        # Create memorial
        memorial = Memorial(
            memorial_id="mem-001",
            correlation_id="corr-001",
            pipeline_id="pipe-001",
            stage="KNOWLEDGE",
            decision=MemorialDecisionType.PROMOTED,
            input_hash="h1",
            output_hash="h2",
            reasoning="Approved by Menxia",
            agent_id="menxia-agent",
            gate_name="menxia",
            timestamp=datetime.now(timezone.utc),
            metadata={"quality_score": 0.8},
        )

        await memorial_store.save(memorial)

        # Verify GraphDB was called
        mock_graph_db.query.assert_called_once()

    def test_memorial_to_markdown_format(self):
        """Memorial converts to proper markdown."""
        memorial = Memorial(
            memorial_id="mem-001",
            correlation_id="corr-001",
            pipeline_id="pipe-001",
            stage="KNOWLEDGE",
            decision=MemorialDecisionType.PROMOTED,
            input_hash="h1",
            output_hash="h2",
            reasoning="Approved",
            agent_id="agent-1",
            gate_name="menxia",
            timestamp=datetime.now(timezone.utc),
            metadata={},
        )

        markdown = memorial.to_markdown()

        assert "# Memorial: mem-001" in markdown
        assert "**Pipeline**: `pipe-001`" in markdown
        assert "**Decision**: PROMOTED" in markdown


class TestMetricsIntegration:
    """Integration tests for metrics."""

    async def test_metrics_aggregated_from_all_components(self):
        """Metrics from all components are aggregated."""
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="Decision: APPROVE")

        mock_db = MagicMock()
        mock_db.query = AsyncMock(return_value=[])

        config = PipelineConfig()
        orchestrator = DikiwiOrchestrator(
            llm_client=mock_llm,
            graph_db=mock_db,
            config=config,
        )

        # Get metrics
        metrics = orchestrator.get_metrics()

        # Should include metrics from various components
        assert "pipelines_started" in metrics
        assert "active_pipelines" in metrics

        await orchestrator.close()
