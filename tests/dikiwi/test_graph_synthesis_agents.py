from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from aily.dikiwi.agents.context import AgentContext
from aily.dikiwi.agents.impact_agent import ImpactAgent
from aily.dikiwi.agents.insight_agent import InsightAgent
from aily.dikiwi.agents.wisdom_agent import WisdomAgent
from aily.dikiwi.network_synthesis import NetworkSynthesisSelector, SubgraphCandidate
from aily.gating.drainage import RainDrop, RainType, StreamType
from aily.sessions.dikiwi_mind import (
    DikiwiStage,
    InformationNode,
    Insight,
    KnowledgeLink,
    StageResult,
    ZettelkastenNote,
)


@dataclass
class WriterCall:
    item: Any
    source_paths: list[str] | None


class FakeDikiwiWriter:
    def __init__(self) -> None:
        self.insight_calls: list[WriterCall] = []
        self.wisdom_calls: list[WriterCall] = []
        self.impact_calls: list[WriterCall] = []
        self.registered: list[tuple[str, str]] = []

    async def write_insight_note(
        self,
        insight: Insight,
        knowledge_note_ids: list[str],
        drop: RainDrop,
        source_paths: list[str] | None = None,
    ) -> str:
        self.insight_calls.append(WriterCall(insight, source_paths))
        return f"note_{insight.id}"

    def register_note_title(self, note_id: str, title: str) -> None:
        self.registered.append((note_id, title))

    async def write_wisdom_note(
        self,
        zettel: ZettelkastenNote,
        insight_note_ids: list[str],
        drop: RainDrop,
        source_paths: list[str] | None = None,
        link_map: dict[str, str] | None = None,
    ) -> str:
        self.wisdom_calls.append(WriterCall(zettel, source_paths))
        return f"note_{zettel.id}"

    async def write_impact_note(
        self,
        impact: dict[str, Any],
        wisdom_note_ids: list[str],
        drop: RainDrop,
        source_paths: list[str] | None = None,
    ) -> str:
        self.impact_calls.append(WriterCall(impact, source_paths))
        return "note_impact"


class FakeGraphDB:
    async def get_top_nodes_by_edge_count(self, limit: int = 15) -> list[dict[str, Any]]:
        return [
            {
                "id": "info_center",
                "type": "information",
                "label": "Constraint lineage connects CDC, STA, and signoff closure.",
                "edge_count": 12,
                "total_weight": 9.4,
            },
            {
                "id": "tag_eda",
                "type": "tag",
                "label": "eda",
                "edge_count": 30,
                "total_weight": 30.0,
            },
        ]


def _drop() -> RainDrop:
    return RainDrop(
        id="drop_pdf",
        rain_type=RainType.DOCUMENT,
        content="raw pdf text",
        source="chaos_processor",
        stream_type=StreamType.EXTRACT_ANALYZE,
        metadata={"source_paths": ["/tmp/original.pdf"]},
    )


def _nodes() -> list[InformationNode]:
    return [
        InformationNode(
            id="info_a",
            data_point_id="dp_a",
            content="STA constraints can hide CDC risk.",
            tags=["eda"],
            info_type="claim",
            domain="eda",
        ),
        InformationNode(
            id="info_b",
            data_point_id="dp_b",
            content="Constraint lineage exposes why downstream closure fails.",
            tags=["eda"],
            info_type="claim",
            domain="eda",
        ),
        InformationNode(
            id="info_c",
            data_point_id="dp_c",
            content="Closure debugging improves when CDC, STA, and signoff evidence share lineage.",
            tags=["eda"],
            info_type="claim",
            domain="eda",
        ),
    ]


def _candidate() -> SubgraphCandidate:
    return SubgraphCandidate(
        id="subgraph_eda",
        anchor_id="tag_eda",
        anchor_label="eda",
        anchor_type="tag",
        reason="new EDA nodes connected to existing verification neighborhood",
        score=5.5,
        nodes=[
            {"id": "info_a", "type": "information", "label": "STA constraints can hide CDC risk."},
            {
                "id": "info_b",
                "type": "information",
                "label": "Constraint lineage exposes downstream closure failures.",
            },
            {
                "id": "info_c",
                "type": "information",
                "label": "Closure debugging improves when evidence shares lineage.",
            },
        ],
        edges=[
            {
                "id": "edge_ab",
                "source_node_id": "info_a",
                "target_node_id": "info_b",
                "relation_type": "reveals",
                "weight": 0.9,
            },
            {
                "id": "edge_bc",
                "source_node_id": "info_b",
                "target_node_id": "info_c",
                "relation_type": "enables",
                "weight": 0.86,
            }
        ],
        changed_node_ids=["info_b"],
    )


def _ctx(*, writer: FakeDikiwiWriter | None = None, graph_db: Any | None = None) -> AgentContext:
    return AgentContext(
        pipeline_id="pipe",
        correlation_id="corr",
        drop=_drop(),
        dikiwi_obsidian_writer=writer,
        graph_db=graph_db,
    )


@pytest.mark.asyncio
async def test_insight_does_not_fallback_to_pdf_local_information(monkeypatch):
    writer = FakeDikiwiWriter()
    ctx = _ctx(writer=writer)
    ctx.stage_results = [
        StageResult(stage=DikiwiStage.INFORMATION, success=True, data={"information_nodes": _nodes()}),
        StageResult(
            stage=DikiwiStage.KNOWLEDGE,
            success=True,
            data={
                "links": [KnowledgeLink("info_a", "info_b", "reveals", 0.9, "A reveals B")],
                "knowledge_note_ids": ["knowledge_ab"],
                "subgraph_candidates": [],
                "network_nodes": [],
            },
        ),
    ]

    async def fail_if_called(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("Insight LLM must not run without graph subgraph candidates")

    monkeypatch.setattr("aily.dikiwi.agents.insight_agent.multi_agent_json", fail_if_called)

    result = await InsightAgent().execute(ctx)

    assert result.success is True
    assert result.items_output == 0
    assert writer.insight_calls == []


@pytest.mark.asyncio
async def test_network_synthesis_does_not_bootstrap_from_current_drop_without_graph():
    assessment = await NetworkSynthesisSelector(min_nodes=2, trigger_score=1.0).assess(
        _ctx(graph_db=None),
        _nodes(),
        [KnowledgeLink("info_a", "info_b", "reveals", 0.9, "A reveals B")],
    )

    assert assessment.triggered is False
    assert assessment.candidates == []
    assert assessment.metrics["requires_persisted_graph"] is True


@pytest.mark.asyncio
async def test_insight_is_written_from_graph_paths_without_source_paths(monkeypatch):
    writer = FakeDikiwiWriter()
    candidate = _candidate()
    ctx = _ctx(writer=writer)
    ctx.stage_results = [
        StageResult(stage=DikiwiStage.INFORMATION, success=True, data={"information_nodes": _nodes()}),
        StageResult(
            stage=DikiwiStage.KNOWLEDGE,
            success=True,
            data={
                "links": [KnowledgeLink("info_a", "info_b", "reveals", 0.9, "A reveals B")],
                "knowledge_note_ids": ["knowledge_ab"],
                "subgraph_candidates": [candidate],
                "network_nodes": _nodes(),
                "network_context": candidate.to_prompt_context(),
            },
        ),
    ]

    async def fake_multi_agent_json(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "insights": [
                {
                    "type": "pattern",
                    "description": "Constraint lineage becomes visible only by walking the STA to closure path.",
                    "related_evidence": ["E1", "E2"],
                    "confidence": 0.82,
                }
            ]
        }

    monkeypatch.setattr("aily.dikiwi.agents.insight_agent.multi_agent_json", fake_multi_agent_json)

    result = await InsightAgent().execute(ctx)

    assert result.success is True
    assert result.items_output == 1
    assert writer.insight_calls[0].source_paths is None
    insight = writer.insight_calls[0].item
    assert insight.related_nodes == ["info_a", "info_b"]
    assert insight.graph_provenance["mode"] == "short_information_paths"
    assert insight.graph_provenance["subgraph_ids"] == ["subgraph_eda"]


@pytest.mark.asyncio
async def test_wisdom_requires_graph_candidates_and_writes_graph_provenance(monkeypatch):
    writer = FakeDikiwiWriter()
    candidate = _candidate()
    ctx = _ctx(writer=writer)
    ctx.stage_results = [
        StageResult(stage=DikiwiStage.INFORMATION, success=True, data={"information_nodes": _nodes()}),
        StageResult(
            stage=DikiwiStage.KNOWLEDGE,
            success=True,
            data={"network_nodes": _nodes()},
        ),
        StageResult(
            stage=DikiwiStage.INSIGHT,
            success=True,
            data={
                "insights": [
                    Insight(
                        id="insight_1",
                        insight_type="pattern",
                        description="The path connects constraint hiding to closure failure.",
                    )
                ],
                "insight_note_ids": ["insight_1"],
                "subgraph_candidates": [candidate],
            },
        ),
    ]

    async def fake_chat_json(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "zettels": [
                {
                    "title": "Constraint lineage turns hidden verification risk into an inspectable path",
                    "content": "Constraint lineage matters because it lets teams inspect why one verification assumption affects downstream closure. "
                    "When the path is explicit, CDC, STA, and signoff are no longer separate checklists but connected evidence. "
                    "That connection supports better debugging, prioritization, and tool insertion decisions.",
                    "tags": ["eda", "constraints"],
                    "links_to": [],
                    "confidence": 0.84,
                }
            ]
        }

    monkeypatch.setattr("aily.dikiwi.agents.wisdom_agent.chat_json", fake_chat_json)

    result = await WisdomAgent().execute(ctx)

    assert result.success is True
    assert result.items_output == 1
    assert writer.wisdom_calls[0].source_paths is None
    zettel = writer.wisdom_calls[0].item
    assert zettel.source == "dikiwi_graph"
    assert zettel.graph_provenance["mode"] == "long_information_paths"


@pytest.mark.asyncio
async def test_impact_requires_information_center_nodes_and_writes_graph_provenance(monkeypatch):
    writer = FakeDikiwiWriter()
    ctx = _ctx(writer=writer, graph_db=FakeGraphDB())
    ctx.stage_results = [
        StageResult(
            stage=DikiwiStage.WISDOM,
            success=True,
            data={
                "zettels": [
                    ZettelkastenNote(
                        id="z1",
                        title="Constraint lineage is a workflow insertion point",
                        content="A durable note about EDA workflow insertion.",
                    )
                ],
                "wisdom_note_ids": ["wisdom_z1"],
            },
        )
    ]

    async def fake_multi_agent_json(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "impacts": [
                {
                    "type": "proposal_seed",
                    "description": "Prototype a constraint-lineage copilot for CDC-to-signoff debugging.",
                    "priority": "high",
                    "rationale": "The center node has many graph connections and exposes a workflow wedge.",
                    "effort_estimate": "medium",
                }
            ]
        }

    monkeypatch.setattr("aily.dikiwi.agents.impact_agent.multi_agent_json", fake_multi_agent_json)

    result = await ImpactAgent().execute(ctx)

    assert result.success is True
    assert result.items_output == 1
    assert writer.impact_calls[0].source_paths is None
    impact = writer.impact_calls[0].item
    assert impact["graph_provenance"]["mode"] == "high_connectivity_center_nodes"
    assert impact["graph_provenance"]["center_node_ids"] == ["info_center"]
