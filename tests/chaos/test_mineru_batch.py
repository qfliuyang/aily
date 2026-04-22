from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aily.chaos.mineru_batch import MinerUChaosBatchRunner, chaos_base_name
from aily.chaos.types import ExtractedContentMultimodal, VisualElement


def test_discover_files_filters_supported_inputs(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "doc1.pdf").write_text("x", encoding="utf-8")
    (source / "slides.pptx").write_text("x", encoding="utf-8")
    (source / "note.md").write_text("x", encoding="utf-8")
    (source / ".processed").mkdir()
    (source / ".processed" / "old.pdf").write_text("x", encoding="utf-8")
    (source / ".hidden.pdf").write_text("x", encoding="utf-8")

    runner = MinerUChaosBatchRunner(
        source_folder=source,
        vault_path=tmp_path / "vault",
        run_dikiwi=False,
    )

    files = runner.discover_files()

    assert [path.name for path in files] == ["doc1.pdf", "slides.pptx"]


def test_chaos_base_name_prefers_metadata():
    extracted = ExtractedContentMultimodal(
        text="body",
        title="Title",
        source_type="pdf",
        source_path=Path("/tmp/source.pdf"),
        metadata={"chaos_base_name": "stable_name"},
        processing_timestamp=datetime(2026, 4, 18, 12, 0, 0),
    )

    assert chaos_base_name(extracted, Path("/tmp/source.pdf")) == "stable_name"


def test_chaos_base_name_ignores_filename_default():
    extracted = ExtractedContentMultimodal(
        text="# Semantic Constraint Verification\n\nBody",
        title="Semantic Constraint Verification",
        source_type="pdf",
        source_path=Path("/tmp/source.pdf"),
        metadata={"chaos_base_name": "source"},
        processing_timestamp=datetime(2026, 4, 18, 12, 0, 0),
    )

    assert chaos_base_name(extracted, Path("/tmp/source.pdf")) == "Semantic_Constraint_Verification"


def test_chaos_base_name_skips_generic_title():
    extracted = ExtractedContentMultimodal(
        text="# Agenda\n\n# IR Driven Placement Optimization\n\nBody",
        title="Agenda",
        source_type="pdf",
        source_path=Path("/tmp/b1-04-redhawk-pres-user.pdf"),
        metadata={},
        processing_timestamp=datetime(2026, 4, 18, 12, 0, 0),
    )

    assert chaos_base_name(extracted, Path("/tmp/b1-04-redhawk-pres-user.pdf")) == "IR_Driven_Placement_Optimization"


def test_batch_runner_writes_transcript_with_stable_name(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    runner = MinerUChaosBatchRunner(
        source_folder=source,
        vault_path=tmp_path / "vault",
        processed_folder=tmp_path / ".processed",
        run_dikiwi=False,
    )

    extracted = ExtractedContentMultimodal(
        text="Structured body",
        title="Imported Title",
        source_type="pdf",
        source_path=source / "paper.pdf",
        metadata={"chaos_base_name": "paper_stable"},
        processing_timestamp=datetime(2026, 4, 18, 12, 0, 0),
    )

    transcript_path = runner._write_chaos_transcript(extracted, source / "paper.pdf")

    assert transcript_path.name == "paper_stable.md"
    content = transcript_path.read_text(encoding="utf-8")
    assert "# Imported Title" in content
    assert "**Original File:** paper.pdf" in content


def test_batch_runner_embeds_visual_assets_in_chaos_transcript(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    export_dir = tmp_path / ".processed" / ".mineru_cache" / "paper_hash" / "paper" / "auto"
    image_dir = export_dir / "images"
    image_dir.mkdir(parents=True)
    image_path = image_dir / "figure1.jpg"
    image_path.write_bytes(b"fake-image")

    runner = MinerUChaosBatchRunner(
        source_folder=source,
        vault_path=tmp_path / "vault",
        processed_folder=tmp_path / ".processed",
        run_dikiwi=False,
    )

    extracted = ExtractedContentMultimodal(
        text="Structured body",
        title="Imported Title",
        source_type="mineru_markdown",
        source_path=source / "paper.pdf",
        metadata={
            "chaos_base_name": "paper_stable",
            "mineru_output_dir": str(export_dir),
        },
        visual_elements=[
            VisualElement(
                element_id="figure_1",
                element_type="image",
                description="Figure 1",
                asset_path="images/figure1.jpg",
            )
        ],
        processing_timestamp=datetime(2026, 4, 18, 12, 0, 0),
    )

    transcript_path = runner._write_chaos_transcript(extracted, source / "paper.pdf")

    asset_copy = tmp_path / "vault" / "00-Chaos" / "_assets" / "paper_stable" / "figure1.jpg"
    assert asset_copy.exists()
    content = transcript_path.read_text(encoding="utf-8")
    assert "## Visual Assets" in content
    assert "![[00-Chaos/_assets/paper_stable/figure1.jpg]]" in content


async def test_batch_runner_extracts_all_before_batched_dikiwi(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    file_a = source / "a.pdf"
    file_b = source / "b.pdf"
    file_a.write_text("x", encoding="utf-8")
    file_b.write_text("x", encoding="utf-8")

    runner = MinerUChaosBatchRunner(
        source_folder=source,
        vault_path=tmp_path / "vault",
        processed_folder=tmp_path / ".processed",
        run_dikiwi=True,
    )

    async def fake_process(path: Path):
        return ExtractedContentMultimodal(
            text=f"body for {path.name}",
            title=path.stem.upper(),
            source_type="pdf",
            source_path=path,
            metadata={},
            processing_timestamp=datetime(2026, 4, 18, 12, 0, 0),
        )

    bridge = SimpleNamespace(
        process_extracted_content_batch=AsyncMock(
            return_value={
                "results": [
                    {"stage": "KNOWLEDGE", "zettels_created": 1, "insights": 0, "source_path": str(file_a)},
                    {"stage": "INSIGHT", "zettels_created": 2, "insights": 1, "source_path": str(file_b)},
                ]
            }
        )
    )

    runner.processor.process = AsyncMock(side_effect=fake_process)
    runner._bridge = bridge
    runner.initialize = AsyncMock(return_value=None)

    summary = await runner.run(files=[file_a, file_b])

    assert summary.processed == 2
    assert summary.failed == 0
    assert [item.stage for item in summary.results] == ["KNOWLEDGE", "INSIGHT"]
    assert [item.zettels_created for item in summary.results] == [1, 2]
    bridge.process_extracted_content_batch.assert_awaited_once()
