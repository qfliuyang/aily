"""Unit tests for framework analyzers (TRIZ, McKinsey, GStack).

These tests verify each analyzer works correctly with mock LLM clients.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from aily.thinking.frameworks.triz import TrizAnalyzer
from aily.thinking.frameworks.mckinsey import McKinseyAnalyzer
from aily.thinking.frameworks.gstack import GStackAnalyzer
from aily.thinking.models import (
    FrameworkType,
    InsightPriority,
    KnowledgePayload,
)


class MockLLMClient:
    """Mock LLM client for testing analyzers."""

    def __init__(self, response=None):
        self.response = response or {"key_insights": ["Test insight"]}
        self.chat = AsyncMock(return_value=self.response)
        self.chat_json = AsyncMock(return_value=self.response)
        self.achat = AsyncMock(return_value=self.response)


class TestTrizAnalyzer:
    """Tests for TRIZ analyzer."""

    @pytest.fixture
    def mock_llm(self):
        return MockLLMClient({
            "key_insights": ["Contradiction found", "Use principle 1"],
            "confidence": 0.8,
            "priority": "high",
            "recommendations": ["Apply separation principle"],
            "action_items": ["Analyze technical contradiction"],
        })

    @pytest.mark.asyncio
    async def test_triz_analyzer_initialization(self, mock_llm):
        """TRIZ analyzer initializes correctly."""
        analyzer = TrizAnalyzer(mock_llm)
        assert analyzer.framework_type == FrameworkType.TRIZ
        assert analyzer.llm_client == mock_llm

    @pytest.mark.asyncio
    async def test_triz_analyze_returns_result(self, mock_llm):
        """TRIZ analyze returns FrameworkInsight."""
        analyzer = TrizAnalyzer(mock_llm)
        payload = KnowledgePayload(content="We need faster and cheaper solution")

        result = await analyzer.analyze(payload)

        assert result.framework_type == FrameworkType.TRIZ
        assert len(result.insights) == 2
        assert result.confidence == 0.8
        assert result.priority == InsightPriority.HIGH

    @pytest.mark.asyncio
    async def test_triz_handles_llm_failure(self):
        """TRIZ handles LLM failures gracefully."""
        failing_llm = MockLLMClient()
        failing_llm.chat_json.side_effect = Exception("LLM error")

        analyzer = TrizAnalyzer(failing_llm)
        payload = KnowledgePayload(content="Test content")

        result = await analyzer.analyze(payload)
        assert not result.success if hasattr(result, "success") else True
        assert "LLM error" in result.insights[0]

    @pytest.mark.asyncio
    async def test_triz_empty_response(self, mock_llm):
        """TRIZ handles empty insights list."""
        mock_llm.chat_json.return_value = {
            "key_insights": [],
            "confidence": 0.0,
            "priority": "low",
        }

        analyzer = TrizAnalyzer(mock_llm)
        payload = KnowledgePayload(content="Test")

        result = await analyzer.analyze(payload)

        assert result.insights == []
        assert result.confidence == 0.0


class TestMcKinseyAnalyzer:
    """Tests for McKinsey analyzer."""

    @pytest.fixture
    def mock_llm(self):
        return MockLLMClient({
            "key_insights": ["Critical market opportunity", "Organizational gap"],
            "confidence": 0.85,
            "priority": "critical",
            "recommendations": ["Restructure team", "Enter new market"],
            "action_items": ["Conduct stakeholder interviews"],
        })

    @pytest.mark.asyncio
    async def test_mckinsey_analyzer_initialization(self, mock_llm):
        """McKinsey analyzer initializes correctly."""
        analyzer = McKinseyAnalyzer(mock_llm)
        assert analyzer.framework_type == FrameworkType.MCKINSEY
        assert analyzer.llm_client == mock_llm

    @pytest.mark.asyncio
    async def test_mckinsey_analyze_returns_result(self, mock_llm):
        """McKinsey analyze returns FrameworkInsight."""
        analyzer = McKinseyAnalyzer(mock_llm)
        payload = KnowledgePayload(content="Should we expand to Asia?")

        result = await analyzer.analyze(payload)

        assert result.framework_type == FrameworkType.MCKINSEY
        assert len(result.insights) == 2
        assert result.confidence == 0.85
        assert result.priority == InsightPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_mckinsey_handles_llm_failure(self):
        """McKinsey handles LLM failures gracefully."""
        failing_llm = MockLLMClient()
        failing_llm.chat_json.side_effect = Exception("API timeout")

        analyzer = McKinseyAnalyzer(failing_llm)
        payload = KnowledgePayload(content="Test content")

        result = await analyzer.analyze(payload)
        assert "API timeout" in result.insights[0]

    @pytest.mark.asyncio
    async def test_mckinsey_business_content(self, mock_llm):
        """McKinsey handles business-focused content."""
        analyzer = McKinseyAnalyzer(mock_llm)
        payload = KnowledgePayload(
            content="Our revenue is declining in Q3",
            source_url="https://internal-report.com/q3",
        )

        result = await analyzer.analyze(payload)

        assert result.framework_type == FrameworkType.MCKINSEY
        mock_llm.chat_json.assert_called_once()


class TestGStackAnalyzer:
    """Tests for GStack analyzer."""

    @pytest.fixture
    def mock_llm(self):
        return MockLLMClient({
            "key_insights": ["PMF not achieved", "Shipping velocity too low"],
            "confidence": 0.75,
            "priority": "high",
            "recommendations": ["Focus on core loop", "Reduce scope"],
            "action_items": ["Interview 10 customers", "Ship MVP this week"],
        })

    @pytest.mark.asyncio
    async def test_gstack_analyzer_initialization(self, mock_llm):
        """GStack analyzer initializes correctly."""
        analyzer = GStackAnalyzer(mock_llm)
        assert analyzer.framework_type == FrameworkType.GSTACK
        assert analyzer.llm_client == mock_llm

    @pytest.mark.asyncio
    async def test_gstack_analyze_returns_result(self, mock_llm):
        """GStack analyze returns FrameworkInsight."""
        analyzer = GStackAnalyzer(mock_llm)
        payload = KnowledgePayload(content="Our startup is struggling to grow")

        result = await analyzer.analyze(payload)

        assert result.framework_type == FrameworkType.GSTACK
        assert len(result.insights) == 2
        assert result.confidence == 0.75

    @pytest.mark.asyncio
    async def test_gstack_handles_startup_content(self, mock_llm):
        """GStack handles startup-focused content."""
        analyzer = GStackAnalyzer(mock_llm)
        payload = KnowledgePayload(content="We have 100 users but no revenue")

        result = await analyzer.analyze(payload)

        assert result.framework_type == FrameworkType.GSTACK
        assert result.raw_analysis is not None

    @pytest.mark.asyncio
    async def test_gstack_product_focus(self, mock_llm):
        """GStack focuses on product metrics."""
        analyzer = GStackAnalyzer(mock_llm)
        payload = KnowledgePayload(content="Feature X has low adoption")

        result = await analyzer.analyze(payload)

        assert result.framework_type == FrameworkType.GSTACK
        mock_llm.chat_json.assert_called_once()

    def test_gstack_system_prompt_supports_deeptech_workflows(self, mock_llm):
        analyzer = GStackAnalyzer(mock_llm)

        system_prompt = analyzer.get_system_prompt()

        assert "enterprise and deep-tech markets" in system_prompt
        assert "integration cost" in system_prompt
        assert "signoff trust" in system_prompt


class TestAnalyzerConfiguration:
    """Tests for analyzer configuration options."""

    def test_triz_with_custom_config(self):
        """TRIZ accepts custom configuration."""
        mock_llm = MockLLMClient()
        config = {"custom_param": "value", "timeout": 30}
        analyzer = TrizAnalyzer(mock_llm, config)
        assert analyzer.config == config

    def test_mckinsey_with_custom_config(self):
        """McKinsey accepts custom configuration."""
        mock_llm = MockLLMClient()
        config = {"mece_strictness": "high"}
        analyzer = McKinseyAnalyzer(mock_llm, config)
        assert analyzer.config == config

    def test_gstack_with_custom_config(self):
        """GStack accepts custom configuration."""
        mock_llm = MockLLMClient()
        config = {"pmf_threshold": 40}
        analyzer = GStackAnalyzer(mock_llm, config)
        assert analyzer.config == config

    def test_analyzer_without_config(self):
        """Analyzers work without config."""
        mock_llm = MockLLMClient()
        triz = TrizAnalyzer(mock_llm)
        mckinsey = McKinseyAnalyzer(mock_llm)
        gstack = GStackAnalyzer(mock_llm)

        assert triz.config is None or triz.config == {}
        assert mckinsey.config is None or mckinsey.config == {}
        assert gstack.config is None or gstack.config == {}


class TestAnalyzerConfidence:
    """Tests for analyzer confidence calculation."""

    @pytest.mark.asyncio
    async def test_high_confidence_response(self):
        """High confidence in LLM response."""
        mock_llm = MockLLMClient({
            "key_insights": ["Clear contradiction"],
            "confidence": 0.95,
            "priority": "high",
        })
        analyzer = TrizAnalyzer(mock_llm)
        payload = KnowledgePayload(content="Obvious technical tradeoff")

        result = await analyzer.analyze(payload)
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_low_confidence_response(self):
        """Low confidence for unclear content."""
        mock_llm = MockLLMClient({
            "key_insights": ["Unclear analysis"],
            "confidence": 0.3,
            "priority": "low",
        })
        analyzer = McKinseyAnalyzer(mock_llm)
        payload = KnowledgePayload(content="Vague content")

        result = await analyzer.analyze(payload)
        assert result.confidence == 0.3

    @pytest.mark.asyncio
    async def test_default_confidence(self):
        """Default confidence when not specified."""
        mock_llm = MockLLMClient({
            "key_insights": ["Insight without confidence"],
        })
        analyzer = GStackAnalyzer(mock_llm)
        payload = KnowledgePayload(content="Test")

        result = await analyzer.analyze(payload)
        assert result.confidence == 0.75  # GStack default value


class TestAnalyzerPriority:
    """Tests for analyzer priority handling."""

    @pytest.mark.parametrize("priority_str,expected_priority", [
        ("critical", InsightPriority.CRITICAL),
        ("high", InsightPriority.HIGH),
        ("medium", InsightPriority.MEDIUM),
        ("low", InsightPriority.LOW),
    ])
    @pytest.mark.asyncio
    async def test_priority_parsing(self, priority_str, expected_priority):
        """Priorities are parsed correctly from LLM response."""
        mock_llm = MockLLMClient({
            "key_insights": ["Test"],
            "confidence": 0.8,
            "priority": priority_str,
        })
        analyzer = TrizAnalyzer(mock_llm)
        payload = KnowledgePayload(content="Test")

        result = await analyzer.analyze(payload)
        assert result.priority == expected_priority

    @pytest.mark.asyncio
    async def test_invalid_priority_defaults_to_computed(self):
        """Invalid priority falls back to computed priority."""
        mock_llm = MockLLMClient({
            "key_insights": ["Test"],
            "priority": "invalid_priority",
        })
        analyzer = McKinseyAnalyzer(mock_llm)
        payload = KnowledgePayload(content="Test")

        result = await analyzer.analyze(payload)
        assert result.priority == InsightPriority.LOW
