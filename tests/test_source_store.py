from __future__ import annotations

from pathlib import Path

import pytest

from aily.source_store import SourceStore


@pytest.mark.asyncio
async def test_source_store_persists_upload_and_detects_duplicate(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        first = await store.store_upload(
            upload_id="upload-1",
            filename="note.txt",
            content_type="text/plain",
            data=b"same content",
        )
        second = await store.store_upload(
            upload_id="upload-2",
            filename="copy.txt",
            content_type="text/plain",
            data=b"same content",
        )

        assert first["duplicate"] is False
        assert second["duplicate"] is True
        assert first["source_id"] == second["source_id"]
        assert Path(first["storage_path"]).read_bytes() == b"same content"
        assert (await store.get_source_for_upload("upload-2"))["source_id"] == first["source_id"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_source_store_status_survives_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    object_dir = tmp_path / "objects"
    store = SourceStore(db_path, object_dir)
    await store.initialize()
    first = await store.store_upload(
        upload_id="upload-1",
        filename="note.txt",
        content_type="text/plain",
        data=b"content",
    )
    await store.update_status(first["source_id"], "completed", {"pipeline_id": "pipe-1"})
    await store.close()

    reopened = SourceStore(db_path, object_dir)
    await reopened.initialize()
    try:
        source = await reopened.get_source(first["source_id"])
        listing = await reopened.list_sources()

        assert source is not None
        assert source["status"] == "completed"
        assert source["metadata"]["pipeline_id"] == "pipe-1"
        assert listing["sources"][0]["source_id"] == first["source_id"]
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_source_store_persists_url_identity(tmp_path: Path) -> None:
    store = SourceStore(tmp_path / "source.db", tmp_path / "objects")
    await store.initialize()
    try:
        first = await store.store_url(url="https://example.com/a")
        second = await store.store_url(url="https://example.com/a")

        assert first["duplicate"] is False
        assert second["duplicate"] is True
        assert first["source_id"] == second["source_id"]
    finally:
        await store.close()
