"""Tests for DIKIWI stage state machine and transitions.

Tests the permission matrix and stage transitions:
- Valid transitions
- Invalid transitions (should raise)
- Rejection loops (封驳)
"""

from __future__ import annotations

import pytest

from aily.dikiwi.stages import (
    DikiwiStage,
    StageContext,
    StageState,
    StageStateMachine,
    can_transition,
)


class TestCanTransition:
    """Test the permission matrix for stage transitions."""

    def test_data_to_information(self):
        """DATA can transition to INFORMATION."""
        assert can_transition(DikiwiStage.DATA, DikiwiStage.INFORMATION)

    def test_information_to_knowledge(self):
        """INFORMATION can transition to KNOWLEDGE."""
        assert can_transition(DikiwiStage.INFORMATION, DikiwiStage.KNOWLEDGE)

    def test_knowledge_to_insight(self):
        """KNOWLEDGE can transition to INSIGHT."""
        assert can_transition(DikiwiStage.KNOWLEDGE, DikiwiStage.INSIGHT)

    def test_insight_to_wisdom(self):
        """INSIGHT can transition to WISDOM."""
        assert can_transition(DikiwiStage.INSIGHT, DikiwiStage.WISDOM)

    def test_wisdom_to_impact(self):
        """WISDOM can transition to IMPACT."""
        assert can_transition(DikiwiStage.WISDOM, DikiwiStage.IMPACT)

    def test_rejection_knowledge_to_information(self):
        """KNOWLEDGE can reject back to INFORMATION (封驳)."""
        assert can_transition(DikiwiStage.KNOWLEDGE, DikiwiStage.INFORMATION)

    def test_rejection_wisdom_to_insight(self):
        """WISDOM can reject back to INSIGHT (CVO rejection)."""
        assert can_transition(DikiwiStage.WISDOM, DikiwiStage.INSIGHT)

    def test_invalid_skip_data_to_knowledge(self):
        """DATA cannot skip to KNOWLEDGE."""
        assert not can_transition(DikiwiStage.DATA, DikiwiStage.KNOWLEDGE)

    def test_invalid_skip_information_to_insight(self):
        """INFORMATION cannot skip to INSIGHT."""
        assert not can_transition(DikiwiStage.INFORMATION, DikiwiStage.INSIGHT)

    def test_invalid_impact_is_terminal(self):
        """IMPACT is terminal - no transitions allowed."""
        for stage in DikiwiStage:
            assert not can_transition(DikiwiStage.IMPACT, stage)


class TestStageStateMachine:
    """Test the StageStateMachine class."""

    def test_initial_state(self, stage_context):
        """State machine initializes with correct state."""
        sm = StageStateMachine(stage_context)
        assert sm.current_stage == DikiwiStage.INFORMATION
        assert sm.can_transition_to(DikiwiStage.KNOWLEDGE)

    def test_valid_transition(self, stage_context):
        """Valid transition updates state."""
        sm = StageStateMachine(stage_context)
        sm.transition_to(DikiwiStage.KNOWLEDGE, reason="Menxia approved")

        assert sm.current_stage == DikiwiStage.KNOWLEDGE
        assert stage_context.current_stage == DikiwiStage.KNOWLEDGE
        assert len(stage_context.stage_history) == 1
        assert stage_context.stage_history[0]["to"] == "KNOWLEDGE"

    def test_invalid_transition_raises(self, stage_context):
        """Invalid transition raises ValueError."""
        sm = StageStateMachine(stage_context)

        with pytest.raises(ValueError) as exc_info:
            sm.transition_to(DikiwiStage.INSIGHT)  # Skip KNOWLEDGE

        assert "Invalid transition" in str(exc_info.value)

    def test_rejection_updates_count(self, stage_context):
        """Rejection increments rejection count."""
        stage_context.current_stage = DikiwiStage.KNOWLEDGE
        sm = StageStateMachine(stage_context)

        sm.transition_to(DikiwiStage.INFORMATION, reason="封驳 - quality too low")

        assert stage_context.rejection_count.get("KNOWLEDGE", 0) == 1

    def test_max_rejections_check(self, stage_context):
        """State machine tracks max rejections."""
        stage_context.rejection_count = {"KNOWLEDGE": 3}
        stage_context.current_stage = DikiwiStage.KNOWLEDGE
        sm = StageStateMachine(stage_context, max_rejections=3)

        assert sm.is_max_rejections_reached()

    def test_get_history(self, stage_context):
        """State machine returns history."""
        sm = StageStateMachine(stage_context)
        sm.transition_to(DikiwiStage.KNOWLEDGE, reason="Approved")
        sm.transition_to(DikiwiStage.INSIGHT, reason="Linked")

        history = sm.get_history()
        assert len(history) == 2
        assert history[0]["to"] == "KNOWLEDGE"
        assert history[1]["to"] == "INSIGHT"


class TestStageContext:
    """Test StageContext dataclass."""

    def test_context_creation(self):
        """Can create a stage context."""
        ctx = StageContext(
            context_id="ctx-001",
            correlation_id="corr-001",
            content_id="content-001",
            current_stage=DikiwiStage.DATA,
            stage_state="PENDING",
            stage_history=[],
            rejection_count={},
        )

        assert ctx.context_id == "ctx-001"
        assert ctx.correlation_id == "corr-001"

    def test_to_dict_serialization(self, stage_context):
        """Context can be serialized to dict."""
        data = stage_context.to_dict()

        assert data["context_id"] == stage_context.context_id
        assert data["current_stage"] == "INFORMATION"

    def test_from_dict_deserialization(self, stage_context):
        """Context can be deserialized from dict."""
        data = stage_context.to_dict()
        restored = StageContext.from_dict(data)

        assert restored.context_id == stage_context.context_id
        assert restored.current_stage == stage_context.current_stage
