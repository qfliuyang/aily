"""Tests for MarkdownizeProcessor.

Tests URL to markdown conversion and content quality detection.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from aily.processing.markdownize import MarkdownizeProcessor, MarkdownContent
from aily.processing.processors import ExtractedContent


class TestMarkdownContent:
    """Test the MarkdownContent dataclass."""

    def test_basic_creation(self):
        """Can create MarkdownContent."""
        content = MarkdownContent(
            markdown="# Title\n\nContent",
            title="Test",
            source_url="https://example.com",
            source_type="url",
        )
        assert content.markdown == "# Title\n\nContent"
        assert content.title == "Test"
        assert content.source_url == "https://example.com"

    def test_metadata_defaults(self):
        """Metadata defaults to empty dict."""
        content = MarkdownContent(markdown="test")
        assert content.metadata == {}


class TestMarkdownizeProcessor:
    """Test the MarkdownizeProcessor."""

    def test_needs_browser_detection(self):
        """Detects URLs that need browser rendering."""
        processor = MarkdownizeProcessor()

        # JS-required domains
        assert processor._needs_browser("https://monica.im/share/chat")
        assert processor._needs_browser("https://chatgpt.com/c/123")
        assert processor._needs_browser("https://claude.ai/chat")
        assert processor._needs_browser("https://twitter.com/user/status/123")

        # Regular domains
        assert not processor._needs_browser("https://example.com/article")
        assert not processor._needs_browser("https://news.ycombinator.com")
        assert not processor._needs_browser("https://arxiv.org/abs/1234")

    def test_is_low_quality_detection(self):
        """Detects low-quality extracted content."""
        processor = MarkdownizeProcessor()

        # Very short content
        short = ExtractedContent(text="Short", source_type="web")
        assert processor._is_low_quality(short)

        # Generic Monica title
        monica = ExtractedContent(
            text="Monica - Your GPT AI Assistant Chrome Extension",
            title="Monica - Your GPT AI Assistant Chrome Extension",
            source_type="web",
        )
        assert processor._is_low_quality(monica)

        # Good content
        good = ExtractedContent(
            text="This is a long article with lots of content about AI. " * 20,
            title="Understanding Neural Networks",
            source_type="web",
        )
        assert not processor._is_low_quality(good)

        # Empty content
        empty = ExtractedContent(text="", source_type="web")
        assert processor._is_low_quality(empty)

    @pytest.mark.asyncio
    async def test_process_static_url(self):
        """Process URL using static fetch."""
        processor = MarkdownizeProcessor(browser_manager=None)

        # Test with example.com (reliable test site)
        result = await processor.process_url(
            "https://example.com",
            use_browser=False,
        )

        assert isinstance(result, MarkdownContent)
        assert result.source_url == "https://example.com"
        assert result.source_type == "url"
        assert "example domain" in result.markdown.lower()
        assert "# " in result.markdown  # Has header

    @pytest.mark.asyncio
    async def test_html_to_markdown_conversion(self):
        """Convert HTML to markdown."""
        processor = MarkdownizeProcessor()

        html = """
        <html>
        <head><title>Test Article</title></head>
        <body>
            <h1>Main Title</h1>
            <p>This is a paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
            <h2>Section</h2>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
            </ul>
            <a href="https://example.com">Link text</a>
        </body>
        </html>
        """

        markdown = processor._html_to_markdown(html, "https://test.com")

        # Check conversions
        assert "# Main Title" in markdown
        assert "## Section" in markdown
        assert "**bold**" in markdown
        assert "*italic*" in markdown
        assert "- Item 1" in markdown
        assert "- Item 2" in markdown
        assert "[Link text](https://example.com)" in markdown
        assert "*Source: https://test.com*" in markdown

    @pytest.mark.asyncio
    async def test_process_low_quality_content_triggers_browser_retry(self):
        """When content is low quality and browser available, retry with browser."""
        mock_browser = AsyncMock()
        mock_browser.fetch = AsyncMock(return_value="Browser fetched content with lots of text. " * 20)

        processor = MarkdownizeProcessor(browser_manager=mock_browser)

        # Create low quality content
        low_quality = ExtractedContent(
            text="Monica - Your GPT AI Assistant",
            title="Monica - Your GPT AI Assistant Chrome Extension",
            source_type="web",
            metadata={"url": "https://monica.im/share/chat?shareId=abc123"},
        )

        result = await processor.process_content(low_quality)

        # Should have retried with browser
        mock_browser.fetch.assert_called_once()
        assert "browser" in result.metadata.get("fetched_with", "")

    @pytest.mark.asyncio
    async def test_process_content_without_url_skips_browser_retry(self):
        """When low quality content has no URL, don't retry."""
        processor = MarkdownizeProcessor(browser_manager=None)

        low_quality = ExtractedContent(
            text="Short",
            source_type="web",
            metadata={},  # No URL
        )

        result = await processor.process_content(low_quality)

        # Should convert to markdown anyway
        assert result.markdown is not None

    def test_convert_tags_to_markdown(self):
        """Test HTML to markdown tag conversion."""
        processor = MarkdownizeProcessor()

        html = """
        <h1>H1</h1>
        <h2>H2</h2>
        <h3>H3</h3>
        <p>Paragraph with <a href="http://test.com">link</a></p>
        <code>inline code</code>
        <pre>code block</pre>
        <blockquote>Quote</blockquote>
        """

        markdown = processor._convert_tags_to_markdown(html)

        assert "# H1" in markdown
        assert "## H2" in markdown
        assert "### H3" in markdown
        assert "[link](http://test.com)" in markdown
        assert "`inline code`" in markdown
        assert "```" in markdown
        assert "> Quote" in markdown
