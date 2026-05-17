from __future__ import annotations

from pathlib import Path

import pytest

from aily.processing.canonical_markdown import CanonicalMarkdownConverter
from aily.processing.processors import ExtractedContent
from aily.source_store import SourceStore


pytestmark = pytest.mark.contract


async def test_source_store_persists_canonical_markdown_package(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    object_dir = tmp_path / "objects"
    markdown_dir = tmp_path / "markdown"
    store = SourceStore(db_path, object_dir, markdown_dir)
    await store.initialize()
    try:
        source = await store.store_upload(
            upload_id="upload-1",
            filename="brief.txt",
            content_type="text/plain",
            data=b"raw brief",
        )
        package = await store.store_markdown_package(
            source_id=source["source_id"],
            markdown="# Brief\n\nCanonical content.",
            title="Brief",
            source_type="text",
            metadata={"converter": "test"},
        )
        source_after = await store.get_source(source["source_id"])

        assert Path(package["package_path"]).read_text(encoding="utf-8") == "# Brief\n\nCanonical content.\n"
        assert source_after is not None
        assert source_after["metadata"]["canonical_markdown_package_id"] == package["package_id"]
        assert source_after["metadata"]["canonical_markdown_path"] == package["package_path"]
    finally:
        await store.close()

    reopened = SourceStore(db_path, object_dir, markdown_dir)
    await reopened.initialize()
    try:
        package_after = await reopened.get_markdown_package(source["source_id"])
        markdown = await reopened.read_markdown_package(source["source_id"])

        assert package_after is not None
        assert package_after["package_id"] == package["package_id"]
        assert package_after["metadata"]["converter"] == "test"
        assert markdown == "# Brief\n\nCanonical content.\n"
    finally:
        await reopened.close()


async def test_canonical_markdown_converter_stores_extracted_content(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects", tmp_path / "markdown")
    await store.initialize()
    try:
        source = await store.store_upload(
            upload_id="upload-1",
            filename="memo.txt",
            content_type="text/plain",
            data=b"memo body",
        )
        converter = CanonicalMarkdownConverter(source_store=store)
        package = await converter.convert_extracted(
            source_id=source["source_id"],
            extracted=ExtractedContent(
                text="Important memo body.",
                title="Memo",
                source_type="text",
                metadata={"language": "en"},
            ),
            fallback_title="memo.txt",
            metadata={"job_id": "job-1"},
        )
        stored = await store.get_markdown_package(source["source_id"])

        assert package.markdown == "# Memo\n\nImportant memo body."
        assert package.title == "Memo"
        assert package.metadata["language"] == "en"
        assert package.metadata["job_id"] == "job-1"
        assert stored is not None
        assert stored["markdown_sha256"] == package.markdown_sha256
    finally:
        await store.close()
