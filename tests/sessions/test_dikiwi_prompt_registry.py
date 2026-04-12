from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aily.llm.prompt_registry import DikiwiPromptRegistry
from aily.sessions.dikiwi_mind import ConversationMemory, DataPoint, DikiwiMind


def test_prompt_registry_builds_shared_mission_messages():
    messages = DikiwiPromptRegistry.wisdom(
        insights_desc="- [pattern] Latency pressure reveals architecture tradeoffs",
        info_samples="- [engineering] Memory bandwidth limits throughput",
        memory_context="Assistant: STAGE 4 complete",
    )

    assert len(messages) == 2
    assert "turn messy input into durable Zettelkasten knowledge" in messages[0]["content"]
    assert "Current role: Zettelkasten Author" in messages[0]["content"]
    assert "internally act as a knowledge editor" in messages[0]["content"]
    assert "## Shared Memory" in messages[1]["content"]


@pytest.mark.asyncio
async def test_dikiwi_classification_uses_shared_memory():
    llm_client = MagicMock()
    llm_client.chat_json = AsyncMock(
        return_value={
            "tags": ["latency", "memory"],
            "info_type": "fact",
            "domain": "engineering",
            "confidence": 0.9,
        }
    )
    graph_db = AsyncMock()
    mind = DikiwiMind(llm_client=llm_client, graph_db=graph_db)

    memory = ConversationMemory()
    memory.add_system("DIKIWI system")
    memory.add_user("User: investigate AI hardware bottlenecks")
    memory.add_assistant("STAGE 1 complete: extracted data about bandwidth and latency")

    data_point = DataPoint(
        id="dp1",
        content="Bandwidth bottlenecks can dominate accelerator throughput.",
        context="This came from a discussion about inference efficiency.",
        source="chaos_processor",
    )

    result = await mind._llm_classify_and_tag(data_point, memory)

    assert result["domain"] == "engineering"
    # First call is the producer (Semantic Classifier); await_args captures the last (reviewer)
    messages = llm_client.chat_json.call_args_list[0].kwargs["messages"]
    assert "Current role: Semantic Classifier" in messages[0]["content"]
    assert "Shared Memory" in messages[1]["content"]
    assert "STAGE 1 complete" in messages[1]["content"]
