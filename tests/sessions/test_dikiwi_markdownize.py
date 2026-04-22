from __future__ import annotations

from types import SimpleNamespace

import pytest

from aily.dikiwi.agents.data_agent import DataAgent
from aily.gating.drainage import RainDrop, RainType, StreamType
from aily.sessions.dikiwi_mind import DikiwiMind


@pytest.mark.asyncio
async def test_markdownize_drop_skips_prefetched_url_markdown():
    mind = DikiwiMind(graph_db=None, llm_client=None)
    drop = RainDrop(
        id="",
        rain_type=RainType.DOCUMENT,
        content="# Imported\n\nAlready fetched markdown with https://example.com/source",
        source="chaos_processor",
        stream_type=StreamType.EXTRACT_ANALYZE,
        metadata={
            "source_type": "url_markdown",
            "processing_method": "browser_url_markdown_fetch",
        },
    )

    result = await mind._markdownize_drop(drop)

    assert result.content == drop.content


@pytest.mark.asyncio
async def test_markdownize_drop_skips_existing_chaos_markdown():
    mind = DikiwiMind(graph_db=None, llm_client=None)
    drop = RainDrop(
        id="",
        rain_type=RainType.DOCUMENT,
        content="# Chaos Note\n\nConverted markdown with https://example.com/already-normalized",
        source="chaos_processor",
        stream_type=StreamType.EXTRACT_ANALYZE,
        metadata={"source_type": "chaos_markdown"},
    )

    result = await mind._markdownize_drop(drop)

    assert result.content == drop.content


@pytest.mark.asyncio
async def test_data_agent_skips_existing_chaos_markdown():
    drop = RainDrop(
        id="",
        rain_type=RainType.DOCUMENT,
        content="# Chaos Note\n\nConverted markdown with https://example.com/already-normalized",
        source="chaos_processor",
        stream_type=StreamType.EXTRACT_ANALYZE,
        metadata={"source_type": "chaos_markdown"},
    )
    ctx = SimpleNamespace(drop=drop)

    result = await DataAgent()._markdownize_drop(ctx)

    assert result.content == drop.content
