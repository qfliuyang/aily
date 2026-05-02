<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# agent

## Purpose

Legacy AI agent framework. Defines the base agent interface, pipeline orchestration, and agent registry. Predecessor to the event-driven DIKIWI agent system.

## Key Files

| File | Description |
|------|-------------|
| `agents.py` | Base agent classes and interfaces |
| `pipeline.py` | `AgentPipeline` — sequential agent execution |
| `registry.py` | `AgentRegistry` — agent discovery and lookup |

## For AI Agents

### Working In This Directory
- This is the **legacy** agent framework — the active runtime is in `aily/dikiwi/`
- Code here may be referenced by older components or gradually migrated
- Prefer `aily/dikiwi/agents/base.py` for new agent work

### Common Patterns
- Agents implement `run(context) → result`
- Pipeline chains agents sequentially
- Registry maps agent names to classes

## Dependencies

### Internal
- `aily/llm/` — LLM client
- `aily/graph/` — GraphDB for agent state

<!-- MANUAL: -->
