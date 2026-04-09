"""Tests for session models (Proposal, SessionState, etc.)."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from aily.sessions.models import (
    ProposalType,
    ProposalStatus,
    Proposal,
    DikiwiStageMetrics,
    DikiwiPipelineMetrics,
    SessionState,
)


class TestProposalType:
    """Tests for ProposalType enum."""

    def test_enum_values(self):
        """Proposal types are distinct."""
        assert ProposalType.INNOVATION != ProposalType.BUSINESS
        assert ProposalType.INNOVATION != ProposalType.SYNTHESIS
        assert ProposalType.BUSINESS != ProposalType.SYNTHESIS


class TestProposalStatus:
    """Tests for ProposalStatus enum."""

    def test_enum_values(self):
        """Statuses are distinct."""
        assert ProposalStatus.PENDING != ProposalStatus.DELIVERED
        assert ProposalStatus.DELIVERED != ProposalStatus.ARCHIVED
        assert ProposalStatus.ARCHIVED != ProposalStatus.REJECTED


class TestProposal:
    """Tests for Proposal dataclass."""

    def test_init_defaults(self):
        """Proposal initializes with correct defaults."""
        proposal = Proposal()

        assert proposal.mind_name == ""
        assert proposal.proposal_type == ProposalType.INNOVATION
        assert proposal.confidence == 0.0
        assert proposal.priority == "medium"
        # 0.0 confidence auto-rejects
        assert proposal.status == ProposalStatus.REJECTED

    def test_init_custom(self):
        """Proposal accepts custom values."""
        proposal = Proposal(
            mind_name="innovation",
            proposal_type=ProposalType.BUSINESS,
            title="Test Proposal",
            content="This is the content",
            summary="Short summary",
            confidence=0.85,
            priority="high",
            framework_used="TRIZ",
        )

        assert proposal.mind_name == "innovation"
        assert proposal.proposal_type == ProposalType.BUSINESS
        assert proposal.title == "Test Proposal"
        assert proposal.confidence == 0.85
        assert proposal.priority == "high"

    def test_confidence_clamped_high(self):
        """Confidence is clamped to max 1.0."""
        proposal = Proposal(confidence=1.5)
        assert proposal.confidence == 1.0

    def test_confidence_clamped_low(self):
        """Confidence is clamped to min 0.0."""
        proposal = Proposal(confidence=-0.5)
        assert proposal.confidence == 0.0

    def test_auto_reject_low_confidence(self):
        """Proposals below 0.7 are auto-rejected."""
        proposal = Proposal(confidence=0.5, status=ProposalStatus.PENDING)
        assert proposal.status == ProposalStatus.REJECTED

    def test_no_auto_reject_high_confidence(self):
        """Proposals at 0.7+ are not auto-rejected."""
        proposal = Proposal(confidence=0.7, status=ProposalStatus.PENDING)
        assert proposal.status == ProposalStatus.PENDING

    def test_to_markdown(self):
        """Convert proposal to markdown format."""
        proposal = Proposal(
            mind_name="innovation",
            title="Test Proposal",
            content="Detailed content here",
            summary="Short summary",
            confidence=0.85,
            priority="high",
            framework_used="TRIZ",
            source_knowledge_ids=["node1", "node2"],
            metadata={"key": "value"},
        )

        markdown = proposal.to_markdown()

        assert "# Test Proposal" in markdown
        assert "**Type:** INNOVATION" in markdown
        assert "**Confidence:** 85%" in markdown
        assert "**Priority:** high" in markdown
        assert "**Framework:** TRIZ" in markdown
        assert "## Summary" in markdown
        assert "Short summary" in markdown
        assert "## Details" in markdown
        assert "Detailed content here" in markdown
        assert "## Source Knowledge" in markdown
        assert "[[node1]]" in markdown

    def test_to_markdown_no_sources(self):
        """Convert proposal with no sources."""
        proposal = Proposal(
            title="Test Proposal",
            content="Content",
        )

        markdown = proposal.to_markdown()

        assert "## Source Knowledge" not in markdown

    def test_to_feishu_summary(self):
        """Convert to brief summary for Feishu."""
        proposal = Proposal(
            title="Test Proposal",
            summary="This is important",
            confidence=0.85,
            priority="high",
        )

        summary = proposal.to_feishu_summary()

        assert "Test Proposal" in summary
        assert "This is important" in summary
        assert "85%" in summary
        # Should have emoji based on priority
        assert "🟠" in summary  # High priority emoji

    def test_to_feishu_summary_critical(self):
        """Critical priority uses correct emoji."""
        proposal = Proposal(
            title="Critical",
            confidence=0.9,
            priority="critical",
        )

        summary = proposal.to_feishu_summary()
        assert "🔴" in summary


class TestDikiwiStageMetrics:
    """Tests for DikiwiStageMetrics dataclass."""

    def test_init_defaults(self):
        """Metrics initialize with correct defaults."""
        metrics = DikiwiStageMetrics(stage_name="Knowledge")

        assert metrics.stage_name == "Knowledge"
        assert metrics.items_processed == 0
        assert metrics.items_promoted == 0
        assert metrics.average_processing_time_ms == 0.0
        assert metrics.errors == 0

    def test_init_custom(self):
        """Metrics accept custom values."""
        metrics = DikiwiStageMetrics(
            stage_name="Insight",
            items_processed=10,
            items_promoted=5,
            average_processing_time_ms=150.5,
            errors=1,
        )

        assert metrics.items_processed == 10
        assert metrics.items_promoted == 5
        assert metrics.average_processing_time_ms == 150.5


class TestDikiwiPipelineMetrics:
    """Tests for DikiwiPipelineMetrics dataclass."""

    def test_total_time_calculation(self):
        """Calculate total pipeline time."""
        metrics = DikiwiPipelineMetrics(input_id="test_123")
        metrics.completed_at = datetime.now(timezone.utc)
        # started_at is set to now() by default, so time should be near zero

        # Should have some time elapsed
        assert metrics.total_time_ms >= 0

    def test_total_time_incomplete(self):
        """Return 0 when pipeline not complete."""
        metrics = DikiwiPipelineMetrics(input_id="test_123")
        # completed_at is None by default

        assert metrics.total_time_ms == 0.0


class TestSessionState:
    """Tests for SessionState dataclass."""

    def test_init_defaults(self):
        """State initializes with correct defaults."""
        state = SessionState(session_id="sess_123", mind_name="innovation")

        assert state.session_id == "sess_123"
        assert state.mind_name == "innovation"
        assert state.events == []

    def test_log_event(self):
        """Log events to session state."""
        state = SessionState(session_id="sess_123", mind_name="innovation")

        state.log_event("start", {"phase": "init"})
        state.log_event("complete", {"proposals": 5})

        assert len(state.events) == 2
        assert state.events[0]["type"] == "start"
        assert state.events[0]["data"]["phase"] == "init"
        assert state.events[1]["type"] == "complete"

    def test_to_replay_log(self):
        """Export session as replay log."""
        state = SessionState(session_id="sess_123", mind_name="innovation")
        state.log_event("start", {"phase": "init"})

        log = state.to_replay_log()

        assert log["session_id"] == "sess_123"
        assert log["mind_name"] == "innovation"
        assert log["event_count"] == 1
        assert len(log["events"]) == 1

    def test_proposal_id_generation(self):
        """Proposals get unique IDs."""
        import time
        proposal1 = Proposal(title="First")
        time.sleep(0.05)  # 50ms delay to ensure different timestamp/id
        proposal2 = Proposal(title="Second")

        assert proposal1.id != proposal2.id
        assert proposal1.id.startswith("proposal_")

    def test_proposal_created_at(self):
        """Proposals get creation timestamp."""
        before = datetime.now(timezone.utc)
        proposal = Proposal()
        after = datetime.now(timezone.utc)

        assert before <= proposal.created_at <= after
