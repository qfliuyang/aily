# Aily — Autopilot Build Spec
Generated: 2026-04-05

## Vision
Aily is a personal AI brain for 小刘, a senior chip design engineer. It captures insights from Monica chats, Kimi deep-research reports, Claude Code sessions, and voice memos, then writes organized, verifiable notes to his Obsidian vault. Aily runs locally on macOS as a daemon with a Feishu bot interface.

## Architecture Decisions (from CEO + Eng Review)

1. **Phased build** — Week 1: reactive pipeline only. Expansions added as plugin layers.
2. **Browser Use serialization** — Dedicated subprocess/queue for all browser work.
3. **Data storage** — Separate SQLite files per concern (`aily_queue.db`, `aily_graph.db`) plus JSONL/YAML.
4. **LLM calls** — Shared `LLMClient` wrapper with timeout/retry/degrade.
5. **Entity graph** — Standard triple store: `nodes`, `edges`, `occurrences`.
6. **Learning loop** — Draft/staging folder in Obsidian. Only moved-then-edited notes trigger inference.
7. **Passive capture** — Hybrid Phase 1: smart polling with jitter/backoff. Pivot to intercept if banned.

## Core Data Flow (Week 1 — Reactive Pipeline)

```
Feishu message (URL)
  → POST /webhook/feishu
  → FastAPI ACK + enqueue to aily_queue.db
  → Background async worker dequeues
  → BrowserUseManager subprocess fetches page
  → Auto-parser registry detects URL type
  → Parser extracts structured text
  → Obsidian writer posts via Local REST API
  → Feishu confirmation reply
```

## Components to Build (Week 1)

### 1. FastAPI webhook receiver (`aily/bot/`)
- `POST /webhook/feishu`
- Parse `event_id`, dedup with 60s TTL
- Extract URL from text message body
- ACK immediately (200)
- Enqueue job to `aily_queue.db`

### 2. SQLite queue (`aily/queue/`)
- `jobs` table: `id`, `type`, `payload`, `status`, `retry_count`, `created_at`, `updated_at`
- Async worker with `asyncio.Semaphore(1)` for job processing
- Exponential backoff on failure, max 3 retries
- Job status transitions: pending → running → completed | failed

### 3. BrowserUseManager subprocess (`aily/browser/`)
- Subprocess worker that owns Playwright/Browser Use lifecycle
- IPC via multiprocessing Queue or async queue bridge
- Accepts fetch tasks, returns page text or errors
- Only one browser session active at a time
- Handles context start/stop to prevent process leaks

### 4. Auto-parser registry (`aily/parser/`)
- Registry mapping regex patterns to parser functions
- Pre-defined patterns: Monica, Kimi, arXiv, GitHub, YouTube, generic fallback
- Each parser returns structured markdown text

### 5. Obsidian writer (`aily/writer/`)
- Local REST API client
- Writes notes to staging/draft folder first
- Adds frontmatter: `aily_generated: true`, `aily_written_at`
- Handles 404/connection errors with retry

### 6. Feishu push module (`aily/push/`)
- Sends confirmation or failure messages back to Feishu
- Uses `lark-oapi` SDK
- Clear, actionable error messages

### 7. LLM client (`aily/llm/`)
- `LLMClient` class wrapping Anthropic/OpenAI APIs
- Config: 60s timeout, 1 retry, `json-repair` for malformed JSON
- Graceful degradation on failure (returns degrade signal)

### 8. Scheduler (`aily/scheduler/`)
- APScheduler for daily digest (8:30 AM)
- Placeholder for passive capture cron with jitter/backoff

### 9. Daemon entrypoint (`aily/main.py`)
- FastAPI app + scheduler + worker startup
- Configuration from `.env` file
- `uvicorn` async server

## File Structure

```
aily/
├── __init__.py
├── main.py                 # Daemon entrypoint
├── config.py               # Settings from env
├── bot/
│   ├── __init__.py
│   └── webhook.py
├── queue/
│   ├── __init__.py
│   ├── db.py
│   └── worker.py
├── browser/
│   ├── __init__.py
│   ├── manager.py
│   └── subprocess_worker.py
├── parser/
│   ├── __init__.py
│   ├── registry.py
│   └── parsers.py
├── writer/
│   ├── __init__.py
│   └── obsidian.py
├── push/
│   ├── __init__.py
│   └── feishu.py
├── llm/
│   ├── __init__.py
│   └── client.py
└── scheduler/
    ├── __init__.py
    └── jobs.py
.env.example
requirements.txt
pytest.ini
tests/
├── __init__.py
├── test_bot.py
├── test_queue.py
├── test_fetcher.py
├── test_writer.py
└── test_e2e.py
```

## Tech Stack
- Python 3.11+
- FastAPI + uvicorn
- aiosqlite (async SQLite)
- playwright (browser automation)
- browser-use (agent framework on Playwright)
- lark-oapi (Feishu SDK)
- APScheduler
- pytest + pytest-asyncio
- python-dotenv
- json-repair
- aiohttp (HTTP client)

## Configuration (.env)
```
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
FEISHU_ENCRYPT_KEY=
OBSIDIAN_REST_API_KEY=
OBSIDIAN_VAULT_PATH=
OBSIDIAN_REST_API_PORT=27123
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
AILY_DATA_DIR=~/.aily
```

## Tests Required
1. `test_bot.py` — webhook parsing, dedup, invalid URL
2. `test_queue.py` — enqueue/dequeue, retry, max-retry failure
3. `test_fetcher.py` — Browser Use extraction on local HTML fixture
4. `test_writer.py` — Obsidian API mocked responses (200, 404, connection refused)
5. `test_e2e.py` — mocked Feishu outbound + Obsidian API end-to-end

## Constraints
- Must run on macOS locally
- Must handle Chinese text natively
- Browser must use isolated profile (no interference with active sessions)
- All secrets in `.env` only, never committed
- Single-user system

## Success Criteria (Week 1)
- 小刘 sends a Feishu URL → verified Obsidian note draft within 60 seconds
- Invalid URL → clear error reply
- Obsidian plugin down → failure notification with actionable hint
- Duplicate webhook → deduplicated within 60s
- Concurrent URL submissions → serialized, no OOM
