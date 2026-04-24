<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# sessions

## Purpose

The Three-Mind System. Three independent schedulers that run at different cadences: DIKIWI Mind (continuous, per-message), Innolaval (Innovation Mind, daily 8am + per-pipeline MAC loop), and Entrepreneur (Business Mind, daily 9am GStack framework).

## Key Files

| File | Description |
|------|-------------|
| `dikiwi_mind.py` | `DikiwiMind` — main entry point for all inbound messages/files |
| `reactor_scheduler.py` | `ReactorScheduler` — Innolaval innovation frameworks, MAC loop Reactor |
| `entrepreneur_scheduler.py` | `EntrepreneurScheduler` — GStack business evaluation |
| `base.py` | Base scheduler class |
| `models.py` | Session models and data structures |
| `gstack_agent.py` | GStack agent integration for entrepreneur sessions |

## For AI Agents

### Working In This Directory
- `DikiwiMind.process_input(drop)` is the universal entry point
- After DIKIWI pipeline completes, MAC loop runs automatically (if `mac_enabled`)
- Reactor evaluates context with 8 innovation frameworks
- Entrepreneur reads `hanlin_proposal` and `residual_proposal` nodes from GraphDB
- Schedulers are wired in `main.py` lifespan context

### Testing Requirements
- `tests/sessions/` covers scheduler behavior
- `tests/e2e/` tests full Three-Mind flow

### Common Patterns
- Schedulers use `APScheduler` for daily runs
- Context gathering: query GraphDB for recent nodes
- Proposal persistence: insert into GraphDB with `pending_innovation`/`pending_business` status

## Dependencies

### Internal
- `aily/dikiwi/` — DIKIWI pipeline
- `aily/thinking/` — Innovation frameworks
- `aily/graph/` — GraphDB queries

### External
- `apscheduler` — Scheduling

<!-- MANUAL: -->
