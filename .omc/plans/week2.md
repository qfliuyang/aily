# Aily — Week 2 Plan: Subprocess Browser, Passive Capture, and Entity Graph Foundation

**Goal:** Build the infrastructure layers deferred from Week 1 so that Aily can run passive capture and start tracking an entity graph.

## Scope

### In Scope
1. **BrowserUseManager with subprocess queue** — Replace in-process `asyncio.Semaphore(1)` with a dedicated subprocess that runs Browser Use under Python 3.11+. Both the queue worker and passive capture will enqueue fetch tasks to this subprocess via IPC.
2. **Passive capture scheduler** — APScheduler-based smart polling with 0-60s jitter and exponential backoff (up to 30 min) on consecutive failures. placeholder implementation for Monica/Kimi URL detection.
3. **Entity graph schema** — Define SQLite tables for `nodes`, `edges`, and `occurrences` in `aily_graph.db`.
4. **URL dedup hash** — Add `url_hash` (SHA256) to the `raw_ingestion_log` and check it before creating a new job.
5. **LLM client wrapper** — Shared client with explicit timeout (60s), retry (1), and graceful-degradation behavior. Includes `json-repair` fallback for malformed JSON.

### Out of Scope
- Feishu voice message verification (blocked: needs real test bot interaction)
- Monica/Kimi DOM selector discovery spike (blocked: needs authenticated accounts)
- Full entity graph query engine and collision detection (schema only this week)
- Daily digest scheduling and content curation (deferred to Week 3)

## Architecture

```
Aily main process (Python 3.11)
  ├── BrowserUseManager
  │     └── spawns subprocess_worker.py on demand
  │     └── IPC via multiprocessing.connection Client/Listener
  ├── APScheduler
  │     └── passive_capture_job (jitter + backoff)
  │         └── enqueues "url_fetch" jobs via QueueDB
  ├── JobWorker
  │     └── dequeues jobs
  │     └── BrowserUseManager.fetch(url)
  │     └── parser → Obsidian writer → Feishu push
  ├── QueueDB (aily_queue.db)
  │     └── jobs table + raw_ingestion_log with url_hash
  └── GraphDB (aily_graph.db)
        └── nodes, edges, occurrences tables
```

## File Changes

### New files
- `aily/browser/subprocess_worker.py`
- `aily/browser/manager.py`
- `aily/scheduler/jobs.py`
- `aily/graph/db.py`
- `aily/llm/client.py`
- `tests/test_browser_manager.py`
- `tests/test_scheduler.py`
- `tests/test_graph_db.py`
- `tests/test_llm_client.py`
- `tests/test_url_dedup.py`

### Modified files
- `aily/browser/fetcher.py` — Replace current logic with delegation to BrowserUseManager
- `aily/queue/db.py` — Add `url_hash` to `raw_ingestion_log`, `insert_raw_log` checks for duplicates, enable WAL mode
- `aily/main.py` — Add scheduler startup, BrowserUseManager lifecycle, graph db init
- `requirements.txt` — Add `APScheduler`, `json-repair`

## Critical Decisions

### IPC: multiprocessing.connection vs asyncio Queue
- **Choice:** `multiprocessing.connection.Listener/Client` (stdlib)
- **Why:** Handles serialization cleanly, works across process boundaries, no `freeze_support` headaches.
- **Trade-off:** Sync client call wrapped in `run_in_executor`, which adds slight blocking overhead. Acceptable for serialized browser access.

### Python 3.9 vs 3.11
- The main Aily daemon now runs on Python 3.11 (venv created in Week 1). Browser subprocess can share the same interpreter, simplifying the setup.
- **Simplification from original plan:** No need for a separate py311 venv; the whole project uses `.venv/bin/python3.11`.

### Passive capture placeholder
- Week 2 implements the scheduler and jitter/backoff mechanics. The actual Monica/Kimi detection logic is a placeholder that logs "would scan" until DOM selectors are discovered.
- **Why:** Unblocks testing the scheduling and retry infrastructure without waiting for authenticated account access.

## Test Strategy

| Test file | What it tests |
|-----------|---------------|
| `test_browser_manager.py` | Subprocess starts/stops, fetch returns text, `BrowserFetchError` on subprocess crash |
| `test_scheduler.py` | Jitter range 0-60s, backoff doubles up to 30 min, failure logging |
| `test_graph_db.py` | Schema init, insert node/edge/occurrence, query by node type |
| `test_llm_client.py` | Success, timeout retry, malformed JSON + json-repair, degrade behavior |
| `test_url_dedup.py` | Duplicate URL hash returns None, new URL gets enqueued |
| `test_passive_capture_e2e.py` | Scheduler fires → enqueues job → mocked BrowserUseManager → worker processes → mocked Obsidian + Feishu push |

## Failure Modes

1. **Subprocess crash on fetch** → `BrowserUseManager` should detect dead process, restart, and retry once. If restart fails, raise `BrowserFetchError`. In-flight request must be tracked so it is resent after restart.
2. **Passive capture backoff saturation** → After 24h of failures, log alert and stop scheduling until manual intervention.
3. **LLM timeout** → After 1 retry, degrade gracefully (simpler prompt or skip feature). Never hard-fail the pipeline.
4. **SQLite unique constraint on url_hash** → Catch `IntegrityError` in `insert_raw_log` and return `None` (duplicate).
5. **IPC connection timeout** → `multiprocessing.connection.Client` should use a socket-level timeout (e.g., 65s) so a hung subprocess does not leave an orphan executor thread.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLEAR | Scope accepted: full Week 2 bundle |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 8 notes addressed inline |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

### Post-Review Fixes (applied)
1. **BrowserUseManager port race** — Child now picks its own ephemeral port via `Listener(("localhost", 0), ...)` and reports it via `READY <port>` stdout. Removes socket race entirely.
2. **IPC timeout leak** — `Client(..., timeout=65)` now sets a socket-level timeout so a hung subprocess cannot orphan the executor thread indefinitely.
3. **BrowserFetcher.stop() wrapper** — Added `stop()` method to `BrowserFetcher` so `main.py` can shut down the manager without reaching past the public facade.
4. **GraphDB DRY helpers** — Added `_execute()` and `_fetchall()` helpers to remove repeated `aiosqlite.connect` boilerplate.
5. **Scheduler exception narrowing** — `_passive_capture_job` now catches `(OSError, asyncio.TimeoutError)` instead of bare `Exception`, preventing silent swallowing of coding errors.
6. **Remove `_running` bool** — Scheduler relies on APScheduler's native state; `_running` flag removed to eliminate stale-state bugs.
7. **Subprocess worker tests** — Added `tests/test_subprocess_worker.py` covering fetch, error response, and unknown message types against `_run_loop`.
8. **Missing tests added** — Subprocess start-failure (`test_browser_manager.py`), reschedule exception (`test_scheduler.py`), LLM repair failure (`test_llm_client.py`).

### Deferred
- **SQLite connection pooling** — Added to `TODOS.md` as P2. Evaluate only if profiling shows contention under concurrent ingestion.

- **UNRESOLVED:** 0
- **VERDICT:** ENG CLEARED — ready to implement
