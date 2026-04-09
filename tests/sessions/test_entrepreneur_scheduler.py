"""Tests for EntrepreneurScheduler - GStack-based business evaluation."""

from __future__ import annotations

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aily.sessions.entrepreneur_scheduler import EntrepreneurScheduler
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
    writer.write_note = AsyncMock(return_value="Aily/Proposals/Business/test.md")
    return writer


@pytest.fixture
def mock_feishu_pusher():
    """Create a mock FeishuPusher."""
    pusher = AsyncMock()
    pusher.send_message = AsyncMock(return_value=None)
    return pusher


@pytest.fixture
def mock_innovation_scheduler():
    """Create a mock InnovationScheduler."""
    scheduler = MagicMock()
    scheduler.is_session_complete = MagicMock(return_value=True)
    scheduler.get_current_proposals = MagicMock(return_value=[])
    return scheduler


@pytest.fixture
def mock_gstack_analyzer():
    """Create a mock GStackAnalyzer."""
    analyzer = AsyncMock()
    result = MagicMock()
    result.insights = ["Strong PMF signals detected"]
    result.raw_analysis = {
        "pmf_analysis": {"pmf_score": 85},
        "shipping_assessment": {"velocity_score": "high"},
        "growth_loops": [
            {"loop_type": "viral", "strength": "strong", "description": "User invites"}
        ]
    }
    result.confidence = 0.88
    result.priority = MagicMock()
    result.priority.value = "high"
    analyzer.analyze = AsyncMock(return_value=result)
    return analyzer


class TestEntrepreneurScheduler:
    """Tests for EntrepreneurScheduler class."""

    def test_init(
        self, mock_llm_client, mock_graph_db, mock_innovation_scheduler
    ):
        """Scheduler initializes with correct defaults."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            innovation_scheduler=mock_innovation_scheduler,
        )

        assert scheduler.mind_name == "entrepreneur"
        assert scheduler.schedule_hour == 9
        assert scheduler.schedule_minute == 0
        assert scheduler.proposal_min_confidence == 0.7
        assert scheduler.proposal_max_per_session == 10
        assert scheduler.innovation_timeout_minutes == 30

    def test_init_custom_values(
        self, mock_llm_client, mock_graph_db
    ):
        """Scheduler accepts custom configuration."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            schedule_hour=11,
            schedule_minute=30,
            proposal_min_confidence=0.75,
            proposal_max_per_session=5,
            innovation_timeout_minutes=15,
        )

        assert scheduler.schedule_hour == 11
        assert scheduler.schedule_minute == 30
        assert scheduler.proposal_min_confidence == 0.75
        assert scheduler.proposal_max_per_session == 5
        assert scheduler.innovation_timeout_minutes == 15

    @pytest.mark.asyncio
    async def test_wait_for_innovation_success(
        self, mock_llm_client, mock_graph_db, mock_innovation_scheduler
    ):
        """Wait for innovation and succeed immediately."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            innovation_scheduler=mock_innovation_scheduler,
        )

        result = await scheduler._wait_for_innovation()

        assert result is True
        mock_innovation_scheduler.is_session_complete.assert_called()

    @pytest.mark.asyncio
    async def test_wait_for_innovation_timeout(
        self, mock_llm_client, mock_graph_db
    ):
        """Timeout when innovation doesn't complete."""
        mock_innovation = MagicMock()
        mock_innovation.is_session_complete = MagicMock(return_value=False)

        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            innovation_scheduler=mock_innovation,
            innovation_timeout_minutes=0,  # Immediate timeout for test
        )

        result = await scheduler._wait_for_innovation()

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_innovation_no_scheduler(
        self, mock_llm_client, mock_graph_db
    ):
        """Return False when no innovation scheduler available."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            innovation_scheduler=None,
        )

        result = await scheduler._wait_for_innovation()

        assert result is False

    @pytest.mark.asyncio
    async def test_query_recent_knowledge(
        self, mock_llm_client, mock_graph_db
    ):
        """Query knowledge from last 24 hours."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        mock_graph_db.execute_query = AsyncMock(return_value=[
            {"id": "node1", "type": "atomic_note", "label": "Business idea", "source": "url1", "created_at": "2024-01-01T00:00:00Z"},
        ])

        knowledge = await scheduler._query_recent_knowledge()

        assert len(knowledge) == 1
        assert knowledge[0]["label"] == "Business idea"

    @pytest.mark.asyncio
    async def test_generate_proposals_weak_pmf(
        self, mock_llm_client, mock_graph_db
    ):
        """Generate PMF alert proposal when PMF is weak."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        gstack_results = {
            "pmf_score": 45,
            "pmf_analysis": {"contradicting_signals": ["Low retention", "High churn"]},
            "shipping_velocity": "low",
            "growth_loops": [],
            "insights": [],
            "confidence": 0.8,
        }
        knowledge = [{"id": "node1"}]

        proposals = await scheduler._generate_proposals(gstack_results, knowledge, [])

        pmf_proposals = [p for p in proposals if "PMF Alert" in p.title]
        assert len(pmf_proposals) == 1
        # PMF < 40 is high priority, 40-60 is medium
        assert pmf_proposals[0].priority in ("high", "medium")

    @pytest.mark.asyncio
    async def test_generate_proposals_strong_pmf(
        self, mock_llm_client, mock_graph_db
    ):
        """Generate double-down proposal when PMF is strong."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        gstack_results = {
            "pmf_score": 85,
            "pmf_analysis": {"supporting_signals": ["High retention", "Word of mouth"]},
            "shipping_velocity": "high",
            "growth_loops": [],
            "insights": [],
            "confidence": 0.9,
        }
        knowledge = [{"id": "node1"}]

        proposals = await scheduler._generate_proposals(gstack_results, knowledge, [])

        pmf_proposals = [p for p in proposals if "PMF Strong" in p.title]
        assert len(pmf_proposals) == 1
        assert pmf_proposals[0].confidence >= 0.85

    @pytest.mark.asyncio
    async def test_generate_proposals_from_growth_loops(
        self, mock_llm_client, mock_graph_db
    ):
        """Generate proposals from growth loops."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        gstack_results = {
            "pmf_score": 70,
            "growth_loops": [
                {"loop_type": "viral", "strength": "strong", "description": "User invites", "activation_points": ["Onboarding", "Success moment"]},
                {"loop_type": "content", "strength": "medium", "description": "SEO content", "activation_points": ["Publishing"]},
            ],
            "insights": [],
            "confidence": 0.8,
        }
        knowledge = [{"id": "node1"}]

        proposals = await scheduler._generate_proposals(gstack_results, knowledge, [])

        growth_proposals = [p for p in proposals if "Growth Loop" in p.title]
        assert len(growth_proposals) == 2
        # Strong loop should be high priority
        viral_proposal = [p for p in growth_proposals if "Viral" in p.title][0]
        assert viral_proposal.priority == "high"

    @pytest.mark.asyncio
    async def test_generate_proposals_from_insights(
        self, mock_llm_client, mock_graph_db
    ):
        """Generate proposals from general insights."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        gstack_results = {
            "pmf_score": 65,
            "growth_loops": [],
            "insights": ["Market timing is favorable for this segment"],
            "confidence": 0.75,
            "priority": "high",
        }
        knowledge = [{"id": "node1"}]

        proposals = await scheduler._generate_proposals(gstack_results, knowledge, [])

        insight_proposals = [p for p in proposals if "Business Insight" in p.title]
        assert len(insight_proposals) == 1

    def test_map_strength_to_confidence(
        self, mock_llm_client, mock_graph_db
    ):
        """Map growth loop strength to confidence."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        assert scheduler._map_strength_to_confidence("strong") == 0.85
        assert scheduler._map_strength_to_confidence("medium") == 0.65
        assert scheduler._map_strength_to_confidence("weak") == 0.45
        assert scheduler._map_strength_to_confidence("potential") == 0.55
        assert scheduler._map_strength_to_confidence("unknown") == 0.5

    def test_format_pmf_proposal_weak(
        self, mock_llm_client, mock_graph_db
    ):
        """Format weak PMF proposal correctly."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        gstack_results = {
            "pmf_score": 40,
            "pmf_analysis": {
                "contradicting_signals": ["Low engagement", "High churn"],
            },
        }

        content = scheduler._format_pmf_proposal(gstack_results, weak=True)

        assert "PMF Score" in content
        assert "Warning Signals" in content
        assert "Talk to users immediately" in content

    def test_format_pmf_proposal_strong(
        self, mock_llm_client, mock_graph_db
    ):
        """Format strong PMF proposal correctly."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        gstack_results = {
            "pmf_score": 90,
            "pmf_analysis": {
                "supporting_signals": ["High retention", "Organic growth"],
            },
        }

        content = scheduler._format_pmf_proposal(gstack_results, weak=False)

        assert "PMF Score" in content
        assert "Positive Signals" in content
        assert "Double down" in content

    def test_format_growth_loop_proposal(
        self, mock_llm_client, mock_graph_db
    ):
        """Format growth loop proposal correctly."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        loop = {
            "loop_type": "viral",
            "strength": "strong",
            "description": "Users invite teammates",
            "activation_points": ["Onboarding", "Project completion"],
        }

        content = scheduler._format_growth_loop_proposal(loop)

        assert "Viral" in content
        assert "Strong" in content
        assert "Users invite teammates" in content
        assert "Action Items" in content

    def test_format_feishu_summary(
        self, mock_llm_client, mock_graph_db
    ):
        """Format Feishu summary correctly."""
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        from aily.sessions.models import Proposal
        proposals = [
            Proposal(mind_name="entrepreneur", proposal_type=ProposalType.BUSINESS, title="PMF Strong", confidence=0.9, priority="high", summary="Great PMF"),
            Proposal(mind_name="entrepreneur", proposal_type=ProposalType.BUSINESS, title="Growth Loop", confidence=0.8, priority="medium", summary="Viral potential"),
        ]

        summary = scheduler._format_feishu_summary(proposals)

        assert "Entrepreneur Mind" in summary
        assert "2 business proposals" in summary
        assert "PMF Strong" in summary
        assert "90%" in summary
