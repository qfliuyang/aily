<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# agents

## Purpose

The 6+ stage agents of the DIKIWI pipeline. Each agent transforms the output of the previous stage into higher-level knowledge artifacts, writing notes to the Obsidian vault.

## Key Files

| File | Description |
|------|-------------|
| `base.py` | `DikiwiAgent` abstract base — all agents extend this |
| `context.py` | `AgentContext` — shared context (budget, drop, LLM, writer) |
| `llm_tools.py` | `chat_json()` — structured LLM output helper |
| `data_agent.py` | DATA stage — chunks raw content, writes unclassified data notes |
| `information_agent.py` | INFORMATION stage — classifies data points into information nodes |
| `knowledge_agent.py` | KNOWLEDGE stage — finds relationships between information nodes |
| `insight_agent.py` | INSIGHT stage — generates pattern insights from knowledge |
| `wisdom_agent.py` | WISDOM stage — synthesizes wisdom zettels (producer-reviewer) |
| `impact_agent.py` | IMPACT stage — generates action items from wisdom |
| `residual_agent.py` | RESIDUAL stage — MAC loop synthesis (part of Innolaval) |
| `obsidian_cli.py` | `ObsidianCLI` — filesystem vault inspector |
| `producer.py` | Producer pattern for multi-model collaboration |
| `reviewer.py` | Reviewer pattern for quality gating |

## For AI Agents

### Working In This Directory
- Add new agents by extending `DikiwiAgent` and registering in `stages.py`
- Each agent's `execute()` returns `StageResult` with stage, notes, data dict
- Use `chat_json()` for structured LLM output
- Budget: call `ctx.budget.reserve()` before LLM calls
- Data point IDs: `dp_{uuid}_{chunk_index}_{i}`

### Common Patterns
- Producer-reviewer: one LLM generates, another reviews (WISDOM, IMPACT)
- `_id_to_title` dict in writer for link resolution
- Frontmatter: YAML with `dikiwi_id`, `aliases`, type-specific fields

## Dependencies

### Internal
- `aily/llm/` — LLM client and prompt registry
- `aily/writer/` — Obsidian writer
- `aily/graph/` — GraphDB for node persistence

<!-- MANUAL: -->
