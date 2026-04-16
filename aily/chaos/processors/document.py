"""Text and document processors."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from pathlib import Path

from aily.browser.manager import BrowserUseManager
from aily.chaos.processors.base import ContentProcessor
from aily.chaos.types import ExtractedContentMultimodal
from aily.processing.markdownize import MarkdownizeProcessor

logger = logging.getLogger(__name__)


class TextProcessor(ContentProcessor):
    """Processor for text and markdown files."""

    URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]{}\"']+")

    def __init__(
        self,
        config,
        llm_client=None,
        browser_manager: BrowserUseManager | None = None,
    ) -> None:
        super().__init__(config, llm_client)
        self.browser_manager = browser_manager

    def _get_browser_manager(self) -> BrowserUseManager:
        if self.browser_manager is None:
            self.browser_manager = BrowserUseManager()
        return self.browser_manager

    async def process(self, file_path: Path) -> ExtractedContentMultimodal | None:
        """Process text/markdown file."""
        try:
            text = await asyncio.to_thread(self._read_file, file_path)
            if file_path.suffix.lower() in {".md", ".markdown"}:
                try:
                    url_result = await self._maybe_fetch_urls_to_markdown(file_path, text)
                    if url_result is not None:
                        return url_result
                except Exception as exc:
                    logger.warning(
                        "URL markdown fetch failed for %s, falling back to plain markdown: %s",
                        file_path.name,
                        exc,
                    )

            # Extract title from first heading
            title = self._extract_title(text, file_path)

            return ExtractedContentMultimodal(
                text=text,
                title=title,
                source_type="text",
                source_path=file_path,
                processing_method="text_reader",
            )
        except Exception as e:
            logger.exception("Failed to process text file: %s", e)
            return None

    async def _maybe_fetch_urls_to_markdown(
        self,
        file_path: Path,
        text: str,
    ) -> ExtractedContentMultimodal | None:
        """If markdown contains URLs, fetch them and return browser-backed markdown."""
        urls = self._extract_urls(text)
        if not urls:
            return None

        logger.info("Markdown file %s contains %s URL(s); fetching content", file_path.name, len(urls))
        markdownizer = MarkdownizeProcessor(self._get_browser_manager())

        fetched_urls: list[str] = []
        failed_urls: list[str] = []
        fetched_items: list[dict[str, str]] = []

        for url in urls:
            try:
                result = await self._fetch_url_as_markdown(markdownizer, url)
                fetched_urls.append(url)
                item_markdown = getattr(result, "markdown", "").strip()
                item_title = getattr(result, "title", None) or self._extract_title(item_markdown, file_path)
                fetched_items.append(
                    {
                        "url": url,
                        "title": item_title,
                        "markdown": item_markdown,
                    }
                )
            except Exception as exc:
                logger.warning("Browser fetch failed for %s: %s", url, exc)
                failed_urls.append(url)

        if not fetched_items:
            return None

        combined_markdown = self._combine_original_and_fetched_markdown(
            file_path=file_path,
            original_text=text,
            fetched_sections=[item["markdown"] for item in fetched_items],
        )
        title = self._extract_title(combined_markdown, file_path)

        tags = ["url-import", "markdown"]
        metadata = {
            "source_urls": fetched_urls,
            "failed_source_urls": failed_urls,
            "source_file_name": file_path.name,
            "fetched_url_count": len(fetched_urls),
            "url_import_items": fetched_items,
        }

        return ExtractedContentMultimodal(
            text=combined_markdown,
            title=title,
            source_type="url_markdown",
            source_path=file_path,
            processing_method="browser_url_markdown_fetch",
            tags=tags,
            metadata=metadata,
        )

    async def _fetch_url_as_markdown(
        self,
        markdownizer: MarkdownizeProcessor,
        url: str,
    ):
        """Fetch URL content with the best available strategy for Chaos imports."""
        # Monica share links require browser rendering; let markdownizer route them.
        return await markdownizer.process_url(url, use_browser=True)

    def _read_file(self, file_path: Path) -> str:
        """Read file contents."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _extract_title(self, text: str, file_path: Path) -> str:
        """Extract title from first markdown heading or filename."""
        lines = text.split("\n")
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            if line.startswith("## "):
                return line[3:].strip()
        # Fallback to filename
        return file_path.stem.replace("_", " ").replace("-", " ").title()

    def _extract_urls(self, text: str) -> list[str]:
        """Extract unique URLs from markdown content in source order."""
        seen: set[str] = set()
        urls: list[str] = []
        for match in self.URL_PATTERN.findall(text):
            url = match.rstrip(".,);!?]>")
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def _combine_original_and_fetched_markdown(
        self,
        *,
        file_path: Path,
        original_text: str,
        fetched_sections: list[str],
    ) -> str:
        """Blend original markdown note with fetched URL content."""
        original = original_text.strip()
        parts: list[str] = []

        if original and len(original) > 20:
            parts.append(f"# URL Import: {file_path.stem.replace('_', ' ').replace('-', ' ').title()}")
            parts.append("")
            parts.append("## Original Note")
            parts.append("")
            parts.append(original)

        if fetched_sections:
            if parts:
                parts.extend(["", "## Fetched Content", ""])
            parts.append("\n\n---\n\n".join(section for section in fetched_sections if section))

        return "\n".join(part for part in parts if part is not None).strip()

    def split_url_import_items(
        self,
        content: ExtractedContentMultimodal,
    ) -> list[ExtractedContentMultimodal]:
        """Split a multi-URL markdown import into one extracted item per fetched URL."""
        items = content.metadata.get("url_import_items", [])
        if not items:
            return [content]

        split_contents: list[ExtractedContentMultimodal] = []
        for item in items:
            url = item.get("url", "")
            title = item.get("title") or content.title
            markdown = item.get("markdown", "").strip()
            if not markdown:
                continue

            source_path = content.source_path
            item_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10] if url else ""
            split_contents.append(
                ExtractedContentMultimodal(
                    text=markdown,
                    title=title,
                    source_type="url_markdown_item",
                    source_path=source_path,
                    processing_method="browser_url_markdown_fetch",
                    tags=list(dict.fromkeys([*content.tags, "url-import-item"])),
                    metadata={
                        **content.metadata,
                        "source_url": url,
                        "source_urls": [url] if url else [],
                        "url_import_item_id": item_hash,
                    },
                )
            )

        return split_contents or [content]

    def can_process(self, file_path: Path) -> bool:
        """Check if file is text."""
        ext = file_path.suffix.lower()
        return ext in {".txt", ".md", ".markdown", ".rst", ".text"}


class GenericDocumentProcessor(ContentProcessor):
    """Fallback processor for unknown file types."""

    async def process(self, file_path: Path) -> ExtractedContentMultimodal | None:
        """Process generic file - just captures metadata."""
        try:
            stat = file_path.stat()
            text = f"""File: {file_path.name}
Type: {file_path.suffix}
Size: {stat.st_size} bytes

This file type is not directly processable. The original file is preserved.
"""
            return ExtractedContentMultimodal(
                text=text,
                title=file_path.stem,
                source_type="generic",
                source_path=file_path,
                processing_method="generic",
                metadata={
                    "file_size": stat.st_size,
                    "extension": file_path.suffix,
                },
            )
        except Exception as e:
            logger.exception("Failed to process generic file: %s", e)
            return None

    def can_process(self, file_path: Path) -> bool:
        """Can process any file."""
        return True
