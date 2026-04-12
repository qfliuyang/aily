import pytest
from aily.graph.db import GraphDB


@pytest.fixture
async def graph_db(tmp_path):
    db = GraphDB(tmp_path / "aily_graph.db")
    await db.initialize()
    return db


@pytest.mark.asyncio
async def test_insert_node_and_query(graph_db):
    await graph_db.insert_node("n1", "person", "Alice", "test")
    nodes = await graph_db.get_nodes_by_type("person")
    assert len(nodes) == 1
    assert nodes[0]["label"] == "Alice"


@pytest.mark.asyncio
async def test_insert_edge_and_cooccurrence(graph_db):
    await graph_db.insert_node("n1", "topic", "AI", "test")
    await graph_db.insert_node("n2", "topic", "Chips", "test")
    await graph_db.insert_edge("e1", "n1", "n2", "related", 1.0, "test")
    await graph_db.insert_occurrence("o1", "n1", "log-1")
    await graph_db.insert_occurrence("o2", "n2", "log-1")
    co = await graph_db.get_cooccurring_nodes("log-1")
    assert len(co) == 2
    labels = {n["label"] for n in co}
    assert labels == {"AI", "Chips"}


@pytest.mark.asyncio
async def test_get_nodes_within_hours(graph_db):
    await graph_db.insert_node("n1", "person", "Alice", "test")
    nodes = await graph_db.get_nodes_within_hours(24)
    assert len(nodes) == 1
    assert nodes[0]["id"] == "n1"
    assert nodes[0]["label"] == "Alice"


@pytest.mark.asyncio
async def test_get_edges_within_hours(graph_db):
    await graph_db.insert_node("n1", "topic", "AI", "test")
    await graph_db.insert_node("n2", "topic", "Chips", "test")
    await graph_db.insert_edge("e1", "n1", "n2", "related", 1.0, "test")
    edges = await graph_db.get_edges_within_hours(24)
    assert len(edges) == 1
    assert edges[0]["id"] == "e1"
    assert edges[0]["relation_type"] == "related"


@pytest.mark.asyncio
async def test_get_top_nodes_by_edge_count(graph_db):
    await graph_db.insert_node("n1", "topic", "AI", "test")
    await graph_db.insert_node("n2", "topic", "Chips", "test")
    await graph_db.insert_node("n3", "topic", "Robots", "test")
    await graph_db.insert_edge("e1", "n1", "n2", "related", 1.0, "test")
    await graph_db.insert_edge("e2", "n1", "n3", "related", 0.5, "test")
    top = await graph_db.get_top_nodes_by_edge_count(limit=10)
    assert len(top) == 3
    # n1 has 2 edges, n2 and n3 have 1 each
    assert top[0]["id"] == "n1"
    assert top[0]["edge_count"] == 2
    assert top[1]["edge_count"] == 1
    assert top[2]["edge_count"] == 1


@pytest.mark.asyncio
async def test_get_collisions_within_hours(graph_db):
    await graph_db.insert_node("n1", "topic", "AI", "test")
    await graph_db.insert_occurrence("o1", "n1", "log-a")
    await graph_db.insert_occurrence("o2", "n1", "log-b")
    collisions = await graph_db.get_collisions_within_hours(24, min_occurrences=2)
    assert len(collisions) == 1
    assert collisions[0]["node_id"] == "n1"
    assert collisions[0]["occurrence_count"] == 2


@pytest.mark.asyncio
async def test_get_source_logs_for_node(graph_db):
    await graph_db.insert_node("n1", "topic", "AI", "test")
    await graph_db.insert_occurrence("o1", "n1", "log-1")
    sources = await graph_db.get_source_logs_for_node("n1")
    assert len(sources) == 1
    assert sources[0]["raw_log_id"] == "log-1"
