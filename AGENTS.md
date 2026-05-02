<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# aily

## Purpose

Aily is a **Three-Mind knowledge system** built as a FastAPI app with a background job queue. It continuously processes incoming messages, files, and URLs through a DIKIWI 6-stage LLM pipeline (Data → Information → Knowledge → Insight → Wisdom → Impact), writes Zettelkasten notes to an Obsidian vault, and runs innovation/business evaluation loops. Supports three execution modes: single-document, batched, and graph-driven incremental processing.

## Key Files

| File | Description |
|------|-------------|
| `aily/config.py` | Pydantic SETTINGS singleton — all env vars and defaults |
| `aily/main.py` | FastAPI entry point, lifespan context, job dispatch |
| `requirements.txt` | Python dependencies |
| `pyproject.toml` | Project metadata and tool config |
| `pytest.ini` | Test configuration (asyncio_mode = auto) |
| `CLAUDE.md` | Project guidance for Claude Code |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `aily/` | Core application code (see `aily/AGENTS.md`) |
| `docs/` | Architecture docs, API guides, design documents |
| `scripts/` | CLI tools, daemons, batch runners (see `scripts/AGENTS.md`) |
| `tests/` | Test suites (see `tests/AGENTS.md`) |
| `plans/` | Claude Code plan files |
| `.omc/` | oh-my-claudecode state (autopilot, plans, sessions) |

## For AI Agents

### Working In This Directory
- All configuration lives in `aily/config.py` via pydantic-settings
- The app reads `.env` at startup; never hardcode API keys
- `pytest -xvs` runs all tests; most are async (auto mode)

### Testing Requirements
- Run `pytest` before committing changes to `aily/`
- Integration tests need real API keys; skip with `-k "not integration"`
- `tests/e2e/` covers full DIKIWI pipeline end-to-end

### Common Patterns
- Async-first codebase — all I/O is async
- Dataclasses for configs, Pydantic for settings
- `logger = logging.getLogger(__name__)` in every module
- `Path` objects everywhere, never string paths

## Dependencies

### Internal
- `aily/` — entire application is self-contained

### External
- `fastapi` — HTTP server
- `pydantic-settings` — Configuration
- `httpx` / `aiohttp` — HTTP clients
- `aiosqlite` — Async SQLite
- `watchfiles` — File watching (Chaos daemon)
- `apscheduler` — Scheduled jobs
- `pdfplumber` / `docling` / `mineru` — Document extraction

<!-- MANUAL: -->
