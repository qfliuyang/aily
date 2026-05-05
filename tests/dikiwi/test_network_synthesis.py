from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from aily.dikiwi.network_synthesis import NetworkSynthesisSelector, candidate_nodes_to_information
from aily.graph.db import GraphDB
from aily.sessions.dikiwi_mind import InformationNode, KnowledgeLink


@pytest.fixture
async def graph_db(tmp_path: Path):
    db = GraphDB(tmp_path / "graph.db")
    await db.initialize()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_network_selector_triggers_on_changed_tag_neighborhood(graph_db: GraphDB):
    await graph_db.insert_node("info_old", "information", "CDC verification misses async crossings", "doc-a")
    await graph_db.insert_node("info_new_1", "information", "STA constraints hide CDC risk", "doc-b")
    await graph_db.insert_node("info_new_2", "information", "EDA signoff needs constraint lineage", "doc-b")
    await graph_db.insert_node("tag_cdc-signoff", "tag", "cdc-signoff", "dikiwi")

    for node_id in ["info_old", "info_new_1", "info_new_2"]:
        await graph_db.insert_edge(f"edge_{node_id}", node_id, "tag_cdc-signoff", "has_tag", 1.0, "dikiwi")
    await graph_db.insert_edge("edge_old_new", "info_old", "info_new_1", "supports", 0.8, "dikiwi")
    await graph_db.set_node_property("info_old", "tags", ["cdc-signoff"])
    await graph_db.set_node_property("info_old", "domain", "semiconductor")
    await graph_db.set_node_property("info_old", "source_paths", ["doc-a.pdf"])
    await graph_db.set_node_property("info_new_1", "tags", ["cdc-signoff"])
    await graph_db.set_node_property("info_new_1", "domain", "semiconductor")
    await graph_db.set_node_property("info_new_1", "source_paths", ["doc-b.pdf"])
    await graph_db.set_node_property("info_new_2", "tags", ["cdc-signoff"])
    await graph_db.set_node_property("info_new_2", "domain", "semiconductor")
    await graph_db.set_node_property("info_new_2", "source_paths", ["doc-b.pdf"])

    ctx = SimpleNamespace(graph_db=graph_db)
    current_nodes = [
        InformationNode("info_new_1", "dp1", "STA constraints hide CDC risk", ["cdc-signoff"], "fact", "semiconductor"),
        InformationNode("info_new_2", "dp2", "EDA signoff needs constraint lineage", ["cdc-signoff"], "fact", "semiconductor"),
    ]
    current_links = [
        KnowledgeLink("info_new_1", "info_new_2", "enables", 0.8, "Constraint lineage enables signoff.")
    ]

    assessment = await NetworkSynthesisSelector(min_nodes=3, trigger_score=3.0).assess(
        ctx,
        current_nodes,
        current_links,
    )

    assert assessment.triggered is True
    assert assessment.candidates
    assert assessment.candidates[0].anchor_label == "cdc-signoff"
    assert all(node["type"] == "information" for node in assessment.candidates[0].nodes)
    assert all(edge["relation_type"] != "has_tag" for edge in assessment.candidates[0].edges)
    network_nodes = candidate_nodes_to_information(assessment.candidates)
    assert {node.id for node in network_nodes} >= {"info_old", "info_new_1", "info_new_2"}


@pytest.mark.asyncio
async def test_network_selector_blocks_weak_graph_change(graph_db: GraphDB):
    await graph_db.insert_node("info_new_1", "information", "One isolated fact", "doc-c")
    await graph_db.insert_node("tag_lonely", "tag", "lonely", "dikiwi")
    await graph_db.insert_edge("edge_lonely", "info_new_1", "tag_lonely", "has_tag", 1.0, "dikiwi")

    ctx = SimpleNamespace(graph_db=graph_db)
    current_nodes = [
        InformationNode("info_new_1", "dp1", "One isolated fact", ["lonely"], "fact", "general")
    ]

    assessment = await NetworkSynthesisSelector(min_nodes=3, trigger_score=3.0).assess(
        ctx,
        current_nodes,
        [],
    )

    assert assessment.triggered is False
    assert "minimum" in assessment.reason or "below threshold" in assessment.reason


@pytest.mark.asyncio
async def test_network_selector_ignores_page_nodes_and_bookkeeping_tags(graph_db: GraphDB):
    await graph_db.insert_node("info_page", "information", "Page 1", "doc-a")
    await graph_db.insert_node("info_real", "information", "IR drop hotspots need vector-aware screening", "doc-a")
    await graph_db.insert_node("tag_eda", "tag", "eda", "dikiwi")
    await graph_db.insert_edge("edge_page_tag", "info_page", "tag_eda", "has_tag", 1.0, "dikiwi")
    await graph_db.insert_edge("edge_real_tag", "info_real", "tag_eda", "has_tag", 1.0, "dikiwi")
    await graph_db.set_node_property("info_page", "tags", ["eda"])
    await graph_db.set_node_property("info_real", "tags", ["eda"])

    ctx = SimpleNamespace(graph_db=graph_db)
    assessment = await NetworkSynthesisSelector(min_nodes=2, trigger_score=1.0).assess(
        ctx,
        [InformationNode("info_real", "dp1", "IR drop hotspots need vector-aware screening", ["eda"], "fact", "eda")],
        [],
    )

    assert assessment.triggered is False
    assert assessment.candidates == []
