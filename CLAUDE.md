# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run the app
python -m aily.main          # starts FastAPI on 127.0.0.1:8000

# Run the chaos file-watcher daemon (separate process)
python scripts/run_chaos_daemon.py start
python scripts/run_chaos_daemon.py status

# Tests
pytest                        # all tests
pytest tests/test_foo.py      # single file
pytest tests/test_foo.py::test_bar  # single test
pytest -xvs                   # stop on first failure, verbose

# Env
cp .env.example .env          # then fill in API keys
```

`pytest.ini` sets `asyncio_mode = auto`, so all async tests run without extra decorators.

## Architecture

Aily is a **Three-Mind knowledge system** built as a FastAPI app with a background job queue. All configuration is loaded once at import time into the `SETTINGS` singleton (`aily/config.py`).

### Three Minds

| Mind | File | Trigger |
|------|------|---------|
| DIKIWI Mind (continuous) | `aily/sessions/dikiwi_mind.py` | Every inbound message |
| Innolaval (Innovation) | `aily/sessions/innolaval_scheduler.py` | Per-pipeline MAC loop + daily 8am |
| Entrepreneur | `aily/sessions/entrepreneur_scheduler.py` | Daily 9am — GStack framework |

All three are wired up and started in `aily/main.py`'s `lifespan()` context manager.

### Message flow

1. **Feishu WebSocket** (`aily/bot/ws_client.py`) receives messages and routes them to `DikiwiMind.process_input()`.
2. **DIKIWI Mind** runs a 6-stage LLM pipeline (Data → Information → Knowledge → Insight → Wisdom → Impact), writing Zettelkasten notes via `aily/writer/dikiwi_obsidian.py`.
3. **MAC Loop** (Multiply-Accumulate): After the 6-stage pipeline, Innolaval runs 8 innovation frameworks on the DIKIWI context; Hanlin synthesizes the results. This iterates 2 rounds — round 1 is a dry run, round 2 persists the final report and `hanlin_proposal` nodes to GraphDB.
4. For non-text inputs (URLs, files, voice, images), the bot enqueues jobs into the **SQLite queue** (`aily/queue/db.py`), dispatched by `JobWorker` (`aily/queue/worker.py`) through `_dispatch_job()` in `main.py`.

### Chaos Daemon (separate process)

`scripts/run_chaos_daemon.py` watches `~/aily_chaos/` for dropped files using `watchfiles`. It calls `aily/chaos/processor.py` → `aily/chaos/dikiwi_bridge.py` to process PDFs, images, video, and text through the same DIKIWI pipeline.

### LLM routing

`aily/llm/provider_routes.py` → `PrimaryLLMRoute.from_settings()` builds the app-wide `LLMClient`. Default provider is **Zhipu AI (GLM-4-flash)**. The `LLMRouter` in `aily/llm/llm_router.py` handles rate limiting (configurable via `llm_max_concurrency` / `llm_min_interval_seconds`).

### Output

All notes go to **Obsidian** via its Local REST API (`aily/writer/obsidian.py`). The vault layout is:
- `10-Knowledge/` — Zettelkasten notes
- `20-Innovation/` — Innolaval proposals
- `30-Business/` — Entrepreneur analyses

### Key subsystems at a glance

| Path | Purpose |
|------|---------|
| `aily/graph/db.py` | SQLite-backed knowledge graph (bidirectional links) |
| `aily/parser/` + `aily/parser/registry.py` | URL parsers (Kimi, Monica, arXiv, GitHub, YouTube) |
| `aily/processing/router.py` | Universal file type router (PDF, image, docx…) |
| `aily/scheduler/jobs.py` | APScheduler wrappers for digest, passive capture, Claude session capture |
| `aily/capture/claude_code.py` | Captures Claude Code session JSONL files into Obsidian |
| `aily/thinking/` | Extended thinking config for complex LLM calls |
| `aily/dikiwi/` | Primary DIKIWI runtime — event-driven agents (Data, Information, Knowledge, Insight, Wisdom, Impact, plus Hanlin vault analyst) |
| `aily/gating/` | Hydrological gating subsystem — **experimental, not the active runtime** |

### Required env vars

```
ZHIPU_API_KEY          # Zhipu AI (primary LLM)
OBSIDIAN_VAULT_PATH    # absolute path to Obsidian vault
OBSIDIAN_REST_API_KEY  # Obsidian Local REST API plugin key
FEISHU_APP_ID          # Feishu bot credentials
FEISHU_APP_SECRET
```

Optional: `TAVILY_API_KEY` (web search), `BROWSER_USE_API_KEY`, `WHISPER_API_KEY` (voice), `AILY_INNOVATION_TIME`, `AILY_ENTREPRENEUR_TIME`.
