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
