<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# events

## Purpose

Event bus for DIKIWI. Provides async, decoupled communication between pipeline stages and agents. Supports both in-memory and Redis backends.

## Key Files

| File | Description |
|------|-------------|
| `bus.py` | `EventBus` — publish/subscribe with in-memory or Redis backend |
| `models.py` | `Event` base class and concrete event types |

## For AI Agents

### Working In This Directory
- Events are the primary inter-stage communication mechanism
- `EventBus.emit(event)` publishes; `@bus.on(EventType)` subscribes
- Redis backend enables distributed/multi-process deployments
- In-memory backend is the default for single-instance runs

### Common Patterns
- Event types are dataclasses extending `Event`
- Handlers are async callables
- Event bus is initialized in `DikiwiMind`

## Dependencies

### Internal
- `aily/dikiwi/agents/` — Agents emit and listen to events

### External
- `redis` — Optional Redis backend

<!-- MANUAL: -->
