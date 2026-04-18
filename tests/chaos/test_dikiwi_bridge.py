from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from aily.chaos.dikiwi_bridge import ChaosDikiwiBridge
from aily.chaos.types import ExtractedContentMultimodal
from scripts.run_chaos_daemon import ChaosDaemon


class FakeDikiwiMind:
    async def process_input(self, drop):
        return SimpleNamespace(
            final_stage_reached=SimpleNamespace(name="KNOWLEDGE"),
            pipeline_id="pipe_1",
            stage_results=[
                SimpleNamespace(success=True, data={"zettels": ["z1", "z2"], "insights": ["i1"]}),
            ],
        )


@pytest.mark.asyncio
async def test_bridge_batch_counts_zettels_created(tmp_path):
    processed_dir = tmp_path / ".processed" / "2026-04-12"
    processed_dir.mkdir(parents=True)

    content = ExtractedContentMultimodal(
        text="raw chaos",
        title="Inbox note",
        source_type="text",
        source_path=Path("/tmp/inbox.md"),
        processing_timestamp=datetime(2026, 4, 12, 10, 0, 0),
        processing_method="unit-test",
    )
    (processed_dir / "item.json").write_text(json.dumps(content.to_dict()), encoding="utf-8")

    bridge = ChaosDikiwiBridge(
        dikiwi_mind=FakeDikiwiMind(),
        processed_folder=tmp_path / ".processed",
    )

    result = await bridge.process_batch(date_folder="2026-04-12")

    assert result["processed"] == 1
    assert result["failed"] == 0
    assert result["zettels_created"] == 2


@dataclass
class FakeRecord:
    id: int
    filename: str
    source_path: str
    file_type: str


class FakeQueue:
    def __init__(self, _db_path):
        self.records = [FakeRecord(1, "one.md", "/tmp/one.md", "text")]
        self.completed = []

    def get_stats(self):
        return {"pending": len(self.records), "completed": len(self.completed)}

    def claim_next(self):
        if self.records:
            return self.records.pop(0)
        return None

    def mark_completed(self, file_id, output_path=None, vault_path=None):
        self.completed.append((file_id, output_path, vault_path))

    def mark_failed(self, file_id, error_message):
        raise AssertionError(f"unexpected failure for {file_id}: {error_message}")

    def reset_processing(self):
        return 0


class FakeImageQueue:
    def __init__(self, _db_path):
        self.records = [
            FakeRecord(1, "session_001.png", "/tmp/session_001.png", "image"),
            FakeRecord(2, "session_002.png", "/tmp/session_002.png", "image"),
        ]
        self.completed = []

    def get_stats(self):
        return {"pending": len(self.records), "completed": len(self.completed)}

    def claim_next(self):
        if self.records:
            return self.records.pop(0)
        return None

    def get_pending_files(self):
        return list(self.records)

    def claim_specific(self, file_ids):
        claimed = [record for record in self.records if record.id in file_ids]
        self.records = [record for record in self.records if record.id not in file_ids]
        return claimed

    def mark_completed(self, file_id, output_path=None, vault_path=None):
        self.completed.append((file_id, output_path, vault_path))

    def mark_failed(self, file_id, error_message):
        raise AssertionError(f"unexpected failure for {file_id}: {error_message}")

    def reset_processing(self):
        return 0


class FakeBridge:
    def __init__(self):
        self.processed = []

    async def process_extracted_content(self, content):
        self.processed.append(content.title)
        return {"stage": "KNOWLEDGE", "zettels_created": 3}


@pytest.mark.asyncio
async def test_daemon_run_once_reuses_shared_bridge(monkeypatch):
    import scripts.run_chaos_daemon as daemon_module

    fake_bridge = FakeBridge()

    monkeypatch.setattr(daemon_module, "ChaosQueue", FakeQueue)

    daemon = ChaosDaemon()
    monkeypatch.setattr(daemon, "scan_existing", lambda: 1)
    async def fake_extract(record):
        return ExtractedContentMultimodal(
            text="captured",
            title=record.filename,
            source_type="text",
            source_path=Path(record.source_path),
        )

    monkeypatch.setattr(daemon, "_extract_content", fake_extract)

    ensure_calls = 0
    close_calls = 0

    async def fake_ensure():
        nonlocal ensure_calls
        ensure_calls += 1
        return fake_bridge

    async def fake_close():
        nonlocal close_calls
        close_calls += 1

    monkeypatch.setattr(daemon, "_ensure_dikiwi_bridge", fake_ensure)
    monkeypatch.setattr(daemon, "_close_dikiwi_runtime", fake_close)

    result = await daemon.run_once()

    assert result == {"processed": 1, "remaining": 0}
    assert ensure_calls == 1
    assert close_calls == 1
    assert fake_bridge.processed == ["one.md"]
    assert daemon.queue.completed[0][0] == 1


@pytest.mark.asyncio
async def test_daemon_groups_related_images_into_one_session(monkeypatch):
    import scripts.run_chaos_daemon as daemon_module

    fake_bridge = FakeBridge()
    monkeypatch.setattr(daemon_module, "ChaosQueue", FakeImageQueue)

    daemon = ChaosDaemon()
    monkeypatch.setattr(daemon, "scan_existing", lambda: 2)

    fake_contents = {
        "/tmp/session_001.png": ExtractedContentMultimodal(
            text="## Image Description\n\nFirst slide",
            title="Session 001",
            source_type="image",
            source_path=Path("/tmp/session_001.png"),
            processing_method="glm-4v",
        ),
        "/tmp/session_002.png": ExtractedContentMultimodal(
            text="## Image Description\n\nSecond slide",
            title="Session 002",
            source_type="image",
            source_path=Path("/tmp/session_002.png"),
            processing_method="glm-4v",
        ),
    }

    async def fake_extract(record):
        return fake_contents[record.source_path]

    async def fake_ensure():
        return fake_bridge

    async def fake_close():
        return None

    monkeypatch.setattr(daemon, "_extract_content", fake_extract)
    monkeypatch.setattr(daemon, "_ensure_dikiwi_bridge", fake_ensure)
    monkeypatch.setattr(daemon, "_close_dikiwi_runtime", fake_close)
    monkeypatch.setattr(daemon, "_session_title_from_paths", lambda paths: "Tech Session")
    monkeypatch.setattr(
        daemon,
        "_build_image_context",
        lambda path: daemon_module.ImageContext(
            path=Path(path),
            parent=Path("/tmp"),
            stem=Path(path).stem,
            suffix=".png",
            mtime=100.0 if "001" in str(path) else 120.0,
            exif_time=None,
            camera_model=None,
            filename_key="session-###",
        ),
    )

    result = await daemon.run_once()

    assert result == {"processed": 2, "remaining": 0}
    assert fake_bridge.processed == ["Tech Session"]
    assert len(daemon.queue.completed) == 2


@pytest.mark.asyncio
async def test_daemon_splits_multi_url_markdown_into_multiple_dikiwi_jobs(monkeypatch):
    import scripts.run_chaos_daemon as daemon_module

    fake_bridge = FakeBridge()
    monkeypatch.setattr(daemon_module, "ChaosQueue", FakeQueue)

    daemon = ChaosDaemon()
    daemon.queue = FakeQueue(None)
    daemon.queue.records = []

    content = ExtractedContentMultimodal(
        text="# URL Import\n",
        title="URL Import",
        source_type="url_markdown",
        source_path=Path("/tmp/urls.md"),
        processing_method="browser_url_markdown_fetch",
        metadata={
            "url_import_items": [
                {"url": "https://example.com/a", "title": "A", "markdown": "# A\n\nOne"},
                {"url": "https://example.com/b", "title": "B", "markdown": "# B\n\nTwo"},
            ],
            "source_urls": ["https://example.com/a", "https://example.com/b"],
        },
    )

    async def fake_extract(record):
        return content

    async def fake_ensure():
        return fake_bridge

    async def fake_close():
        return None

    monkeypatch.setattr(daemon, "_extract_content", fake_extract)
    monkeypatch.setattr(daemon, "_ensure_dikiwi_bridge", fake_ensure)
    monkeypatch.setattr(daemon, "_close_dikiwi_runtime", fake_close)

    await daemon._process_records([FakeRecord(1, "urls.md", "/tmp/urls.md", "markdown")])

    assert fake_bridge.processed == ["A", "B"]


def test_daemon_scan_existing_skips_mineru_sidecars(monkeypatch, tmp_path):
    import scripts.run_chaos_daemon as daemon_module

    chaos_root = tmp_path / "chaos"
    export_dir = chaos_root / "mineru_batch" / "report"
    export_dir.mkdir(parents=True)
    (export_dir / "full.md").write_text("# Parsed\n\nBody", encoding="utf-8")
    (export_dir / "content_list.json").write_text("[]", encoding="utf-8")
    (export_dir / "layout.json").write_text("{}", encoding="utf-8")

    added: list[tuple[str, str]] = []

    class RecordingQueue:
        def __init__(self, _db_path):
            pass

        def add_file(self, path, file_type):
            added.append((Path(path).name, file_type))
            return True

    monkeypatch.setattr(daemon_module, "CHAOS_FOLDER", chaos_root)
    monkeypatch.setattr(daemon_module, "ChaosQueue", RecordingQueue)

    daemon = daemon_module.ChaosDaemon()
    scanned = daemon.scan_existing()

    assert scanned == 1
    assert added == [("full.md", "markdown")]
