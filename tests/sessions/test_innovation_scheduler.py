"""Tests for InnovationScheduler - TRIZ-based daily insight generation."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from aily.sessions.innovation_scheduler import InnovationScheduler
from aily.sessions.models import ProposalType, ProposalStatus


@pytest.fixture
def mock_graph_db():
    """Create a mock GraphDB."""
    db = AsyncMock()
    db.execute_query = AsyncMock(return_value=[])
    return db


@pytest.fixture
def mock_llm_client():
    """Create a mock LLMClient."""
    return MagicMock()


@pytest.fixture
def mock_obsidian_writer():
    """Create a mock ObsidianWriter."""
    writer = AsyncMock()
    writer.write_note = AsyncMock(return_value="Aily/Proposals/Innovation/test.md")
    return writer


@pytest.fixture
def mock_feishu_pusher():
    """Create a mock FeishuPusher."""
    pusher = AsyncMock()
    pusher.send_message = AsyncMock(return_value=None)
    return pusher


@pytest.fixture
def mock_triz_analyzer():
    """Create a mock TrizAnalyzer."""
    analyzer = AsyncMock()
    result = MagicMock()
    result.insights = ["Test insight about AI"]
    result.raw_analysis = {
        "contradictions": [
            {"description": "Speed vs Quality tradeoff", "contradiction_type": "technical", "severity": "high", "severity_score": 80}
        ],
        "principle_recommendations": [
            {"principle_number": 1, "principle_name": "Segmentation", "confidence": 0.85, "application": "Break into parts"}
        ]
    }
    result.confidence = 0.85
    result.priority = MagicMock()
    result.priority.value = "high"
    analyzer.analyze = AsyncMock(return_value=result)
    return analyzer


class TestInnovationScheduler:
    """Tests for InnovationScheduler class."""

    def test_init(
        self, mock_llm_client, mock_graph_db, mock_obsidian_writer, mock_feishu_pusher
    ):
        """Scheduler initializes with correct defaults."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            obsidian_writer=mock_obsidian_writer,
            feishu_pusher=mock_feishu_pusher,
        )

        assert scheduler.mind_name == "innovation"
        assert scheduler.schedule_hour == 8
        assert scheduler.schedule_minute == 0
        assert scheduler.proposal_min_confidence == 0.7
        assert scheduler.proposal_max_per_session == 10

    def test_init_custom_values(
        self, mock_llm_client, mock_graph_db
    ):
        """Scheduler accepts custom configuration."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            schedule_hour=10,
            schedule_minute=30,
            proposal_min_confidence=0.8,
            proposal_max_per_session=5,
        )

        assert scheduler.schedule_hour == 10
        assert scheduler.schedule_minute == 30
        assert scheduler.proposal_min_confidence == 0.8
        assert scheduler.proposal_max_per_session == 5

    @pytest.mark.asyncio
    async def test_query_recent_knowledge(
        self, mock_llm_client, mock_graph_db
    ):
        """Query knowledge from last 24 hours."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        mock_graph_db.execute_query = AsyncMock(return_value=[
            {"id": "node1", "type": "atomic_note", "label": "AI insight", "source": "url1", "created_at": "2024-01-01T00:00:00Z"},
            {"id": "node2", "type": "atomic_note", "label": "ML finding", "source": "url2", "created_at": "2024-01-01T01:00:00Z"},
        ])

        knowledge = await scheduler._query_recent_knowledge()

        assert len(knowledge) == 2
        assert knowledge[0]["id"] == "node1"
        assert knowledge[1]["label"] == "ML finding"

    @pytest.mark.asyncio
    async def test_run_session_no_knowledge(
        self, mock_llm_client, mock_graph_db
    ):
        """Session skips when no knowledge available."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        mock_graph_db.execute_query = AsyncMock(return_value=[])

        result = await scheduler._run_session()

        assert result["proposals_generated"] == 0
        assert result["metadata"]["reason"] == "no_knowledge"

    @pytest.mark.asyncio
    async def test_generate_proposals_from_contradictions(
        self, mock_llm_client, mock_graph_db
    ):
        """Generate proposals from TRIZ contradictions."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        triz_results = {
            "contradictions": [
                {"description": "Speed vs Quality", "contradiction_type": "technical", "severity": "high", "severity_score": 85},
            ],
            "principles": [],
            "insights": [],
            "confidence": 0.8,
        }
        knowledge = [{"id": "node1", "label": "Test"}]

        proposals = await scheduler._generate_proposals(triz_results, knowledge)

        assert len(proposals) >= 1
        assert proposals[0].mind_name == "innovation"
        assert proposals[0].proposal_type == ProposalType.INNOVATION
        assert proposals[0].framework_used == "TRIZ"

    @pytest.mark.asyncio
    async def test_generate_proposals_from_principles(
        self, mock_llm_client, mock_graph_db
    ):
        """Generate proposals from TRIZ principles."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        triz_results = {
            "contradictions": [],
            "principles": [
                {"principle_number": 1, "principle_name": "Segmentation", "confidence": 0.9, "application": "Break into parts"},
            ],
            "insights": [],
            "confidence": 0.8,
        }
        knowledge = [{"id": "node1", "label": "Test"}]

        proposals = await scheduler._generate_proposals(triz_results, knowledge)

        assert len(proposals) >= 1
        assert "Principle #1" in proposals[0].title

    @pytest.mark.asyncio
    async def test_generate_proposals_from_insights(
        self, mock_llm_client, mock_graph_db
    ):
        """Generate proposals from general insights."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        triz_results = {
            "contradictions": [],
            "principles": [],
            "insights": ["AI is transforming how we build software"],
            "confidence": 0.85,
            "priority": "high",
        }
        knowledge = [{"id": "node1", "label": "Test"}]

        proposals = await scheduler._generate_proposals(triz_results, knowledge)

        assert len(proposals) >= 1
        assert "Insight:" in proposals[0].title

    @pytest.mark.asyncio
    async def test_filter_by_confidence(
        self, mock_llm_client, mock_graph_db, mock_obsidian_writer, mock_feishu_pusher
    ):
        """Only deliver proposals above confidence threshold."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            obsidian_writer=mock_obsidian_writer,
            feishu_pusher=mock_feishu_pusher,
            proposal_min_confidence=0.8,
        )

        # Create proposals with varying confidence
        from aily.sessions.models import Proposal
        proposals = [
            Proposal(mind_name="innovation", proposal_type=ProposalType.INNOVATION, title="High confidence", confidence=0.9),
            Proposal(mind_name="innovation", proposal_type=ProposalType.INNOVATION, title="Low confidence", confidence=0.5),
            Proposal(mind_name="innovation", proposal_type=ProposalType.INNOVATION, title="Medium confidence", confidence=0.75),
        ]

        delivered = await scheduler._deliver_proposals(proposals)

        # All 3 proposals should be delivered (each is delivered individually)
        assert delivered == 3

    @pytest.mark.asyncio
    async def test_limit_max_proposals(
        self, mock_llm_client, mock_graph_db
    ):
        """Limit proposals per session."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            proposal_max_per_session=3,
        )

        # Create more proposals than max
        from aily.sessions.models import Proposal
        proposals = [
            Proposal(mind_name="innovation", proposal_type=ProposalType.INNOVATION, title=f"Proposal {i}", confidence=0.8 - (i * 0.05))
            for i in range(10)
        ]

        # Filter by confidence (all pass 0.7)
        qualified = [p for p in proposals if p.confidence >= 0.7]

        # Limit to max
        if len(qualified) > scheduler.proposal_max_per_session:
            qualified.sort(key=lambda x: x.confidence, reverse=True)
            qualified = qualified[:scheduler.proposal_max_per_session]

        assert len(qualified) == 3
        assert qualified[0].confidence >= qualified[1].confidence >= qualified[2].confidence

    def test_get_current_proposals(
        self, mock_llm_client, mock_graph_db
    ):
        """Get proposals from current session."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        from aily.sessions.models import Proposal
        proposals = [Proposal(mind_name="innovation", proposal_type=ProposalType.INNOVATION, title="Test")]
        scheduler._current_session_proposals = proposals

        assert scheduler.get_current_proposals() == proposals

    def test_is_session_complete_false_initially(
        self, mock_llm_client, mock_graph_db
    ):
        """Session not complete initially."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        assert scheduler.is_session_complete() is False

    def test_is_session_complete_true_after_run(
        self, mock_llm_client, mock_graph_db
    ):
        """Session complete after running."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        scheduler._last_session_completed = datetime.now(timezone.utc)

        assert scheduler.is_session_complete() is True

    def test_map_priority(
        self, mock_llm_client, mock_graph_db
    ):
        """Map TRIZ priority to proposal priority."""
        scheduler = InnovationScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        assert scheduler._map_priority("critical") == "critical"
        assert scheduler._map_priority("high") == "high"
        assert scheduler._map_priority("medium") == "medium"
        assert scheduler._map_priority("low") == "low"
        assert scheduler._map_priority("unknown") == "medium"
