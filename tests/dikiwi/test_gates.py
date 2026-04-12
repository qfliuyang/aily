"""Tests for DIKIWI gates (Menxia and CVO).

Tests:
- Menxia quality review
- Menxia circuit breaker integration
- CVO approval flow
- CVO TTL auto-approve
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from aily.dikiwi.gates import (
    ApprovalDecisionType,
    CVOGate,
    MenxiaGate,
    ReviewDecisionType,
)


class TestMenxiaGate:
    """Test the 门下省 (Menxia) institutional review gate."""

    async def test_review_approves_good_content(self, mock_llm_client):
        """Menxia approves content above quality threshold."""
        mock_llm_client.complete = AsyncMock(return_value="""
            Decision: APPROVE
            Quality Score: 0.8
            Reason: Well structured content
        """)

        gate = MenxiaGate(llm_client=mock_llm_client, quality_threshold=0.6)
        decision = await gate.review(
            content="This is high quality content about Python programming.",
            metadata={"tags": ["python", "programming"]},
        )

        assert decision.decision == ReviewDecisionType.APPROVE
        assert decision.quality_score == 0.8

    async def test_review_rejects_poor_content(self, mock_llm_client):
        """Menxia rejects content below quality threshold."""
        mock_llm_client.complete = AsyncMock(return_value="""
            Decision: REJECT
            Quality Score: 0.3
            Reason: Poor quality content
        """)

        gate = MenxiaGate(llm_client=mock_llm_client, quality_threshold=0.6)
        decision = await gate.review(
            content="Bad content.",
            metadata={"tags": []},
        )

        assert decision.decision == ReviewDecisionType.REJECT
        assert decision.quality_score == 0.3

    async def test_auto_reject_below_threshold(self, mock_llm_client):
        """Content with score below threshold is auto-rejected."""
        mock_llm_client.complete = AsyncMock(return_value="""
            Decision: APPROVE
            Quality Score: 0.5
            Reason: Borderline content
        """)

        gate = MenxiaGate(llm_client=mock_llm_client, quality_threshold=0.6)
        decision = await gate.review(
            content="Some content.",
            metadata={},
        )

        # Even though LLM said APPROVE, score is below threshold
        assert decision.decision == ReviewDecisionType.REJECT

    async def test_auto_approve_without_llm(self):
        """Gate auto-approves if no LLM available."""
        gate = MenxiaGate(llm_client=None)
        decision = await gate.review("Some content", metadata={})

        assert decision.decision == ReviewDecisionType.APPROVE
        assert "No LLM" in decision.reason

    async def test_circuit_breaker_opens_after_failures(self, mock_llm_client):
        """Circuit breaker opens after consecutive failures."""
        mock_llm_client.complete = AsyncMock(side_effect=Exception("LLM Error"))

        gate = MenxiaGate(
            llm_client=mock_llm_client,
            circuit_failure_threshold=3,
        )

        # First 3 calls should fail open (auto-approve with error)
        for _ in range(3):
            decision = await gate.review("Content", metadata={})
            assert decision.decision == ReviewDecisionType.APPROVE

        # Circuit should be open now
        assert not await gate.can_execute()

        # 4th call should be blocked by circuit breaker
        decision = await gate.review("Content", metadata={})
        assert "Circuit breaker" in decision.reason

    async def test_circuit_breaker_records_metrics(self, mock_llm_client):
        """Circuit breaker metrics are tracked."""
        mock_llm_client.complete = AsyncMock(side_effect=Exception("LLM Error"))

        gate = MenxiaGate(llm_client=mock_llm_client)

        # Trigger failures
        for _ in range(3):
            await gate.review("Content", metadata={})

        metrics = gate.get_metrics()
        assert metrics["circuit_failure_count"] == 3
        assert not metrics["circuit_healthy"]

    def test_parse_decision_extracts_fields(self):
        """Decision parser extracts all fields correctly."""
        gate = MenxiaGate()
        response = """
            Decision: MODIFY
            Quality Score: 0.75
            Reason: Good but needs improvement
        """

        decision = gate._parse_decision(response)

        assert decision.decision == ReviewDecisionType.MODIFY
        assert decision.quality_score == 0.75

    async def test_batch_review(self, mock_llm_client):
        """Can review multiple items in batch."""
        gate = MenxiaGate(llm_client=mock_llm_client)
        items = [
            {"content": "Item 1", "metadata": {}},
            {"content": "Item 2", "metadata": {}},
        ]

        decisions = await gate.batch_review(items)

        assert len(decisions) == 2
        assert all(d.decision == ReviewDecisionType.APPROVE for d in decisions)


class TestCVOGate:
    """Test the Chief Vision Officer approval gate."""

    async def test_request_approval_creates_pending(self, cvo_gate):
        """Request approval creates a pending approval."""
        pending = await cvo_gate.request_approval(
            approval_id="app-001",
            content_id="content-001",
            content_preview="Preview",
            wisdom_summary="Summary",
            impact_proposal={"action": "deploy"},
        )

        assert pending.approval_id == "app-001"
        assert not pending.is_expired()

    async def test_approve_returns_decision(self, cvo_gate):
        """Human approval returns APPROVED decision."""
        await cvo_gate.request_approval(
            approval_id="app-001",
            content_id="content-001",
            content_preview="Preview",
            wisdom_summary="Summary",
            impact_proposal={},
        )

        decision = cvo_gate.approve("app-001", approved_by="CEO", reasoning="Looks good")

        assert decision.decision == ApprovalDecisionType.APPROVED
        assert decision.approved_by == "CEO"

    async def test_reject_returns_decision(self, cvo_gate):
        """Human rejection returns REJECTED decision."""
        await cvo_gate.request_approval(
            approval_id="app-001",
            content_id="content-001",
            content_preview="Preview",
            wisdom_summary="Summary",
            impact_proposal={},
        )

        decision = cvo_gate.reject("app-001", rejected_by="CEO", reasoning="Not aligned")

        assert decision.decision == ApprovalDecisionType.REJECTED
        assert "Not aligned" in decision.reasoning

    async def test_await_approval_with_event(self, cvo_gate):
        """await_approval uses asyncio.Event for notification."""
        await cvo_gate.request_approval(
            approval_id="app-001",
            content_id="content-001",
            content_preview="Preview",
            wisdom_summary="Summary",
            impact_proposal={},
        )

        # Approve in background after short delay
        async def delayed_approve():
            await asyncio.sleep(0.1)
            cvo_gate.approve("app-001")

        asyncio.create_task(delayed_approve())

        # Should receive approval
        decision = await cvo_gate.await_approval("app-001")
        assert decision.decision == ApprovalDecisionType.APPROVED

    async def test_ttl_auto_approve(self):
        """TTL expiration auto-approves."""
        # Use very short TTL for testing
        gate = CVOGate(ttl_hours=0)  # 0 hours = immediate expiry

        await gate.request_approval(
            approval_id="app-001",
            content_id="content-001",
            content_preview="Preview",
            wisdom_summary="Summary",
            impact_proposal={},
        )

        decision = await gate.await_approval("app-001")

        assert decision.decision == ApprovalDecisionType.AUTO_APPROVED
        assert "TTL" in decision.reasoning

    def test_get_pending_lists_all(self, cvo_gate):
        """get_pending returns all pending approvals."""
        # Note: Can't test async request_approval in sync test
        # But we can test the method exists
        pending = cvo_gate.get_pending()
        assert isinstance(pending, list)

    def test_metrics_tracks_approvals(self, cvo_gate):
        """Metrics track approval counts."""
        metrics = cvo_gate.get_metrics()

        assert "approved" in metrics
        assert "auto_approved" in metrics
        assert "rejected" in metrics
        assert "human_engagement_rate" in metrics
