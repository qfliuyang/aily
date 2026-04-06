import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import date

from aily.digest.pipeline import DigestPipeline


@pytest.fixture
def pipeline():
    graph_db = AsyncMock()
    queue_db = AsyncMock()
    llm = AsyncMock()
    writer = AsyncMock()
    pusher = AsyncMock()
    return DigestPipeline(graph_db, queue_db, llm, writer, pusher)


@pytest.mark.asyncio
async def test_run_happy_path(pipeline):
    pipeline.graph_db.get_top_nodes_by_edge_count = AsyncMock(return_value=[{"id": "n1", "type": "topic", "label": "AI", "edge_count": 2}])
    pipeline.graph_db.get_collisions_within_hours = AsyncMock(return_value=[{"node_id": "n1", "type": "topic", "label": "AI", "occurrence_count": 2}])
    pipeline.graph_db.get_nodes_within_hours = AsyncMock(return_value=[{"id": "n1"}])
    pipeline.graph_db.get_edges_within_hours = AsyncMock(return_value=[{"id": "e1"}])
    pipeline.graph_db.get_source_logs_for_node = AsyncMock(return_value=[{"raw_log_id": "log1"}])
    pipeline.queue_db.get_urls_for_raw_logs = AsyncMock(return_value={"log1": "https://example.com"})
    pipeline.llm.chat = AsyncMock(return_value="# Digest")
    pipeline.writer.write_note = AsyncMock(return_value="Aily Drafts/Daily Digest 2026-04-05.md")
    pipeline.pusher.send_message = AsyncMock(return_value=True)

    path = await pipeline.run(open_id="u1")
    assert "Daily Digest" in path
    pipeline.writer.write_note.assert_awaited_once()
    pipeline.pusher.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_push_failure_non_fatal(pipeline):
    pipeline.graph_db.get_top_nodes_by_edge_count = AsyncMock(return_value=[])
    pipeline.graph_db.get_collisions_within_hours = AsyncMock(return_value=[])
    pipeline.graph_db.get_nodes_within_hours = AsyncMock(return_value=[])
    pipeline.graph_db.get_edges_within_hours = AsyncMock(return_value=[])
    pipeline.queue_db.get_urls_for_raw_logs = AsyncMock(return_value={})
    pipeline.llm.chat = AsyncMock(return_value="# Digest")
    pipeline.writer.write_note = AsyncMock(return_value="Aily Drafts/Daily Digest 2026-04-05.md")
    pipeline.pusher.send_message = AsyncMock(side_effect=RuntimeError("boom"))

    path = await pipeline.run(open_id="u1")
    assert path is not None
    pipeline.pusher.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_no_pusher(pipeline):
    pipeline.graph_db.get_top_nodes_by_edge_count = AsyncMock(return_value=[])
    pipeline.graph_db.get_collisions_within_hours = AsyncMock(return_value=[])
    pipeline.graph_db.get_nodes_within_hours = AsyncMock(return_value=[])
    pipeline.graph_db.get_edges_within_hours = AsyncMock(return_value=[])
    pipeline.queue_db.get_urls_for_raw_logs = AsyncMock(return_value={})
    pipeline.llm.chat = AsyncMock(return_value="# Digest")
    pipeline.writer.write_note = AsyncMock(return_value="Aily Drafts/Daily Digest 2026-04-05.md")
    pipeline.pusher = None

    path = await pipeline.run()
    assert path is not None
