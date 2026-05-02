<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# integration

## Purpose

Integration layer connecting the thinking/innovation system to Aily's core infrastructure. Provides LLM clients with structured output validation, GraphDB access, agent registration, and queue/output adapters.

## Key Files

| File | Description |
|------|-------------|
| `llm_integration.py` | `ThinkingLLMClient` — wraps LLMClient with Instructor-based structured output validation |
| `graphdb_client.py` | GraphDB adapter for thinking system queries and proposal persistence |
| `agent_registration.py` | Registers thinking analyzers as DIKIWI pipeline agents |
| `output_integration.py` | Routes synthesized proposals to Obsidian writer and output channels |
| `queue_integration.py` | Enqueues thinking jobs for async background processing |

## For AI Agents

### Working In This Directory
- `ThinkingLLMClient` uses `instructor` library for automatic Pydantic model validation + retry
- GraphDB client maps between thinking models and graph node types
- Output integration writes proposals as `07-Proposal/` notes and `hanlin_proposal` GraphDB nodes

### Common Patterns
- Instructor wrapper validates LLM output against Pydantic schemas
- Failed validations trigger automatic retry with error context fed back to LLM
- Queue integration allows thinking jobs to be deferred and processed async

## Dependencies

### Internal
- `aily/llm/` — Base LLM client
- `aily/graph/` — GraphDB for proposal storage
- `aily/writer/` — Obsidian output
- `aily/thinking/frameworks/` — Framework analyzers
- `aily/thinking/synthesis/` — Synthesis engine

### External
- `instructor` — Structured LLM output validation library

<!-- MANUAL: -->
