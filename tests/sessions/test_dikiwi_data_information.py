from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from aily.dikiwi.agents.context import AgentContext
from aily.dikiwi.agents.data_agent import DataAgent
from aily.dikiwi.agents.information_agent import InformationAgent
from aily.gating.drainage import RainDrop, RainType, StreamType
from aily.sessions.dikiwi_mind import DataPoint, DikiwiStage, StageResult


class FakeDataWriter:
    def __init__(self) -> None:
        self.data_calls: list[DataPoint] = []

    async def write_data_point_note(self, data_point: DataPoint, source: str, source_paths=None) -> str:
        self.data_calls.append(data_point)
        return f"data_note_for_{data_point.id}"


class FakeInfoWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[str] | None]] = []

    async def write_information_note(self, node, data_note_id: str, source: str, source_paths=None, data_point_id: str = "", data_note_ids=None) -> str:
        self.calls.append((data_point_id, data_note_id, data_note_ids))
        return f"information_note_for_{node.id}"


def _drop_with_visuals() -> RainDrop:
    return RainDrop(
        id="drop_visual",
        rain_type=RainType.DOCUMENT,
        content=(
            "Power analysis depends on representative vectors and signoff correlation. "
            "Teams repeatedly compare RTL estimates against downstream signoff behavior to understand "
            "whether the vectors are representative, whether the workload is realistic, and whether "
            "the extracted parasitics distort the final closure signal.\n\n"
            "The workflow also depends on visual evidence from correlation charts, timing overlays, "
            "and extraction comparison figures that explain where the divergence first appears."
        ),
        source="chaos_processor",
        stream_type=StreamType.EXTRACT_ANALYZE,
        metadata={
            "source_type": "chaos_markdown",
            "source_paths": ["/tmp/source.pdf"],
            "visual_elements": [
                {
                    "element_type": "figure",
                    "description": "Timing correlation chart comparing pre-route and post-route estimates",
                    "source_page": 7,
                    "asset_path": "images/figure1.png",
                }
            ],
            "chaos_visual_assets": [
                {
                    "asset_path": "images/figure1.png",
                    "wikilink": "![[00-Chaos/_assets/Doc/figure1.png]]",
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_data_agent_writes_atomic_data_notes_and_visual_datapoints():
    llm_client = SimpleNamespace(
        chat_json=AsyncMock(
            return_value={
                "title": "Vector Quality",
                "summary": "Representative vectors matter.",
                "data_points": [
                    {
                        "content": "Representative power vectors determine whether RTL power estimates correlate with signoff.",
                        "concept": "representative power vectors",
                        "context": "Observed in power analysis flow discussions.",
                        "confidence": 0.9,
                    }
                ],
            }
        )
    )
    writer = FakeDataWriter()
    ctx = AgentContext(
        pipeline_id="pipe_data",
        correlation_id="corr_data",
        drop=_drop_with_visuals(),
        llm_client=llm_client,
        dikiwi_obsidian_writer=writer,
    )

    result = await DataAgent().execute(ctx)

    assert result.success is True
    assert len(result.data["data_points"]) == 2
    assert len(writer.data_calls) == 2
    assert result.data["data_note_id_map"]
    visual_points = [dp for dp in result.data["data_points"] if dp.modality == "visual"]
    assert len(visual_points) == 1
    assert visual_points[0].asset_embeds == ["![[00-Chaos/_assets/Doc/figure1.png]]"]
    assert visual_points[0].source_page == 7


@pytest.mark.asyncio
async def test_information_agent_uses_data_point_note_mapping():
    writer = FakeInfoWriter()
    data_points = [
        DataPoint(id="dp_text", content="Text datum", source="chaos_processor", concept="text datum"),
        DataPoint(
            id="dp_visual",
            content="Visual datum",
            source="chaos_processor",
            concept="visual datum",
            modality="visual",
        ),
    ]
    ctx = AgentContext(
        pipeline_id="pipe_info",
        correlation_id="corr_info",
        drop=_drop_with_visuals(),
        dikiwi_obsidian_writer=writer,
    )
    ctx.stage_results = [
        StageResult(
            stage=DikiwiStage.DATA,
            success=True,
            data={
                "data_points": data_points,
                "data_note_id": "legacy_note_id",
                "data_note_ids": ["legacy_a", "legacy_b"],
                "data_note_id_map": {
                    "dp_text": "data_note_for_dp_text",
                    "dp_visual": "data_note_for_dp_visual",
                },
            },
        )
    ]

    agent = InformationAgent()
    agent._llm_cluster_batch = AsyncMock(
        return_value=[
            {
                "canonical_title": "correlated power evidence",
                "member_indices": [0, 1],
                "summary": "Text and visual datapoints jointly show correlated power evidence.",
                "tags": ["eda", "power"],
                "info_type": "evidence",
                "domain": "eda",
                "source_evidence": ["page 7"],
                "confidence": 0.89,
            }
        ]
    )

    result = await agent.execute(ctx)

    assert result.success is True
    assert len(result.data["information_nodes"]) == 1
    assert writer.calls == [
        ("dp_text", "data_note_for_dp_text", ["data_note_for_dp_text", "data_note_for_dp_visual"]),
    ]
