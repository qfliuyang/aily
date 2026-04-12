from __future__ import annotations

import pytest

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
