from __future__ import annotations

from pathlib import Path

import pytest

from aily.chaos.config import ChaosConfig
from aily.chaos.processors.mineru_processor import MinerUProcessor


class FakeProc:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode

    async def communicate(self):
        return b"ok", b""


@pytest.mark.asyncio
async def test_mineru_processor_normalizes_cli_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "deck.pptx"
    source.write_bytes(b"fake")

    config = ChaosConfig(
        watch_folder=tmp_path,
        processed_folder=tmp_path / ".processed",
        failed_folder=tmp_path / ".failed",
    )
    processor = MinerUProcessor(config)

    async def fake_base_url():
        return "http://127.0.0.1:8000"

    async def fake_invoke(base_url: str, file_path: Path, output_dir: Path) -> bool:
        export_dir = output_dir / file_path.stem / "auto"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / f"{file_path.stem}.md").write_text("# Deck Title\n\nBody", encoding="utf-8")
        (export_dir / "content_list.json").write_text(
            '[{"type":"image","page_idx":0,"image_caption":["Diagram"]}]',
            encoding="utf-8",
        )
        return True

    monkeypatch.setattr(processor, "_ensure_api_base_url", fake_base_url)
    monkeypatch.setattr(processor, "_invoke_mineru_api", fake_invoke)

    result = await processor.process(source)

    assert result is not None
    assert result.source_path == source
    assert result.source_type == "presentation"
    assert result.processing_method == "mineru:pipeline"
    assert result.metadata["chaos_base_name"] == "deck"
    assert result.metadata["mineru_backend"] == "pipeline"
    assert result.metadata["mineru_model_source"] == "modelscope"
    assert result.visual_elements[0].element_type == "image"
    assert "mineru" in result.tags


def test_mineru_processor_builds_expected_command(tmp_path: Path):
    config = ChaosConfig()
    config.mineru.backend = "hybrid-auto-engine"
    config.mineru.method = "auto"
    config.mineru.language = "en"
    config.mineru.model_source = "modelscope"
    config.mineru.api_url = "http://127.0.0.1:8000"

    processor = MinerUProcessor(config)
    command = processor._build_command(
        "/usr/local/bin/mineru",
        tmp_path / "paper.pdf",
        tmp_path / "out",
    )

    assert command[:5] == [
        "/usr/local/bin/mineru",
        "-p",
        str(tmp_path / "paper.pdf"),
        "-o",
        str(tmp_path / "out"),
    ]
    assert "--api-url" in command
    assert "http://127.0.0.1:8000" in command
    assert "--source" in command
    assert "modelscope" in command
    assert "-b" in command
    assert "hybrid-auto-engine" in command


@pytest.mark.asyncio
async def test_mineru_processor_falls_back_to_cli_when_api_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"fake")

    config = ChaosConfig(
        watch_folder=tmp_path,
        processed_folder=tmp_path / ".processed",
        failed_folder=tmp_path / ".failed",
    )
    processor = MinerUProcessor(config)

    async def no_api():
        return None

    async def fake_cli(command_path: str, file_path: Path, output_dir: Path) -> bool:
        export_dir = output_dir / file_path.stem / "auto"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / f"{file_path.stem}.md").write_text("# Paper\n\nBody", encoding="utf-8")
        return True

    monkeypatch.setattr(processor, "_ensure_api_base_url", no_api)
    monkeypatch.setattr(processor, "_resolve_command", lambda: "/usr/local/bin/mineru")
    monkeypatch.setattr(processor, "_invoke_mineru_cli", fake_cli)

    result = await processor.process(source)

    assert result is not None
    assert result.title == "Paper"
