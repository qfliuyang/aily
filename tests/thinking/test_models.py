"""Unit tests for thinking system data models.

Tests validation, creation, and edge cases for all model classes.
"""

import pytest
from datetime import datetime
from aily.thinking.models import (
    FrameworkType,
    InsightPriority,
    KnowledgePayload,
    FrameworkInsight,
    SynthesizedInsight,
    ThinkingResult,
)


class TestFrameworkType:
    """Tests for FrameworkType enum."""

    def test_framework_type_values(self):
        """FrameworkType has expected values."""
        assert FrameworkType.TRIZ.value == "triz"
        assert FrameworkType.MCKINSEY.value == "mckinsey"
        assert FrameworkType.GSTACK.value == "gstack"

    def test_framework_type_comparison(self):
        """FrameworkType can be compared."""
        assert FrameworkType.TRIZ == FrameworkType.TRIZ
        assert FrameworkType.TRIZ != FrameworkType.MCKINSEY


class TestInsightPriority:
    """Tests for InsightPriority enum."""

    def test_priority_values(self):
        """InsightPriority has expected values."""
        assert InsightPriority.LOW.value == 1
        assert InsightPriority.MEDIUM.value == 2
        assert InsightPriority.HIGH.value == 3
        assert InsightPriority.CRITICAL.value == 4

    def test_priority_comparison(self):
        """InsightPriority can be ordered."""
        assert InsightPriority.LOW < InsightPriority.MEDIUM
        assert InsightPriority.MEDIUM < InsightPriority.HIGH
        assert InsightPriority.HIGH < InsightPriority.CRITICAL


class TestKnowledgePayload:
    """Tests for KnowledgePayload model."""

    def test_create_minimal_payload(self):
        """Create payload with only required content."""
        payload = KnowledgePayload(content="Test content")
        assert payload.content == "Test content"
        assert payload.source_url is None
        assert payload.source_title is None
        assert payload.metadata == {}
        assert payload.context_nodes == []
        assert isinstance(payload.timestamp, datetime)

    def test_create_full_payload(self):
        """Create payload with all fields."""
        payload = KnowledgePayload(
            content="Test content",
            source_url="https://example.com",
            source_title="Example Title",
            metadata={"author": "Test"},
            context_nodes=["node1", "node2"],
        )
        assert payload.content == "Test content"
        assert payload.source_url == "https://example.com"
        assert payload.source_title == "Example Title"
        assert payload.metadata == {"author": "Test"}
        assert payload.context_nodes == ["node1", "node2"]

    def test_empty_content_raises(self):
        """Empty content raises validation error."""
        with pytest.raises(ValueError):
            KnowledgePayload(content="")

    def test_content_accessible(self):
        """Content field is accessible."""
        payload = KnowledgePayload(content="Important information")
        assert "Important" in payload.content


class TestFrameworkInsight:
    """Tests for FrameworkInsight model."""

    def test_create_minimal_insight(self):
        """Create insight with required fields."""
        insight = FrameworkInsight(
            framework_type=FrameworkType.TRIZ,
            insights=["Insight 1"],
            confidence=0.5,
        )
        assert insight.framework_type == FrameworkType.TRIZ
        assert insight.insights == ["Insight 1"]
        assert insight.confidence == 0.5
        assert insight.priority == InsightPriority.MEDIUM  # default

    def test_create_full_insight(self):
        """Create insight with all fields."""
        insight = FrameworkInsight(
            framework_type=FrameworkType.MCKINSEY,
            insights=["Insight 1", "Insight 2"],
            confidence=0.85,
            priority=InsightPriority.HIGH,
            key_recommendations=["Rec 1"],
            action_items=["Action 1"],
            processing_time_ms=100,
        )
        assert insight.framework_type == FrameworkType.MCKINSEY
        assert insight.confidence == 0.85
        assert insight.priority == InsightPriority.HIGH
        assert insight.processing_time_ms == 100

    def test_insight_with_empty_list(self):
        """Insight can have empty insights list."""
        insight = FrameworkInsight(
            framework_type=FrameworkType.GSTACK,
            insights=[],
            confidence=0.5,
        )
        assert insight.insights == []

    def test_confidence_bounds(self):
        """Confidence should be between 0 and 1."""
        # These should work (validation may happen elsewhere)
        low = FrameworkInsight(
            framework_type=FrameworkType.TRIZ,
            insights=["Test"],
            confidence=0.0,
        )
        high = FrameworkInsight(
            framework_type=FrameworkType.TRIZ,
            insights=["Test"],
            confidence=1.0,
        )
        assert low.confidence == 0.0
        assert high.confidence == 1.0


class TestSynthesizedInsight:
    """Tests for SynthesizedInsight model."""

    def test_create_minimal_synthesized(self):
        """Create synthesized insight with required fields."""
        insight = SynthesizedInsight(
            title="Test Title",
            description="Test description",
            supporting_frameworks=[FrameworkType.TRIZ],
            confidence=0.8,
            priority=InsightPriority.HIGH,
        )
        assert insight.title == "Test Title"
        assert insight.description == "Test description"
        assert insight.supporting_frameworks == [FrameworkType.TRIZ]
        assert insight.confidence == 0.8

    def test_create_full_synthesized(self):
        """Create synthesized insight with all fields."""
        insight = SynthesizedInsight(
            title="Full Title",
            description="Full description",
            supporting_frameworks=[FrameworkType.TRIZ, FrameworkType.MCKINSEY],
            confidence=0.9,
            priority=InsightPriority.CRITICAL,
            evidence=["Evidence 1", "Evidence 2"],
            contradictions=["Counter view"],
            action_items=["Action 1"],
        )
        assert len(insight.supporting_frameworks) == 2
        assert len(insight.evidence) == 2
        assert len(insight.contradictions) == 1

    def test_multiple_supporting_frameworks(self):
        """Insight can support multiple frameworks."""
        insight = SynthesizedInsight(
            title="Multi-framework",
            description="Supported by all",
            supporting_frameworks=[FrameworkType.TRIZ, FrameworkType.MCKINSEY, FrameworkType.GSTACK],
            confidence=0.95,
            priority=InsightPriority.HIGH,
        )
        assert len(insight.supporting_frameworks) == 3


class TestThinkingResult:
    """Tests for ThinkingResult model."""

    def test_create_minimal_result(self):
        """Create result with required fields."""
        payload = KnowledgePayload(content="Test")
        result = ThinkingResult(
            request_id="req-123",
            payload=payload,
            framework_insights=[],
            synthesized_insights=[],
            top_insights=[],
            confidence_score=0.5,
            processing_metadata={},
        )
        assert result.request_id == "req-123"
        assert result.payload == payload
        assert result.confidence_score == 0.5

    def test_create_full_result(self):
        """Create result with all fields."""
        payload = KnowledgePayload(content="Test content")
        framework_insight = FrameworkInsight(
            framework_type=FrameworkType.TRIZ,
            insights=["Insight 1"],
            confidence=0.8,
        )
        synthesized = SynthesizedInsight(
            title="Synthesized",
            description="Description",
            supporting_frameworks=[FrameworkType.TRIZ],
            confidence=0.8,
            priority=InsightPriority.HIGH,
        )

        result = ThinkingResult(
            request_id="req-456",
            payload=payload,
            framework_insights=[framework_insight],
            synthesized_insights=[synthesized],
            top_insights=[synthesized],
            confidence_score=0.85,
            processing_metadata={"time_ms": 1000},
            formatted_output={"obsidian": "# Content"},
        )
        assert len(result.framework_insights) == 1
        assert len(result.top_insights) == 1
        assert result.formatted_output == {"obsidian": "# Content"}

    def test_result_with_empty_lists(self):
        """Result can have empty insight lists."""
        payload = KnowledgePayload(content="Test")
        result = ThinkingResult(
            request_id="req-789",
            payload=payload,
            framework_insights=[],
            synthesized_insights=[],
            top_insights=[],
            confidence_score=0.0,
            processing_metadata={},
        )
        assert result.framework_insights == []
        assert result.confidence_score == 0.0


class TestModelEdgeCases:
    """Tests for edge cases and error handling."""

    def test_unicode_content(self):
        """Models handle unicode content."""
        payload = KnowledgePayload(content="Unicode: 你好世界 🌍 émojis")
        assert "你好世界" in payload.content

    def test_very_long_content(self):
        """Models handle very long content."""
        long_content = "Word " * 10000
        payload = KnowledgePayload(content=long_content)
        assert len(payload.content) == len(long_content)

    def test_special_characters_in_titles(self):
        """Titles can contain special characters."""
        insight = SynthesizedInsight(
            title='Title with <tags> & "quotes" and \'apostrophes\'',
            description="Description",
            supporting_frameworks=[FrameworkType.TRIZ],
            confidence=0.8,
            priority=InsightPriority.HIGH,
        )
        assert "<tags>" in insight.title

    def test_none_values_in_optional_fields(self):
        """Optional fields can be None."""
        payload = KnowledgePayload(
            content="Test",
            source_url=None,
            source_title=None,
        )
        assert payload.source_url is None
        assert payload.source_title is None

    def test_nested_metadata(self):
        """Metadata can be nested dictionaries."""
        payload = KnowledgePayload(
            content="Test",
            metadata={
                "nested": {"deep": {"value": 123}},
                "list": [1, 2, 3],
            },
        )
        assert payload.metadata["nested"]["deep"]["value"] == 123
