from __future__ import annotations

from types import SimpleNamespace

import pytest

from aily.sessions.dikiwi_mind import DikiwiMind, InformationNode, Insight


class FakeLLMClient:
    async def chat_json(self, messages, temperature=0.0):
        return {
            "zettels": [
                {
                    "title": "Constraint-Aware Chip Design Requires Early Architecture Decisions",
                    "content": "Architecture decisions front-load the design space and determine later optimization ceilings. A useful permanent note should preserve that mechanism rather than summarize the whole deck.",
                    "tags": ["architecture", "chip-design"],
                    "links_to": ["Timing Closure Depends on Early Constraint Modeling"],
                    "confidence": 0.88,
                }
            ]
        }


@pytest.mark.asyncio
async def test_wisdom_can_generate_zettels_without_insights():
    mind = DikiwiMind(graph_db=None, llm_client=FakeLLMClient())

    info_nodes = [
        InformationNode(
            id="n1",
            data_point_id="d1",
            content="Architecture determines the downstream physical optimization options in chip design.",
            tags=["architecture"],
            info_type="fact",
            domain="semiconductor",
        )
    ]

    result = await mind._stage_wisdom(
        insights=[],
        info_nodes=info_nodes,
        drop=SimpleNamespace(source="test-source", metadata={}),
        memory=None,
    )

    assert result.success is True
    assert len(result.data["zettels"]) == 1
