import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from aily.agent.pipeline import PlannerPipeline
from aily.agent.registry import AgentRegistry


async def _fake_agent(context, text=""):
    return f"result: {text}"


@pytest.fixture
def registry():
    r = AgentRegistry()
    r.register("summarizer", _fake_agent, "Summarize text.")
    r.register("researcher", _fake_agent, "Research query.")
    return r


@pytest.fixture
def pipeline(registry):
    graph_db = AsyncMock()
    graph_db.get_top_nodes_by_edge_count = AsyncMock(return_value=[])
    graph_db.get_collisions_within_hours = AsyncMock(return_value=[])
    llm = AsyncMock()
    writer = AsyncMock()
    writer.write_note = AsyncMock(return_value="Aily Agent Result 2026-04-06.md")
    pusher = AsyncMock()
    pusher.send_message = AsyncMock(return_value=True)
    return PlannerPipeline(graph_db, llm, registry, writer, pusher)


@pytest.mark.asyncio
async def test_pipeline_executes_steps_and_writes_note(pipeline):
    pipeline.llm.chat_json = AsyncMock(return_value={
        "steps": [
            {"agent": "summarizer", "args": {"text": "hello"}},
            {"agent": "researcher", "args": {"text": "world"}},
        ]
    })
    path = await pipeline.run("do something", open_id="u1")
    assert path == "Aily Agent Result 2026-04-06.md"
    pipeline.writer.write_note.assert_awaited_once()
    pipeline.pusher.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_pipeline_invalid_agent_continues(pipeline):
    pipeline.llm.chat_json = AsyncMock(return_value={
        "steps": [
            {"agent": "summarizer", "args": {"text": "ok"}},
            {"agent": "nonexistent", "args": {"text": "bad"}},
        ]
    })
    path = await pipeline.run("test")
    assert path == "Aily Agent Result 2026-04-06.md"
    assert len(pipeline.writer.write_note.await_args[0][1].split("###")) == 3  # 2 steps header + content


@pytest.mark.asyncio
async def test_pipeline_llm_failure_falls_back(pipeline):
    pipeline.llm.chat_json = AsyncMock(side_effect=Exception("LLM down"))
    path = await pipeline.run("test")
    assert path == "Aily Agent Result 2026-04-06.md"
    markdown = pipeline.writer.write_note.await_args[0][1]
    assert "summarizer" in markdown


@pytest.mark.asyncio
async def test_pipeline_feishu_failure_non_fatal(pipeline):
    pipeline.llm.chat_json = AsyncMock(return_value={"steps": []})
    pipeline.pusher.send_message = AsyncMock(side_effect=Exception("push failed"))
    path = await pipeline.run("test", open_id="u1")
    assert path is not None


@pytest.mark.asyncio
async def test_pipeline_invalid_steps_format_falls_back(pipeline):
    pipeline.llm.chat_json = AsyncMock(return_value={"steps": "not_a_list"})
    path = await pipeline.run("test")
    markdown = pipeline.writer.write_note.await_args[0][1]
    assert "summarizer" in markdown
