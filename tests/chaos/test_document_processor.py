from __future__ import annotations

from pathlib import Path

import pytest

from aily.chaos.config import ChaosConfig
from aily.chaos.processors.document import TextProcessor


class FakeMarkdownizeResult:
    def __init__(self, markdown: str) -> None:
        self.markdown = markdown


class FakeBrowserManager:
    async def fetch(self, url: str, timeout: int = 60, use_personal_profile: bool = False) -> str:
        return f"Fetched content for {url}"


@pytest.mark.asyncio
async def test_text_processor_reads_plain_markdown(tmp_path: Path):
    file_path = tmp_path / "note.md"
    file_path.write_text("# Test Document\n\nThis is a local note.", encoding="utf-8")

    processor = TextProcessor(ChaosConfig())
    result = await processor.process(file_path)

    assert result is not None
    assert result.title == "Test Document"
    assert result.source_type == "text"
    assert "This is a local note." in result.text


@pytest.mark.asyncio
async def test_text_processor_fetches_url_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    file_path = tmp_path / "article.md"
    file_path.write_text("https://example.com/article\n", encoding="utf-8")

    async def fake_fetch_with_browser(self, url: str):
        return FakeMarkdownizeResult(f"# Example Article\n\nBody from {url}\n\n---\n*Source: {url}*")

    monkeypatch.setattr(
        TextProcessor,
        "_fetch_url_as_markdown",
        lambda self, markdownizer, url: fake_fetch_with_browser(markdownizer, url),
    )

    processor = TextProcessor(ChaosConfig(), browser_manager=FakeBrowserManager())
    result = await processor.process(file_path)

    assert result is not None
    assert result.source_type == "url_markdown"
    assert result.processing_method == "browser_url_markdown_fetch"
    assert result.metadata["source_urls"] == ["https://example.com/article"]
    assert len(result.metadata["url_import_items"]) == 1
    assert "# Example Article" in result.text
    assert "https://example.com/article" in result.text


@pytest.mark.asyncio
async def test_text_processor_keeps_original_note_when_fetching_urls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    file_path = tmp_path / "bookmark.md"
    file_path.write_text("# Reading Queue\n\nhttps://example.com/post\n", encoding="utf-8")

    async def fake_fetch_with_browser(self, url: str):
        return FakeMarkdownizeResult(f"# Imported Post\n\nFetched body from {url}")

    monkeypatch.setattr(
        TextProcessor,
        "_fetch_url_as_markdown",
        lambda self, markdownizer, url: fake_fetch_with_browser(markdownizer, url),
    )

    processor = TextProcessor(ChaosConfig(), browser_manager=FakeBrowserManager())
    result = await processor.process(file_path)

    assert result is not None
    assert result.source_type == "url_markdown"
    assert len(result.metadata["url_import_items"]) == 1
    assert "## Original Note" in result.text
    assert "# Reading Queue" in result.text
    assert "## Fetched Content" in result.text
    assert "# Imported Post" in result.text


@pytest.mark.asyncio
async def test_text_processor_splits_multi_url_import_into_atomic_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    file_path = tmp_path / "bundle.md"
    file_path.write_text("https://example.com/a\nhttps://example.com/b\n", encoding="utf-8")

    async def fake_fetch(self, markdownizer, url: str):
        return FakeMarkdownizeResult(f"# {url[-1].upper()} Title\n\nBody from {url}")

    monkeypatch.setattr(TextProcessor, "_fetch_url_as_markdown", fake_fetch)

    processor = TextProcessor(ChaosConfig(), browser_manager=FakeBrowserManager())
    result = await processor.process(file_path)
    split_items = processor.split_url_import_items(result)

    assert len(split_items) == 2
    assert split_items[0].source_type == "url_markdown_item"
    assert split_items[0].metadata["source_url"] == "https://example.com/a"
    assert split_items[0].title == "A Title"
    assert split_items[1].metadata["source_url"] == "https://example.com/b"


@pytest.mark.asyncio
async def test_text_processor_imports_mineru_full_markdown(tmp_path: Path):
    export_dir = tmp_path / "paper_export"
    export_dir.mkdir()
    file_path = export_dir / "full.md"
    file_path.write_text("# MinerU Paper Title\n\nStructured markdown body.", encoding="utf-8")
    (export_dir / "content_list.json").write_text(
        '[{"page_idx": 0, "text": "a"}, {"page_idx": 1, "text": "b"}]',
        encoding="utf-8",
    )

    processor = TextProcessor(ChaosConfig())
    result = await processor.process(file_path)

    assert result is not None
    assert result.source_type == "mineru_markdown"
    assert result.processing_method == "mineru_import"
    assert result.metadata["chaos_base_name"] == "paper_export"
    assert result.metadata["pages"] == 2
    assert "content_list.json" in result.metadata["mineru_sidecar_files"]
    assert result.title == "MinerU Paper Title"
