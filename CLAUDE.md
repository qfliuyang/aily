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

`aily/llm/provider_routes.py` → `PrimaryLLMRoute.from_settings()` builds the app-wide `LLMClient`. Supports **4 providers** with workload-aware routing:

| Provider | Model | API URL | Mode |
|----------|-------|---------|------|
| **Kimi** (default) | `kimi-k2.6` | `api.moonshot.cn/v1` | Per-token (standard) |
| **Zhipu** | `glm-5.1` | `open.bigmodel.cn/api/paas/v4` | Per-token (standard) |
| **DeepSeek** | `deepseek-v4-pro` | `api.deepseek.com` | Per-token (standard) |
| **ByteDance Ark** | `kimi-k2.6` | Coding Plan | Fixed monthly |

Workload-aware routing via `llm_workload_routes_json` setting. Thinking mode is **disabled by default** for batch speed (was causing 90s latency with 28% timeout rate). Timeout: 300s. Required env vars: `KIMI_API_KEY`, `ZHIPU_API_KEY`, `DEEPSEEK_API_KEY`.

### Output

All notes go to **Obsidian** via filesystem writes (`aily/writer/dikiwi_obsidian.py`). Higher-stage notes (insight, wisdom, impact) include `grounded_in` frontmatter for dependency tracking, enabling incremental staleness detection. Vault layout:
- `00-Chaos/` + `00-Chaos/images/` — Raw transcripts and extracted images
- `01-Data/` — Unclassified data points
- `02-Information/` — Classified information nodes
- `03-Knowledge/` — Knowledge relationships
- `04-Insight/` — Pattern insights
- `05-Wisdom/` — Synthesized wisdom zettels
- `06-Impact/` — Action items
- `07-Proposal/` — Innovation proposals
- `08-Entrepreneurship/` — Business evaluations
- `99-MOC/` — Maps of Content

### Incremental processing (NEW)

`aily/dikiwi/incremental_orchestrator.py` — Graph-driven delta pipeline. When new files arrive:
1. DATA + INFORMATION run on new content only
2. `NetworkSynthesisSelector` detects changed graph neighborhoods via GraphDB
3. `ObsidianCLI.search_by_frontmatter("grounded_in", ...)` finds stale higher-stage notes
4. Only affected insight/wisdom/impact notes regenerate

Entry points:
- `DikiwiMind.process_input_incremental(files)` — programmatic API
- `scripts/aily_ingest.py --chaos-dir <dir>` — CLI (one-shot)
- `scripts/aily_ingest.py --watch --chaos-dir <dir>` — daemon mode
- `scripts/aily_ingest.py --force ...` — bypass graph threshold, full pipeline

### Key subsystems at a glance

| Path | Purpose |
|------|---------|
| `aily/graph/db.py` | SQLite-backed knowledge graph (nodes, edges, properties, occurrences) |
| `aily/dikiwi/` | DIKIWI runtime — 6 event-driven agents + incremental orchestrator |
| `aily/dikiwi/incremental_orchestrator.py` | Graph-driven incremental pipeline (NEW) |
| `aily/dikiwi/network_synthesis.py` | Subgraph change detection for incremental triggering |
| `aily/dikiwi/agents/obsidian_cli.py` | Filesystem vault reader — frontmatter search, backlinks, tags |
| `aily/parser/` + `aily/parser/registry.py` | URL parsers (Kimi, Monica, arXiv, GitHub, YouTube) |
| `aily/processing/router.py` | Universal file type router (PDF, image, docx…) |
| `aily/scheduler/jobs.py` | APScheduler wrappers for digest, passive capture, Claude session capture |
| `aily/thinking/` | 11 innovation frameworks (TRIZ, SCAMPER, Blue Ocean, etc.) |
| `aily/gating/` | Hydrological gating subsystem — **experimental, not the active runtime** |
| `scripts/benchmark_providers.py` | Multi-provider benchmark (Kimi / Zhipu / DeepSeek) |
| `scripts/prep_chaos.py` | Pre-extract PDFs for consistent benchmark inputs |

### Required env vars

```
KIMI_API_KEY            # Kimi / Moonshot AI (primary LLM)
ZHIPU_API_KEY           # Zhipu / BigModel (secondary)
DEEPSEEK_API_KEY        # DeepSeek (tertiary)
OBSIDIAN_VAULT_PATH     # absolute path to Obsidian vault
FEISHU_APP_ID           # Feishu bot credentials
FEISHU_APP_SECRET
```

Optional: `TAVILY_API_KEY`, `BROWSER_USE_API_KEY`, `WHISPER_API_KEY`, `AILY_INNOVATION_TIME`, `AILY_ENTREPRENEUR_TIME`.
