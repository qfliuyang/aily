"""Universal content processing router.

Routes content to the appropriate processor based on detected type.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aily.config import SETTINGS
from aily.processing.detector import ContentType, ContentTypeDetector
from aily.processing.processors import (
    ContentProcessor,
    CSVProcessor,
    DocxProcessor,
    ExtractedContent,
    ImageProcessor,
    MarkdownProcessor,
    PDFProcessor,
    TextProcessor,
    WebProcessor,
    XLSXProcessor,
)

if TYPE_CHECKING:
    from aily.browser.manager import BrowserUseManager

logger = logging.getLogger(__name__)


def _format_size(size_bytes: int) -> str:
    """Format byte size to human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


class ProcessingRouter:
    """Routes content to the appropriate processor.

    Usage:
        router = ProcessingRouter()
        result = await router.process(file_bytes, filename="paper.pdf")
        # result.text contains extracted text
    """

    def __init__(self, browser_manager: "BrowserUseManager | None" = None) -> None:
        self.browser_manager = browser_manager
        self._processors: list[ContentProcessor] = []
        self._init_processors()

    def _init_processors(self) -> None:
        """Initialize all available processors."""
        self._processors = [
            PDFProcessor(),
            ImageProcessor(languages=["en", "ch_sim", "ch_tra"]),  # English + Chinese
            MarkdownProcessor(),
            DocxProcessor(),
            CSVProcessor(),
            XLSXProcessor(),
            WebProcessor(browser_manager=self.browser_manager),
            TextProcessor(),  # Fallback for text/*
        ]

    async def process(
        self,
        data: bytes,
        filename: str | None = None,
        http_content_type: str | None = None,
    ) -> ExtractedContent:
        """Process any content and extract text.

        Args:
            data: Raw file bytes
            filename: Original filename (helps with detection)
            http_content_type: HTTP Content-Type header (if fetched from URL)

        Returns:
            ExtractedContent with text and metadata
        """
        # 1. Check file size limits first
        size_limit = SETTINGS.max_file_size
        if http_content_type and http_content_type.startswith("image/"):
            size_limit = SETTINGS.max_image_size

        if len(data) > size_limit:
            logger.warning(
                "File too large: %s > %s limit",
                _format_size(len(data)),
                _format_size(size_limit),
            )
            return ExtractedContent(
                text=f"[File too large: {_format_size(len(data))} exceeds limit of {_format_size(size_limit)}]",
                source_type="error",
            )

        # 2. Detect content type
        content_type = ContentTypeDetector.detect(
            data=data,
            filename=filename,
            http_content_type=http_content_type,
        )

        logger.info(
            "Processing content: type=%s, confidence=%.2f, filename=%s",
            content_type.mime_type,
            content_type.confidence,
            filename,
        )

        # 3. Find matching processor
        processor = self._get_processor(content_type.mime_type)

        if processor is None:
            logger.warning(
                "No processor for type %s, trying text fallback",
                content_type.mime_type,
            )
            # Try text processor as last resort
            processor = TextProcessor()

        # 3. Process and return
        try:
            result = await processor.process(data, filename)
            logger.info(
                "Extracted %d chars from %s",
                len(result.text),
                content_type.mime_type,
            )
            return result
        except Exception as e:
            logger.exception("Processing failed for %s", content_type.mime_type)
            return ExtractedContent(
                text=f"[Processing failed: {e}]",
                source_type="error",
            )

    def _get_processor(self, mime_type: str) -> ContentProcessor | None:
        """Find the best processor for a MIME type."""
        # Exact match first
        for processor in self._processors:
            if mime_type in processor.SUPPORTED_TYPES:
                return processor

        # Wildcard match (e.g., image/*)
        for processor in self._processors:
            if processor.can_process(mime_type):
                return processor

        return None

    async def process_url(
        self,
        url: str,
        browser_manager: "BrowserUseManager | None" = None,
    ) -> ExtractedContent:
        """Process content from a URL.

        Args:
            url: URL to fetch and process
            browser_manager: Optional browser for JS-rendered pages

        Returns:
            ExtractedContent with text and metadata
        """
        import httpx

        logger.info("Fetching URL: %s", url)

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()

                data = response.content
                content_type = response.headers.get("content-type")

                return await self.process(
                    data=data,
                    filename=url.split("/")[-1] or "index.html",
                    http_content_type=content_type,
                )

        except Exception as e:
            logger.exception("Failed to fetch URL: %s", url)
            return ExtractedContent(
                text=f"[Failed to fetch {url}: {e}]",
                source_type="web",
            )
