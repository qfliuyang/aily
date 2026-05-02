from __future__ import annotations

import pytest

from aily.config import SETTINGS
from aily.sessions.dikiwi_mind import DataPoint, DikiwiMind, InformationNode, Insight, LLMUsageBudget


class CountingLLMClient:
    def __init__(self) -> None:
        self.calls = 0

    async def chat_json(self, messages, temperature=0.0):
        self.calls += 1
        return {"ok": True, "messages": messages, "temperature": temperature}


class SequenceLLMClient:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def chat_json(self, messages, temperature=0.0):
        self.calls += 1
        if not self.responses:
            raise AssertionError("No more fake responses available")
        return self.responses.pop(0)


def _mind_with_budget(max_calls: int, stage_round_limit: int):
    client = CountingLLMClient()
    mind = DikiwiMind(graph_db=None, llm_client=client)
    pipeline_id = "pipeline-test"
    memory = mind._get_or_create_memory(pipeline_id)
    mind._llm_budgets[pipeline_id] = LLMUsageBudget(
        max_calls=max_calls,
        stage_round_limit=stage_round_limit,
    )
    return mind, client, pipeline_id, memory


@pytest.mark.asyncio
async def test_chat_json_tracks_budget_per_stage():
    mind, client, pipeline_id, memory = _mind_with_budget(max_calls=4, stage_round_limit=2)

    await mind._chat_json(stage="data", messages=[{"role": "user", "content": "a"}], temperature=0.2, memory=memory)
    await mind._chat_json(stage="data", messages=[{"role": "user", "content": "b"}], temperature=0.2, memory=memory)
    await mind._chat_json(stage="information", messages=[{"role": "user", "content": "c"}], temperature=0.2, memory=memory)

    budget = mind._llm_budgets[pipeline_id]
    assert client.calls == 3
    assert budget.calls_used == 3
    assert budget.stage_calls == {"data": 2, "information": 1}


@pytest.mark.asyncio
async def test_chat_json_enforces_stage_round_limit():
    mind, client, _, memory = _mind_with_budget(max_calls=5, stage_round_limit=1)

    await mind._chat_json(stage="wisdom", messages=[{"role": "user", "content": "first"}], temperature=0.5, memory=memory)

    with pytest.raises(RuntimeError, match="stage round limit exceeded"):
        await mind._chat_json(stage="wisdom", messages=[{"role": "user", "content": "second"}], temperature=0.5, memory=memory)

    assert client.calls == 1


@pytest.mark.asyncio
async def test_chat_json_enforces_total_budget():
    mind, client, _, memory = _mind_with_budget(max_calls=2, stage_round_limit=3)

    await mind._chat_json(stage="data", messages=[{"role": "user", "content": "one"}], temperature=0.2, memory=memory)
    await mind._chat_json(stage="information", messages=[{"role": "user", "content": "two"}], temperature=0.2, memory=memory)

    with pytest.raises(RuntimeError, match="budget exceeded"):
        await mind._chat_json(stage="knowledge", messages=[{"role": "user", "content": "three"}], temperature=0.2, memory=memory)

    assert client.calls == 2


@pytest.mark.asyncio
async def test_classification_multi_agent_rounds_are_scoped_per_data_point():
    client = SequenceLLMClient(
        [
            {"tags": ["chip"], "info_type": "fact", "domain": "semiconductor", "confidence": 0.7},
            {"tags": ["chip-architecture"], "info_type": "fact", "domain": "semiconductor", "confidence": 0.9},
            {"tags": ["timing"], "info_type": "fact", "domain": "eda", "confidence": 0.7},
            {"tags": ["timing-closure"], "info_type": "fact", "domain": "eda", "confidence": 0.9},
        ]
    )
    mind = DikiwiMind(graph_db=None, llm_client=client)
    pipeline_id = "pipeline-classification"
    memory = mind._get_or_create_memory(pipeline_id)
    mind._llm_budgets[pipeline_id] = LLMUsageBudget(max_calls=4, stage_round_limit=2)

    first = await mind._llm_classify_and_tag(
        DataPoint(id="dp1", content="Architecture choices constrain floorplanning.", source="pdf"),
        memory,
    )
    second = await mind._llm_classify_and_tag(
        DataPoint(id="dp2", content="Timing closure depends on realistic constraint models.", source="pdf"),
        memory,
    )

    assert client.calls == 4
    assert first["tags"] == ["chip-architecture"]
    assert second["tags"] == ["timing-closure"]


@pytest.mark.asyncio
async def test_wisdom_uses_single_pass_by_default():
    client = SequenceLLMClient(
        [
            {
                "zettels": [
                    {
                        "title": "Architecture Decisions Set the Ceiling for Later Optimization",
                        "content": "Architecture decisions shape later optimization capacity by defining the feasible constraint space before implementation begins. " * 6,
                        "tags": ["architecture", "optimization"],
                        "links_to": ["Timing Closure Depends on Early Constraint Modeling"],
                        "confidence": 0.9,
                    }
                ]
            },
        ]
    )
    mind = DikiwiMind(graph_db=None, llm_client=client)
    pipeline_id = "pipeline-wisdom-single"
    memory = mind._get_or_create_memory(pipeline_id)
    mind._llm_budgets[pipeline_id] = LLMUsageBudget(max_calls=4, stage_round_limit=2)

    original_review_enabled = SETTINGS.dikiwi_wisdom_review_enabled
    try:
        SETTINGS.dikiwi_wisdom_review_enabled = False
        zettels = await mind._llm_synthesize_wisdom(
            insights=[Insight(id="i1", insight_type="pattern", description="Architecture and closure are tightly coupled.")],
            info_nodes=[
                InformationNode(
                    id="n1",
                    data_point_id="d1",
                    content="Architecture determines the downstream physical optimization options in chip design.",
                    tags=["architecture"],
                    info_type="fact",
                    domain="semiconductor",
                )
            ],
            memory=memory,
        )
    finally:
        SETTINGS.dikiwi_wisdom_review_enabled = original_review_enabled

    assert client.calls == 1
    assert len(zettels) == 1
    assert zettels[0].title == "Architecture Decisions Set the Ceiling for Later Optimization"


@pytest.mark.asyncio
async def test_wisdom_can_use_producer_and_reviewer_agents_when_enabled():
    client = SequenceLLMClient(
        [
            {
                "zettels": [
                    {
                        "title": "Architecture Drives Downstream Optimization",
                        "content": "Architecture decisions shape later optimization capacity. " * 8,
                        "tags": ["architecture"],
                        "links_to": ["Timing Closure Depends on Early Constraint Modeling"],
                        "confidence": 0.6,
                    }
                ]
            },
            {
                "zettels": [
                    {
                        "title": "Architecture Decisions Set the Ceiling for Later Optimization",
                        "content": "Architecture decisions shape later optimization capacity by defining the feasible constraint space before implementation begins. " * 6,
                        "tags": ["architecture", "optimization"],
                        "links_to": ["Timing Closure Depends on Early Constraint Modeling"],
                        "confidence": 0.9,
                    },
                    {
                        "title": "Constraint Models Must Appear Early to Support Closure",
                        "content": "Constraint models are more valuable when they appear during architectural exploration rather than after implementation pressure accumulates. " * 6,
                        "tags": ["constraints", "timing-closure"],
                        "links_to": ["Architecture Decisions Set the Ceiling for Later Optimization"],
                        "confidence": 0.88,
                    },
                ]
            },
        ]
    )
    mind = DikiwiMind(graph_db=None, llm_client=client)
    pipeline_id = "pipeline-wisdom"
    memory = mind._get_or_create_memory(pipeline_id)
    mind._llm_budgets[pipeline_id] = LLMUsageBudget(max_calls=4, stage_round_limit=2)

    original_review_enabled = SETTINGS.dikiwi_wisdom_review_enabled
    try:
        SETTINGS.dikiwi_wisdom_review_enabled = True
        zettels = await mind._llm_synthesize_wisdom(
            insights=[Insight(id="i1", insight_type="pattern", description="Architecture and closure are tightly coupled.")],
            info_nodes=[
                InformationNode(
                    id="n1",
                    data_point_id="d1",
                    content="Architecture determines the downstream physical optimization options in chip design.",
                    tags=["architecture"],
                    info_type="fact",
                    domain="semiconductor",
                )
            ],
            memory=memory,
        )
    finally:
        SETTINGS.dikiwi_wisdom_review_enabled = original_review_enabled

    assert client.calls == 2
    assert len(zettels) == 2
    assert zettels[0].title == "Architecture Decisions Set the Ceiling for Later Optimization"
