# Aily

Aily is a three-mind knowledge system built around a continuous DIKIWI pipeline, a proposal-generation layer, and a business-evaluation layer.

The current production path is:

1. `DikiwiMind` processes input through `DATA -> INFORMATION -> KNOWLEDGE -> INSIGHT -> WISDOM -> IMPACT`
2. `ReactorScheduler` generates proposal candidates from multiple innovation frameworks
3. `ResidualAgent` synthesizes those candidates into structured `residual_proposal` nodes
4. `EntrepreneurScheduler` runs GStack review on business-ready proposals
5. `Guru` writes a deep appendix for every reviewed proposal, including denied ones

## Main Components

### DIKIWI Mind

- Entry point: `aily/sessions/dikiwi_mind.py`
- Runtime coordination: `aily/dikiwi/orchestrator.py`
- Stage agents: `aily/dikiwi/agents/`
- Purpose: turn raw input into structured notes and graph-linked knowledge

### Reactor

- File: `aily/sessions/reactor_scheduler.py`
- Purpose: run multiple thinking frameworks and score proposal candidates
- Output: proposal candidates and innovation-screened `residual_proposal` nodes

### Residual

- File: `aily/dikiwi/agents/residual_agent.py`
- Purpose: analyze the vault, graph, and reactor proposals to draft structured venture-style proposals
- Output: notes in `07-Proposal` and `residual_proposal` nodes in GraphDB

### Entrepreneur

- File: `aily/sessions/entrepreneur_scheduler.py`
- Purpose: evaluate pending business proposals with GStack
- Output: reviewed notes in `08-Entrepreneurship`, GraphDB status updates, and incubation tasks for approved ideas

### Guru

- File: `aily/sessions/gstack_agent.py`
- Purpose: generate executive-grade appendices after GStack review
- Scope: both accepted and denied ideas
- Output: hypothesis-driven business briefing plus simulation-driven development appendix in `08-Entrepreneurship`

## Active Input Paths

- Feishu WebSocket messages via `aily/bot/ws_client.py`
- Chaos file ingestion via `aily/chaos/dikiwi_bridge.py` and `scripts/run_chaos_daemon.py`
- Queue-driven legacy jobs in `aily/main.py` for URL fetch, digest, voice, file, and session processing

## Active Vault Layout

- `00-Chaos`
- `01-Data`
- `02-Information`
- `03-Knowledge`
- `04-Insight`
- `05-Wisdom`
- `06-Impact`
- `07-Proposal`
- `08-Entrepreneurship`

## Startup Flow

The FastAPI lifespan in `aily/main.py` starts:

- GraphDB and queue DB
- Browser manager when available
- `DikiwiMind`
- Feishu WebSocket client
- Learning loop
- Passive capture scheduler
- Daily digest scheduler
- Claude Code capture scheduler
- `ReactorScheduler`
- `EntrepreneurScheduler`

`DikiwiMind` is also wired to Reactor and Entrepreneur so post-pipeline proposal flow can happen immediately after DIKIWI completes.

## Notes On Runtime Status

- `aily/dikiwi/skills/` exists in-tree but is not part of the active production path.
- `aily/dikiwi/memorials/` exists in-tree but is not wired into the active runtime.
- `aily/gating/` still exists as older/secondary infrastructure and fallback material.

## Documentation

- `docs/CURRENT_STATE.md` - shortest reliable map of what is active
- `docs/ARCHITECTURE_AND_VISION.md` - current high-level architecture
- `docs/DIKIWI_ARCHITECTURE.md` - DIKIWI and post-pipeline flow
- `docs/AILY_CHAOS_ARCHITECTURE.md` - chaos ingestion path
- `docs/AI_INNOVATION_METHODOLOGIES.md` - framework reference
- `docs/prompt-improvement-spec.md` - prompt improvement spec
