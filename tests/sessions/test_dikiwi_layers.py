from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from aily.gating.drainage import RainDrop, RainType, StreamType
from aily.sessions.dikiwi_mind import DataPoint, DikiwiMind, InformationNode, KnowledgeLink, Insight
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter


@pytest.mark.asyncio
async def test_layered_zettels_write_levels_to_vault():
    with TemporaryDirectory() as tmpdir:
        writer = DikiwiObsidianWriter(vault_path=Path(tmpdir), zettelkasten_only=True)
        mind = DikiwiMind(graph_db=None, llm_client=None, dikiwi_obsidian_writer=writer)
        drop = RainDrop(
            id="",
            rain_type=RainType.DOCUMENT,
            content="raw source",
            source="chaos_processor",
            stream_type=StreamType.EXTRACT_ANALYZE,
            metadata={"source_paths": ["/tmp/source.pdf"]},
        )

        await mind._write_data_zettels(
            [DataPoint(id="dp1", content="Architecture choices constrain later optimization.", source="chaos_processor", confidence=0.9)],
            drop,
        )
        await mind._write_information_zettels(
            [InformationNode(id="i1", data_point_id="dp1", content="Architecture choices constrain later optimization.", tags=["architecture"], info_type="fact", domain="semiconductor")],
            drop,
        )
        await mind._write_knowledge_zettels(
            [KnowledgeLink(source_id="i1", target_id="i2", relation_type="leads_to", strength=0.8)],
            [
                InformationNode(id="i1", data_point_id="dp1", content="Architecture choices constrain later optimization.", tags=["architecture"], info_type="fact", domain="semiconductor"),
                InformationNode(id="i2", data_point_id="dp2", content="Constraint models determine downstream closure strategies.", tags=["constraints"], info_type="fact", domain="semiconductor"),
            ],
            drop,
        )
        await mind._write_insight_zettels(
            [Insight(id="s1", insight_type="pattern", description="Early architecture and later closure are tightly coupled.", confidence=0.82)],
            [],
            drop,
        )

        notes = sorted(Path(tmpdir).rglob("*.md"))
        text = "\n".join(p.read_text(encoding="utf-8") for p in notes)
        assert 'dikiwi_level: "data"' in text
        assert 'dikiwi_level: "information"' in text
        assert 'dikiwi_level: "knowledge"' in text
        assert 'dikiwi_level: "insight"' in text
        assert "/tmp/source.pdf" in text
