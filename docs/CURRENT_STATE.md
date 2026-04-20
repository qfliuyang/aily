# Aily Current State

This file is the shortest trustworthy map of the codebase as it exists now.

## Active Runtime

- App bootstrap: `aily/main.py`
- Continuous pipeline entrypoint: `aily/sessions/dikiwi_mind.py`
- DIKIWI runtime coordination: `aily/dikiwi/orchestrator.py`
- DIKIWI graph-trigger selector: `aily/dikiwi/network_synthesis.py`
- Post-pipeline proposal synthesis: `aily/dikiwi/agents/residual_agent.py`
- Innovation scheduler: `aily/sessions/reactor_scheduler.py`
- Business evaluation scheduler: `aily/sessions/entrepreneur_scheduler.py`
- GStack and Guru planning: `aily/sessions/gstack_agent.py`
- Chaos ingestion bridge: `aily/chaos/dikiwi_bridge.py`
- Chaos daemon entrypoint: `scripts/run_chaos_daemon.py`

## Active Flow

1. Input enters through Feishu WebSocket, the chaos bridge, or queue-driven jobs.
2. For single inputs, `DikiwiMind` can still run one pipeline directly through `DATA -> INFORMATION -> KNOWLEDGE`.
3. For batch chaos ingestion, `00-Chaos` is written first and then the whole batch advances stage-by-stage through `01-Data`, `02-Information`, and `03-Knowledge`.
4. After batch `INFORMATION`, Aily measures incremental graph growth. If new information nodes add less than `5%` to the existing information graph, the batch stops after `KNOWLEDGE`.
5. If the batch crosses the incremental threshold and a context has a synthesis-grade changed neighborhood, that context continues through `INSIGHT -> WISDOM -> IMPACT`.
6. After IMPACT, `ReactorScheduler` generates proposal candidates from multiple frameworks.
7. `ResidualAgent` synthesizes vault, graph, and reactor context into structured `residual_proposal` nodes.
8. Reactor screens those residual proposals for innovation quality and promotes passing proposals to `pending_business`.
9. `EntrepreneurScheduler` runs GStack business review on pending proposals.
10. `Guru` writes an appendix for every reviewed proposal, including denied ones.
11. Notes are written into the numbered Obsidian vault layout.

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

## Reference Docs

- `README.md` - repo entrypoint and current workflow overview
- `docs/ARCHITECTURE_AND_VISION.md` - high-level system map
- `docs/DIKIWI_ARCHITECTURE.md` - current DIKIWI runtime and post-pipeline flow
- `docs/AILY_CHAOS_ARCHITECTURE.md` - current chaos ingestion and bridge path
- `docs/AI_INNOVATION_METHODOLOGIES.md` - framework reference
- `docs/prompt-improvement-spec.md` - prompt design direction and prompt-layer changes

## Experimental Or Quarantined

- `aily/dikiwi/skills/` is shipped in-tree but is not part of the active production path.
- `aily/dikiwi/memorials/` is shipped in-tree but is not wired into the active runtime.
- `aily/gating/` remains as older/secondary infrastructure and fallback material, not the primary DIKIWI path.

## Known Hybrid Areas

- The Feishu WebSocket path routes directly into `DikiwiMind`.
- The chaos batch path now uses `DikiwiMind.process_inputs_batched()` through `aily/chaos/dikiwi_bridge.py` and `aily/chaos/mineru_batch.py`.
- Some older queue-based jobs still exist in `aily/main.py` for URL fetch, digest, voice, file, and session processing.
- The passive capture scheduler exists, but its browser tab detection remains incomplete and should not be treated as the core ingestion path.
