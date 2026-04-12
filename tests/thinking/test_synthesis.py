"""Tests for the synthesis engine.

These tests verify the synthesis engine's adaptive behavior for 1-3 frameworks,
conflict resolution, and pattern matching functionality.
"""

import pytest
from aily.thinking.models import (
    FrameworkInsight,
    FrameworkType,
    InsightPriority,
    KnowledgePayload,
    SynthesizedInsight,
)
from aily.thinking.synthesis import (
    Conflict,
    Pattern,
    SynthesisEngine,
    calculate_cross_framework_confidence,
    detect_conflicts,
    find_reinforcing_patterns,
    resolve_conflicts,
)


class TestConflictDetection:
    """Tests for conflict detection functionality."""

    def test_detect_no_conflicts_single_insight(self):
        """No conflicts with a single insight."""
        insights = [
            SynthesizedInsight(
                title="Test Insight",
                description="This is a test insight",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            )
        ]
        conflicts = detect_conflicts(insights)
        assert len(conflicts) == 0

    def test_detect_semantic_contradiction(self):
        """Detect semantic contradictions between insights."""
        insights = [
            SynthesizedInsight(
                title="Increase Investment",
                description="We should increase investment in this area",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
            SynthesizedInsight(
                title="Decrease Investment",
                description="We should decrease investment to save costs",
                supporting_frameworks=[FrameworkType.MCKINSEY],
                confidence=0.7,
                priority=InsightPriority.HIGH,
            ),
        ]
        conflicts = detect_conflicts(insights)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "semantic_contradiction"
        assert "increase" in conflicts[0].description.lower()
        assert "decrease" in conflicts[0].description.lower()

    def test_detect_action_conflict(self):
        """Detect conflicting action items."""
        insights = [
            SynthesizedInsight(
                title="Build Feature",
                description="Build the new feature",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.8,
                priority=InsightPriority.HIGH,
                action_items=["Build the feature immediately"],
            ),
            SynthesizedInsight(
                title="Kill Feature",
                description="Kill the feature to save resources",
                supporting_frameworks=[FrameworkType.GSTACK],
                confidence=0.7,
                priority=InsightPriority.HIGH,
                action_items=["Kill the feature project"],
            ),
        ]
        conflicts = detect_conflicts(insights)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "action_conflict"

    def test_no_conflict_same_framework(self):
        """Insights from same framework don't conflict with each other."""
        insights = [
            SynthesizedInsight(
                title="Insight A",
                description="Increase speed",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
            SynthesizedInsight(
                title="Insight B",
                description="Decrease cost",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.7,
                priority=InsightPriority.HIGH,
            ),
        ]
        conflicts = detect_conflicts(insights)
        # Same framework, so no cross-framework conflict detected
        assert len(conflicts) == 0


class TestConflictResolution:
    """Tests for conflict resolution strategies."""

    def test_resolve_by_higher_confidence(self):
        """Higher confidence insight wins."""
        insights = [
            SynthesizedInsight(
                title="High Confidence",
                description="This is the better insight",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.9,
                priority=InsightPriority.HIGH,
            ),
            SynthesizedInsight(
                title="Low Confidence",
                description="This is the weaker insight",
                supporting_frameworks=[FrameworkType.MCKINSEY],
                confidence=0.5,
                priority=InsightPriority.HIGH,
            ),
        ]
        conflicts = [
            Conflict(
                insight_a="High Confidence",
                insight_b="Low Confidence",
                conflict_type="test",
                description="Test conflict",
                severity=0.6,
            )
        ]

        resolved = resolve_conflicts(insights, conflicts, "higher_confidence")

        # Higher confidence insight should remain
        high_conf = next(i for i in resolved if i.title == "High Confidence")
        assert high_conf.confidence == 0.9

        # Lower confidence insight should be penalized
        low_conf = next(i for i in resolved if i.title == "Low Confidence")
        assert low_conf.confidence == 0.25  # 0.5 * 0.5
        assert low_conf.priority == InsightPriority.LOW

    def test_resolve_by_synthesis(self):
        """Synthesize both perspectives."""
        insights = [
            SynthesizedInsight(
                title="Perspective A",
                description="Focus on technical excellence",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
            SynthesizedInsight(
                title="Perspective B",
                description="Focus on market speed",
                supporting_frameworks=[FrameworkType.GSTACK],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
        ]
        conflicts = [
            Conflict(
                insight_a="Perspective A",
                insight_b="Perspective B",
                conflict_type="test",
                description="Different focuses",
                severity=0.5,
            )
        ]

        resolved = resolve_conflicts(insights, conflicts, "synthesize")

        # Should have one merged insight
        assert len(resolved) == 1
        assert "Perspective A" in resolved[0].title
        assert "Perspective B" in resolved[0].title
        assert FrameworkType.TRIZ in resolved[0].supporting_frameworks
        assert FrameworkType.GSTACK in resolved[0].supporting_frameworks

    def test_resolve_by_flagging(self):
        """Flag conflicts for human review."""
        insights = [
            SynthesizedInsight(
                title="Critical Decision",
                description="Make a big investment",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
            SynthesizedInsight(
                title="Opposite Decision",
                description="Cut all investment",
                supporting_frameworks=[FrameworkType.MCKINSEY],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
        ]
        conflicts = [
            Conflict(
                insight_a="Critical Decision",
                insight_b="Opposite Decision",
                conflict_type="test",
                description="Severe conflict",
                severity=0.9,
            )
        ]

        resolved = resolve_conflicts(insights, conflicts, "flag_for_review")

        # Both insights should be flagged
        flagged = [i for i in resolved if i.title.startswith("[REVIEW]")]
        assert len(flagged) == 1

        # At least one should have CRITICAL priority
        critical = [i for i in resolved if i.priority == InsightPriority.CRITICAL]
        assert len(critical) >= 1


class TestPatternMatching:
    """Tests for pattern matching functionality."""

    def test_find_convergent_pattern(self):
        """Detect when multiple frameworks agree (requires 2+ insights)."""
        insights = [
            SynthesizedInsight(
                title="Agreed Insight A",
                description="All frameworks support this",
                supporting_frameworks=[FrameworkType.TRIZ, FrameworkType.MCKINSEY],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
            SynthesizedInsight(
                title="Agreed Insight B",
                description="All frameworks also support this",
                supporting_frameworks=[FrameworkType.TRIZ, FrameworkType.GSTACK],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
        ]
        patterns = find_reinforcing_patterns(insights)

        convergent = [p for p in patterns if p.pattern_type == "convergent"]
        assert len(convergent) == 2  # Both insights have 2+ frameworks
        assert all(len(p.frameworks) >= 2 for p in convergent)
        assert all(p.confidence_boost > 0 for p in convergent)

    def test_find_complementary_pattern(self):
        """Detect complementary aspects."""
        insights = [
            SynthesizedInsight(
                title="Strategy",
                description="Focus on strategic planning",
                supporting_frameworks=[FrameworkType.MCKINSEY],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
            SynthesizedInsight(
                title="Execution",
                description="Focus on shipping fast",
                supporting_frameworks=[FrameworkType.GSTACK],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
        ]
        patterns = find_reinforcing_patterns(insights)

        complementary = [p for p in patterns if p.pattern_type == "complementary"]
        assert len(complementary) == 1
        assert "complementary" in complementary[0].description.lower()

    def test_no_patterns_single_insight(self):
        """No patterns with single insight."""
        insights = [
            SynthesizedInsight(
                title="Single Insight",
                description="Only one insight",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
        ]
        patterns = find_reinforcing_patterns(insights)
        assert len(patterns) == 0


class TestSynthesisEngine:
    """Tests for the SynthesisEngine class."""

    @pytest.mark.asyncio
    async def test_single_framework_pass_through(self):
        """Single framework: pass-through with normalization."""
        engine = SynthesisEngine()
        payload = KnowledgePayload(content="Test content")

        framework_insights = [
            FrameworkInsight(
                framework_type=FrameworkType.TRIZ,
                insights=["Insight 1", "Insight 2"],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            )
        ]

        result = await engine.synthesize(payload, framework_insights)

        assert len(result) == 2
        assert all(isinstance(r, SynthesizedInsight) for r in result)
        assert all(r.supporting_frameworks == [FrameworkType.TRIZ] for r in result)

    @pytest.mark.asyncio
    async def test_two_frameworks_cross_validation(self):
        """Two frameworks: cross-validation."""
        engine = SynthesisEngine()
        payload = KnowledgePayload(content="Test content")

        framework_insights = [
            FrameworkInsight(
                framework_type=FrameworkType.TRIZ,
                insights=["Focus on innovation"],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
            FrameworkInsight(
                framework_type=FrameworkType.GSTACK,
                insights=["Focus on product market fit"],
                confidence=0.7,
                priority=InsightPriority.HIGH,
            ),
        ]

        result = await engine.synthesize(payload, framework_insights)

        assert len(result) > 0
        assert all(isinstance(r, SynthesizedInsight) for r in result)

    @pytest.mark.asyncio
    async def test_three_frameworks_full_synthesis(self):
        """Three frameworks: full synthesis with pattern matching."""
        engine = SynthesisEngine()
        payload = KnowledgePayload(content="Test content")

        framework_insights = [
            FrameworkInsight(
                framework_type=FrameworkType.TRIZ,
                insights=["Technical innovation needed"],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
            FrameworkInsight(
                framework_type=FrameworkType.MCKINSEY,
                insights=["Strategic restructuring required"],
                confidence=0.75,
                priority=InsightPriority.HIGH,
            ),
            FrameworkInsight(
                framework_type=FrameworkType.GSTACK,
                insights=["Ship faster to validate"],
                confidence=0.7,
                priority=InsightPriority.MEDIUM,
            ),
        ]

        result = await engine.synthesize(payload, framework_insights)

        assert len(result) > 0
        assert all(isinstance(r, SynthesizedInsight) for r in result)

    @pytest.mark.asyncio
    async def test_empty_framework_insights(self):
        """Handle empty framework insights."""
        engine = SynthesisEngine()
        payload = KnowledgePayload(content="Test content")

        result = await engine.synthesize(payload, [])

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_confidence_threshold_filtering(self):
        """Filter insights below confidence threshold."""
        engine = SynthesisEngine(config={"min_confidence": 0.7})
        payload = KnowledgePayload(content="Test content")

        framework_insights = [
            FrameworkInsight(
                framework_type=FrameworkType.TRIZ,
                insights=["High confidence insight"],
                confidence=0.8,
                priority=InsightPriority.HIGH,
            ),
            FrameworkInsight(
                framework_type=FrameworkType.MCKINSEY,
                insights=["Low confidence insight"],
                confidence=0.5,
                priority=InsightPriority.LOW,
            ),
        ]

        result = await engine.synthesize(payload, framework_insights)

        # Only high confidence insights should remain
        assert all(r.confidence >= 0.7 for r in result)

    def test_rank_insights(self):
        """Insights ranked by priority and confidence."""
        engine = SynthesisEngine()

        insights = [
            SynthesizedInsight(
                title="Low Priority",
                description="Low",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.9,
                priority=InsightPriority.LOW,
            ),
            SynthesizedInsight(
                title="High Priority Low Confidence",
                description="High",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.6,
                priority=InsightPriority.HIGH,
            ),
            SynthesizedInsight(
                title="High Priority High Confidence",
                description="High",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.9,
                priority=InsightPriority.HIGH,
            ),
        ]

        ranked = engine._rank_insights(insights)

        # Highest priority + highest confidence should be first
        assert ranked[0].title == "High Priority High Confidence"
        # Same priority, higher confidence first
        assert ranked[1].title == "High Priority Low Confidence"
        # Lowest priority last
        assert ranked[2].title == "Low Priority"

    def test_get_top_insights(self):
        """Get top N insights."""
        engine = SynthesisEngine()

        insights = [
            SynthesizedInsight(
                title=f"Insight {i}",
                description=f"Description {i}",
                supporting_frameworks=[FrameworkType.TRIZ],
                confidence=0.5 + (i * 0.1),
                priority=InsightPriority.HIGH if i < 3 else InsightPriority.LOW,
            )
            for i in range(5)
        ]

        top = engine.get_top_insights(insights, count=3)

        assert len(top) == 3


class TestCrossFrameworkConfidence:
    """Tests for cross-framework confidence calculation."""

    def test_single_framework_no_boost(self):
        """Single framework gets minimal boost."""
        framework_insights = [
            FrameworkInsight(
                framework_type=FrameworkType.TRIZ,
                insights=["Test"],
                confidence=0.7,
                priority=InsightPriority.MEDIUM,
            )
        ]
        synthesized = SynthesizedInsight(
            title="Test",
            description="Test",
            supporting_frameworks=[FrameworkType.TRIZ],
            confidence=0.7,
            priority=InsightPriority.MEDIUM,
        )

        result = calculate_cross_framework_confidence(framework_insights, synthesized)

        # Single framework: weighted average of base (0.5), no boost (0.3*0), source (0.2*0.7)
        # = 0.35 + 0 + 0.14 = 0.49
        assert 0.4 < result < 0.6

    def test_multiple_frameworks_boost(self):
        """Multiple frameworks get confidence boost."""
        framework_insights = [
            FrameworkInsight(
                framework_type=FrameworkType.TRIZ,
                insights=["Test"],
                confidence=0.8,
                priority=InsightPriority.MEDIUM,
            ),
            FrameworkInsight(
                framework_type=FrameworkType.MCKINSEY,
                insights=["Test"],
                confidence=0.8,
                priority=InsightPriority.MEDIUM,
            ),
        ]
        synthesized = SynthesizedInsight(
            title="Test",
            description="Test",
            supporting_frameworks=[FrameworkType.TRIZ, FrameworkType.MCKINSEY],
            confidence=0.8,
            priority=InsightPriority.MEDIUM,
        )

        result = calculate_cross_framework_confidence(framework_insights, synthesized)

        # Multi-framework: weighted average of base (0.5*0.8), boost (0.3*0.15), source (0.2*0.8)
        # = 0.40 + 0.045 + 0.16 = 0.605
        # With 2 frameworks, should be higher than single framework case
        assert result > 0.5
        assert result <= 1.0


class TestDataClasses:
    """Tests for Conflict and Pattern dataclasses."""

    def test_conflict_creation(self):
        """Conflict dataclass can be created."""
        conflict = Conflict(
            insight_a="Insight A",
            insight_b="Insight B",
            conflict_type="semantic_contradiction",
            description="These insights contradict",
            severity=0.7,
        )

        assert conflict.insight_a == "Insight A"
        assert conflict.insight_b == "Insight B"
        assert conflict.severity == 0.7

    def test_pattern_creation(self):
        """Pattern dataclass can be created."""
        pattern = Pattern(
            pattern_type="convergent",
            description="All frameworks agree",
            frameworks=[FrameworkType.TRIZ, FrameworkType.MCKINSEY],
            confidence_boost=0.15,
            related_insights=["Insight 1"],
        )

        assert pattern.pattern_type == "convergent"
        assert len(pattern.frameworks) == 2
        assert pattern.confidence_boost == 0.15
