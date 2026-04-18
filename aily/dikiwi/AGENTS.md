<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# dikiwi

## Purpose

The DIKIWI (Data → Information → Knowledge → Insight → Wisdom → Impact) pipeline. This is the core knowledge processing engine: 6 event-driven stage agents that transform raw content into structured Zettelkasten notes, with a post-pipeline MAC loop (Multiply-Accumulate) that runs innovation frameworks and synthesizes proposals.

## Key Files

| File | Description |
|------|-------------|
| `orchestrator.py` | `DikiwiOrchestrator` — manages pipeline state, stage transitions, CVO gating |
| `stages.py` | `DikiwiStage` enum, stage transition logic, TTL/CVO review |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `agents/` | Stage agents — Data, Information, Knowledge, Insight, Wisdom, Impact, Residual, Hanlin (see `agents/AGENTS.md`) |
| `events/` | Event bus — `StageCompletedEvent`, `DropCompletedEvent` |
| `gates/` | CVO (Chief Vision Officer) gating, Menxia review system |
| `memorials/` | Persistent memory models and storage |
| `skills/` | DIKIWI skill system — builtin pattern detection, synthesis, tagging |

## For AI Agents

### Working In This Directory
- Each stage agent extends `DikiwiAgent` from `agents/base.py`
- Agents are event-driven: `execute(ctx: AgentContext) -> StageResult`
- The orchestrator handles promotion logic; agents don't call each other directly
- `AgentContext` carries budget, drop, LLM client, and obsidian writer
- Budget enforcement: `ctx.budget.reserve()` before LLM calls

### Testing Requirements
- `tests/dikiwi/` covers stage logic and agent behavior
- `tests/e2e/` runs full pipeline with real LLM calls

### Common Patterns
- `chat_json()` in `agents/llm_tools.py` for structured LLM output
- Producer-reviewer pattern for WISDOM and IMPACT stages
- Data point IDs: `dp_{uuid}_{chunk_index}_{i}`
- Note IDs use SHA1 hashes for stability

## Dependencies

### Internal
- `aily/llm/` — `LLMClient`, `LLMRouter`, prompt registry
- `aily/writer/` — `DikiwiObsidianWriter` for vault output
- `aily/graph/` — GraphDB for node/edge persistence
- `aily/sessions/` — `DikiwiMind` wires the orchestrator + schedulers

### External
- See root requirements

<!-- MANUAL: -->
