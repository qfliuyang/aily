from __future__ import annotations

from datetime import datetime
from pathlib import Path

from aily.chaos.mineru_batch import MinerUChaosBatchRunner, chaos_base_name
from aily.chaos.types import ExtractedContentMultimodal


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
