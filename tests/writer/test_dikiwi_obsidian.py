from __future__ import annotations

from pathlib import Path

import pytest

from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter


@pytest.mark.asyncio
async def test_write_zettel_creates_obsidian_management_notes(tmp_path):
    writer = DikiwiObsidianWriter(vault_path=tmp_path, zettelkasten_only=True)

    note_path = await writer.write_zettel(
        zettel_id="z123abc",
        title="Attention Is a Budget, Not a Background Resource",
        content="Attention behaves like a limited budget. Systems that ignore this create hidden costs.",
        tags=["attention", "productivity"],
        links_to=["Focus Switching Multiplies Coordination Cost"],
        source="chaos_processor",
        source_paths=["/Users/luzi/aily_chaos/slide1.png", "/Users/luzi/aily_chaos/slide2.png"],
        dikiwi_level="knowledge",
    )

    index_path = tmp_path / "3-Resources" / "Zettelkasten" / "00 Zettelkasten Index.md"
    moc_path = tmp_path / "3-Resources" / "MOCs" / "attention.md"

    assert note_path.exists()
    assert index_path.exists()
    assert moc_path.exists()

    content = note_path.read_text(encoding="utf-8")
    assert "aliases:" in content
    assert 'note_type: "permanent"' in content
    assert 'dikiwi_level: "knowledge"' in content
    assert 'source_paths:' in content
    assert '/Users/luzi/aily_chaos/slide1.png' in content
    assert "  - knowledge" in content
    assert "[[Focus Switching Multiplies Coordination Cost]]" in content

    index = index_path.read_text(encoding="utf-8")
    assert 'WHERE note_type = "permanent"' in index
    assert 'FROM "3-Resources/MOCs"' in index

    moc = moc_path.read_text(encoding="utf-8")
    assert "# attention" in moc
    assert 'contains(tags, "attention")' in moc
