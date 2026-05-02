<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# aily

## Purpose

Core application package containing all subsystems: LLM routing, chaos processing, DIKIWI pipeline, knowledge graph, sessions, and output writers. Every module under here is part of the active runtime.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package init with version |
| `config.py` | `Settings` pydantic-settings class + `MindsConfig` + `SETTINGS` singleton |
| `main.py` | FastAPI app, lifespan manager, job dispatch router |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `agent/` | Legacy agent pipeline (see `agent/AGENTS.md`) |
| `bot/` | Feishu bot integration — WebSocket client, webhooks, intent routing |
| `browser/` | Headless browser management for web scraping |
| `capture/` | Claude Code session capture into Obsidian |
| `chaos/` | File-watcher daemon, document processors, DIKIWI bridge |
| `digest/` | Daily digest generation and scheduling |
| `dikiwi/` | 6-stage DIKIWI pipeline — agents, orchestrator, events |
| `gating/` | Hydrological gating subsystem (experimental) |
| `graph/` | SQLite-backed knowledge graph with bidirectional edges |
| `learning/` | Spaced repetition and recall system |
| `llm/` | LLM client, router, provider routes, prompt registry |
| `network/` | Network utilities |
| `parser/` | URL parsers (Kimi, Monica, arXiv, GitHub, YouTube) |
| `processing/` | File type router, atomicizer, markdownize |
| `push/` | Feishu message pusher |
| `queue/` | SQLite job queue and worker |
| `scheduler/` | APScheduler wrappers for daily jobs |
| `search/` | Tavily web search integration |
| `security/` | Keychain and credential management |
| `sessions/` | Three-Mind schedulers — DIKIWI, Innolaval, Entrepreneur |
| `thinking/` | Innovation frameworks, synthesis engine, orchestrator |
| `verify/` | Verification utilities |
| `voice/` | Voice memo download and transcription |
| `writer/` | Obsidian vault writers — DIKIWI notes, generic notes |

## For AI Agents

### Working In This Directory
- Import paths are relative to `aily/` (e.g., `from aily.config import SETTINGS`)
- Never import from `aily.main` in other modules (circular risk)
- `SETTINGS` is loaded once at import time — don't mutate it

### Testing Requirements
- Most modules have corresponding tests under `tests/`
- Async tests run without decorators (pytest.ini sets `asyncio_mode = auto`)

### Common Patterns
- `from __future__ import annotations` in every file
- Type hints everywhere; `dict[str, Any]` not `Dict`
- Use `pathlib.Path`, never `os.path`

## Dependencies

### Internal
- `config.py` is the root dependency — imported by almost everything
- `llm/` provides the shared `LLMClient` used across all minds

### External
- See root `requirements.txt`

<!-- MANUAL: -->
