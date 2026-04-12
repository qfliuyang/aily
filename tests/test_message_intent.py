"""Tests for message intent detection.

Tests the IntentRouter's ability to classify messages correctly,
especially edge cases like Monica share links with analysis keywords in titles.
"""

import pytest

from aily.bot.message_intent import IntentRouter, IntentType, MessageIntent


class TestIntentRouter:
    """Test the IntentRouter classification."""

    def test_simple_chat(self):
        """Simple chat messages are classified as CHAT."""
        result = IntentRouter.analyze("Hello, how are you?")
        assert result.intent_type == IntentType.CHAT
        assert result.url is None

    def test_url_with_thinking_keywords(self):
        """URL with explicit thinking request triggers analysis."""
        result = IntentRouter.analyze("请分析这个链接 https://example.com/article")
        assert result.intent_type == IntentType.THINKING_ANALYSIS
        assert result.url == "https://example.com/article"

    def test_url_without_thinking_keywords(self):
        """URL without thinking keywords is saved only."""
        result = IntentRouter.analyze("Check this out: https://example.com/page")
        assert result.intent_type == IntentType.URL_SAVE
        assert result.url == "https://example.com/page"

    def test_monica_share_link_with_analysis_keywords(self):
        """Monica share links with analysis keywords in title should be URL_SAVE.

        This is a regression test for the issue where Chinese analysis keywords
        like '评估', '分析', '方法论' in Monica share link titles incorrectly
        triggered THINKING_ANALYSIS instead of URL_SAVE.
        """
        test_cases = [
            # Message 8, 9, 10 from the original bug report
            "【评估NVIDIA生成式AI技术用于EDA领域TCL脚本生成的适用性 - Monica AI Chat】https://monica.im/share/chat?shareId=BsA0KcdiGWQo4l09",
            "【PDK 评价体系与工艺线平衡分析 - Monica AI Chat】https://monica.im/share/chat?shareId=nLsKxwTCySW0p6Z3",
            "【芯片signoff规则制定方法论及学习资料 - Monica AI Chat】https://monica.im/share/chat?shareId=4cxQomLr6VD28Ofx",
            # Additional variations
            "【分析某个问题 - Monica AI Chat】https://monica.im/share/chat?shareId=abc123",
            "【深度评估报告 - Monica AI Chat】https://monica.im/share/chat?shareId=def456",
        ]

        for msg in test_cases:
            result = IntentRouter.analyze(msg)
            assert result.intent_type == IntentType.URL_SAVE, \
                f"Expected URL_SAVE for: {msg[:50]}... but got {result.intent_type.name}"
            assert "monica.im/share" in result.url
            assert "分析" in result.reasoning or "Share link" in result.reasoning

    def test_regular_url_with_analysis_still_triggers_thinking(self):
        """Non-share URLs with analysis keywords should still trigger THINKING_ANALYSIS."""
        result = IntentRouter.analyze("请分析这个技术文档 https://arxiv.org/abs/1234.5678")
        assert result.intent_type == IntentType.THINKING_ANALYSIS
        assert result.url == "https://arxiv.org/abs/1234.5678"

    def test_explicit_save_only_keyword(self):
        """Explicit save keywords override thinking detection."""
        result = IntentRouter.analyze("保存这个链接 https://example.com/article")
        assert result.intent_type == IntentType.URL_SAVE

    def test_explicit_skip_analysis(self):
        """Explicit skip analysis keywords work."""
        result = IntentRouter.analyze(
            "直接保存 https://example.com/article 不用分析"
        )
        assert result.intent_type == IntentType.URL_SAVE

    def test_mind_control_commands(self):
        """Mind control commands are detected."""
        # Test enable
        result = IntentRouter.analyze("enable innovation mind")
        assert result.intent_type == IntentType.MIND_CONTROL
        assert result.mind_action == "enable"
        assert result.mind_name == "innovation"

        # Test disable
        result = IntentRouter.analyze("关闭 dikiwi")
        assert result.intent_type == IntentType.MIND_CONTROL
        assert result.mind_action == "disable"
        assert result.mind_name == "dikiwi"

        # Test status
        result = IntentRouter.analyze("entrepreneur status")
        assert result.intent_type == IntentType.MIND_CONTROL
        assert result.mind_action == "status"
        assert result.mind_name == "entrepreneur"

    def test_should_analyze_helper(self):
        """The should_analyze helper works correctly."""
        assert IntentRouter.should_analyze("分析这个 https://example.com")
        assert not IntentRouter.should_analyze("Hello world")
        assert not IntentRouter.should_analyze(
            "【分析某个问题 - Monica AI Chat】https://monica.im/share/chat?shareId=abc"
        )


class TestMessageIntent:
    """Test the MessageIntent dataclass."""

    def test_basic_creation(self):
        """Can create a MessageIntent."""
        intent = MessageIntent(
            intent_type=IntentType.URL_SAVE,
            url="https://example.com",
            text="Check this out",
            confidence=0.9,
            reasoning="URL detected",
        )
        assert intent.intent_type == IntentType.URL_SAVE
        assert intent.url == "https://example.com"

    def test_mind_control_creation(self):
        """Can create a mind control intent."""
        intent = MessageIntent(
            intent_type=IntentType.MIND_CONTROL,
            mind_name="dikiwi",
            mind_action="enable",
            confidence=0.95,
        )
        assert intent.mind_name == "dikiwi"
        assert intent.mind_action == "enable"
