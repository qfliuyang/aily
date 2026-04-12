import pytest

from aily.agent.registry import AgentRegistry


async def dummy_agent(context, text):
    return f"dummy: {text}"


@pytest.mark.asyncio
async def test_register_and_get():
    registry = AgentRegistry()
    registry.register("dummy", dummy_agent, "A dummy agent.")
    fn = registry.get("dummy")
    result = await fn({}, "hello")
    assert result == "dummy: hello"


@pytest.mark.asyncio
async def test_list_agents():
    registry = AgentRegistry()
    registry.register("a", dummy_agent, "Agent A")
    registry.register("b", dummy_agent, "Agent B")
    agents = registry.list_agents()
    assert len(agents) == 2
    assert agents[0]["name"] == "a"
    assert agents[1]["name"] == "b"


def test_duplicate_registration_raises():
    registry = AgentRegistry()
    registry.register("dup", dummy_agent, "desc")
    with pytest.raises(KeyError):
        registry.register("dup", dummy_agent, "desc")


def test_missing_agent_raises():
    registry = AgentRegistry()
    with pytest.raises(KeyError, match="Agent 'missing' not found"):
        registry.get("missing")
