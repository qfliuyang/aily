from __future__ import annotations

from typing import Any, Awaitable, Callable


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, tuple[Callable[..., Awaitable[str]], str]] = {}

    def register(
        self, name: str, agent_fn: Callable[..., Awaitable[str]], description: str
    ) -> None:
        if name in self._agents:
            raise KeyError(f"Agent '{name}' is already registered")
        self._agents[name] = (agent_fn, description)

    def get(self, name: str) -> Callable[..., Awaitable[str]]:
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' not found")
        return self._agents[name][0]

    def list_agents(self) -> list[dict[str, str]]:
        return [
            {"name": name, "description": desc}
            for name, (_, desc) in self._agents.items()
        ]
