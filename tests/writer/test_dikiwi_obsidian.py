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

    index_path = tmp_path / "00-Chaos" / "00 Zettelkasten Index.md"
    assert note_path.exists()
    assert index_path.exists()
    assert not (tmp_path / "99-MOC" / "attention.md").exists()

    content = note_path.read_text(encoding="utf-8")
    assert "aliases:" in content
    assert 'note_type: "permanent"' in content
    assert 'dikiwi_level: "knowledge"' in content
    assert 'source_paths:' in content
    assert '/Users/luzi/aily_chaos/slide1.png' in content
    assert '"knowledge"' in content
    assert "[[Focus Switching Multiplies Coordination Cost]]" in content
    assert "## Concept Neighborhood" not in content
    assert "[[99-MOC/attention|#attention]]" not in content
    assert "[[99-MOC/productivity|#productivity]]" not in content
    assert 'semantic_topics:' in content

    index = index_path.read_text(encoding="utf-8")
    assert 'WHERE note_type = "permanent"' in index
    assert 'FROM "/"' in index
    assert 'FROM "99-MOC"' in index


@pytest.mark.asyncio
async def test_relation_labels_do_not_become_graph_topic_nodes(tmp_path):
    writer = DikiwiObsidianWriter(vault_path=tmp_path, zettelkasten_only=True)

    class Link:
        source_id = "info_a"
        target_id = "info_b"
        relation_type = "example_of"
        strength = 0.9
        reasoning = "A is an example of B."

    class Node:
        def __init__(self, content: str) -> None:
            self.content = content

    await writer.write_knowledge_note(
        Link(),
        Node("Specific buffering failure mode"),
        Node("Broader constraint propagation issue"),
        "information_a",
        "information_b",
        "test",
    )

    note = next((tmp_path / "03-Knowledge").glob("**/*.md"))
    text = note.read_text(encoding="utf-8")

    assert 'relation: "example_of"' in text
    assert '- "example_of"' not in text
    assert 'semantic_topics:' not in text
    assert "[[99-MOC/example_of|#example_of]]" not in text
    assert not (tmp_path / "99-MOC" / "example_of.md").exists()


@pytest.mark.asyncio
async def test_human_titles_are_not_truncated_in_written_notes(tmp_path):
    writer = DikiwiObsidianWriter(vault_path=tmp_path, zettelkasten_only=False)

    long_insight = (
        "This insight title should remain fully intact without any artificial truncation "
        "because shortening it changes the meaning of the conclusion"
    )
    long_wisdom = (
        "This wisdom principle should remain fully intact without any artificial truncation "
        "because shortening it changes the meaning of the principle"
    )
    long_impact = (
        "This impact proposal should remain fully intact without any artificial truncation "
        "because shortening it changes the meaning of the action"
    )

    class Insight:
        insight_type = "pattern"
        description = long_insight
        confidence = 0.9

    insight_paths = await writer.write_insights("msg1", [Insight()], "Source Note")
    wisdom_paths = await writer.write_wisdom(
        "msg2",
        [{"principle": long_wisdom, "context": "", "implications": []}],
    )
    impact_paths = await writer.write_impact(
        "msg3",
        [{"proposal": long_impact, "rationale": "Because it matters.", "expected_outcome": "Clarity"}],
    )

    insight_text = insight_paths[0].read_text(encoding="utf-8")
    wisdom_text = wisdom_paths[0].read_text(encoding="utf-8")
    impact_text = impact_paths[0].read_text(encoding="utf-8")

    assert f"# 🔍 Pattern: {long_insight}" in insight_text
    assert f"# 🧠 Principle: {long_wisdom}" in wisdom_text
    assert f"# 🚀 Proposal: {long_impact}" in impact_text


@pytest.mark.asyncio
async def test_reactor_notes_route_to_07_proposal(tmp_path):
    writer = DikiwiObsidianWriter(vault_path=tmp_path, zettelkasten_only=False)

    path = await writer.write_note(
        title="Innovation: Timing Closure Copilot",
        markdown="# Proposal\n\nDetails",
        source_url="aily://reactor/2026-04-22/0",
    )

    note_path = Path(path)
    assert note_path.parent.parent == tmp_path / "07-Proposal"
    assert note_path.exists()
