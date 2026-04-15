# Aily Current State

This file is the shortest trustworthy map of the current codebase.

## Active Runtime

- App bootstrap: `aily/main.py`
- Continuous knowledge pipeline: `aily/sessions/dikiwi_mind.py`
- Daily innovation mind: `aily/sessions/innolaval_scheduler.py`
- Post-pipeline vault analyst: `aily/dikiwi/agents/hanlin_agent.py`
- Daily entrepreneur mind: `aily/sessions/entrepreneur_scheduler.py`
- Chaos ingestion runtime: `scripts/run_chaos_daemon.py`

## Active Reference Docs

- `README.md` - setup and product overview
- `docs/ARCHITECTURE_AND_VISION.md` - high-level system map
- `docs/AILY_CHAOS_ARCHITECTURE.md` - file ingestion and daemon behavior
- `docs/DIKIWI_ARCHITECTURE.md` - DIKIWI concepts and the experimental event-driven design
- `docs/AI_INNOVATION_METHODOLOGIES.md` - innovation framework reference
- `docs/DIKIWI_OBSIDIAN_OUTPUT_EXAMPLES.md` - output examples
- `docs/browser_authenticated_usage.md` - authenticated browser capture notes
- `docs/feishu-voice-webhook.md` - voice integration notes
- `docs/monica-kimi-dom-discovery.md` - passive capture research

## Active Runtime (Updated)

- `aily/dikiwi/` - event-driven DIKIWI architecture; now the primary runtime via `DikiwiOrchestrator`
- `aily/gating/` - hydrological gating subsystem; not the primary runtime path

## Archived Docs

Historical plans, review notes, and migration documents live under `docs/archive/`.
They are useful as decision history, but they should not be treated as the current architecture.
