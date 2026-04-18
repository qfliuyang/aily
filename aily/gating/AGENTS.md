<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# gating

## Purpose

Hydrological gating subsystem — experimental flow-control metaphor for content routing. Models knowledge as water: raindrops (inputs) flow through drainage (filters), dams (buffers), and reservoirs (storage) before reaching output channels.

## Key Files

| File | Description |
|------|-------------|
| `channels.py` | `InputChannel`, `OutputChannel` — ingress/egress connectors |
| `drainage.py` | `DrainageSystem` — routes raindrops through filters |
| `dam.py` | `Dam` — buffers and throttles flow |
| `reservoir.py` | `Reservoir` — persistent storage for gating state |

## For AI Agents

### Working In This Directory
- This subsystem is **experimental** and not the active DIKIWI runtime
- The active runtime uses the event-driven agent pipeline in `aily/dikiwi/`
- Gating may be revived for backpressure or rate-limiting scenarios

### Common Patterns
- `RainDrop` dataclass carries content + metadata through the system
- `RainType` enum classifies inputs (text, file, url, voice)
- Filters are composable: each drain can have multiple filters

## Dependencies

### Internal
- `aily/queue/` — QueueDB for job persistence
- `aily/bot/` — Feishu input channel

<!-- MANUAL: -->
