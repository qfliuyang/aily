# Aily — Autopilot Build Spec (Revised)
Generated: 2026-04-05

## Vision
Aily is a personal AI brain for 小刘, a senior chip design engineer. It captures insights from Monica chats, Kimi deep-research reports, and other AI tool outputs, then writes organized notes to his Obsidian vault. Aily runs locally on macOS as a daemon with a Feishu bot interface.

## Architecture Decisions (from CEO + Eng Review)

1. **Phased build** — Week 1: reactive pipeline only. Expansions added as plugin layers.
2. **Browser Use serialization** — In-process `asyncio.Semaphore(1)` for Week 1. Subprocess queue deferred.
3. **Data storage** — Separate SQLite files per concern (`aily_queue.db`, `aily_graph.db`) plus JSONL/YAML.
4. **LLM calls** — Deferred to Week 2. Week 1 uses deterministic parsers.
5. **Entity graph** — Schema defined, but full implementation deferred to Weeks 3-4.
6. **Learning loop** — Draft/staging folder in Obsidian. Implementation deferred.
7. **Passive capture** — Hybrid Phase 1: smart polling with jitter/backoff. Deferred to Week 2.

## Day 0 Prerequisites

1. **Python 3.11+ installed** (`python3.11` is now available at `/opt/homebrew/bin/python3.11`)
2. **Feishu test app registered** — need `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_VERIFICATION_TOKEN`, `FEISHU_ENCRYPT_KEY`
3. **Obsidian Local REST API plugin installed** — `coddingtonbear/obsidian-local-rest-api`
4. **Obsidian REST API key generated** and vault path confirmed
5. **Playwright browsers downloaded** — `playwright install chromium`

## Core Data Flow (Week 1 — Reactive Pipeline)

```
Feishu message (URL)
  → POST /webhook/feishu
  → Verify signature using FEISHU_ENCRYPT_KEY
  → Parse event_id, dedup with 60s TTL
  → Extract URL from text body
  → ACK immediately (200)
  → Enqueue job to aily_queue.db
  → Background async worker dequeues (Semaphore(1))
  → Browser Use agent fetches page
  → Auto-parser registry detects URL type
  → Parser extracts structured markdown
  → Obsidian writer POSTs via Local REST API
  → Feishu confirmation or failure reply
```

## Components to Build (Week 1)

### 0. Project Bootstrap
- `pyproject.toml` with Python 3.11 requirement
- `requirements.txt`
- `.gitignore`
- `pytest.ini` with `pytest-asyncio`

### 1. FastAPI webhook receiver (`aily/bot/webhook.py`)
- `POST /webhook/feishu`
- Verify Feishu signature using encrypt key (reject invalid signatures with 403)
- Parse `event_id`, dedup with 60s TTL (in-memory dict with eviction)
- Extract first URL from text using regex (`https?://\S+`)
- If no URL found, return 200 but do not enqueue (or enqueue as unsupported)
- ACK immediately with JSON `{"challenge": ...}` for Feishu handshake, then `{"status": "ok"}` for events
- Enqueue job to `aily_queue.db`

### 2. SQLite queue (`aily/queue/`)
- `jobs` table:
  ```sql
  CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,        -- 'url_fetch'
    payload TEXT NOT NULL,     -- JSON
    status TEXT NOT NULL,      -- 'pending', 'running', 'completed', 'failed'
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
- `enqueue(type, payload)` → insert pending job
- `dequeue()` → select oldest pending job, atomically update to running
- `complete_job(id, success, error_message)` → update status, set updated_at
- `retry_job(id)` → increment retry_count, reset to pending if < max_retries
- Background worker loop:
  - `asyncio.Semaphore(1)` around job processing (not Browser Use itself)
  - Only one job processed at a time
  - Exponential backoff: 2s, 4s, 8s, max 3 retries
  - On max retry exceeded: mark failed and notify

### 3. Browser fetcher (`aily/browser/fetcher.py`)
- `class BrowserFetcher` wrapping Browser Use agent
- `async def fetch(self, url: str) -> str:`
- Global `asyncio.Semaphore(1)` ensuring only one browser session active at a time
- Uses isolated browser profile at `~/.aily/browser_profile`
- Handles context start/stop to prevent process leaks
- 60-second timeout on page load
- Returns page text or raises `FetchError`
- Gracefully handles empty page content

### 4. Auto-parser registry (`aily/parser/`)
- Registry mapping regex patterns to parser functions
- Pre-defined patterns:
  - `^https://kimi\.moonshot\.cn/share/` → `kimi_report_parser`
  - `^https://monica\.im/` → `monica_chat_parser`
  - `^https://arxiv\.org/abs/` → `arxiv_parser`
  - `^https://github\.com/` → `github_parser`
  - `^https://(www\.)?youtube\.com/watch` → `youtube_parser`
- Generic fallback: extract page title + body text
- Each parser receives raw text and returns structured markdown

### 5. Obsidian writer (`aily/writer/obsidian.py`)
- Uses **Obsidian Local REST API** plugin by coddingtonbear
- Endpoint: `POST http://127.0.0.1:{port}/vault/{path}`
- Headers: `Authorization: Bearer {OBSIDIAN_REST_API_KEY}`, `Content-Type: text/markdown`
- Writes notes to **draft folder first**: `{vault}/Aily Drafts/`
- Frontmatter included:
  ```yaml
  ---
  aily_generated: true
  aily_written_at: "2026-04-05T08:30:00Z"
  source_url: "https://..."
  ---
  ```
- Handles 404 (plugin not running) → actionable error: "Obsidian Local REST API plugin is not running. Please start Obsidian and enable the plugin."
- Handles connection refused → retry once after 2s
- Vault path and port from `.env`

### 6. Feishu push module (`aily/push/feishu.py`)
- Sends text messages back to Feishu via `lark-oapi` SDK
- `send_message(receive_id, content)`
- Confirmation: `"Saved to Obsidian: {note_title}"`
- Failure: clear, actionable error with next step

### 7. Queue worker (`aily/queue/worker.py`)
- Orchestrates the pipeline:
  1. Dequeue URL job
  2. `BrowserFetcher.fetch(url)`
  3. `Registry.detect_parser(url)` → `parser.parse(raw_text)`
  4. `ObsidianWriter.write_note(title, content, source_url)`
  5. `FeishuPush.send_confirmation(...)`
- On any step failure: catch exception, log, retry or fail with notification

### 8. Daemon entrypoint (`aily/main.py`)
- FastAPI app with webhook router
- Config from `.env` via Pydantic Settings
- Background worker `asyncio.create_task(worker_loop())`
- `uvicorn` async server

### 9. Configuration (`aily/config.py`)
- Pydantic BaseSettings reading from `.env`
- Fields:
  - `feishu_app_id`, `feishu_app_secret`, `feishu_verification_token`, `feishu_encrypt_key`
  - `obsidian_rest_api_key`, `obsidian_vault_path`, `obsidian_rest_api_port=27123`
  - `aily_data_dir` (default `~/.aily`)

## File Structure

```
aily/
├── __init__.py
├── main.py                 # Daemon entrypoint
├── config.py               # Pydantic settings from env
├── bot/
│   ├── __init__.py
│   └── webhook.py
├── queue/
│   ├── __init__.py
│   ├── db.py
│   └── worker.py
├── browser/
│   ├── __init__.py
│   └── fetcher.py
├── parser/
│   ├── __init__.py
│   ├── registry.py
│   └── parsers.py
├── writer/
│   ├── __init__.py
│   └── obsidian.py
└── push/
    ├── __init__.py
    └── feishu.py
.env.example
pyproject.toml
requirements.txt
pytest.ini
tests/
├── __init__.py
├── conftest.py
├── test_bot.py
├── test_queue.py
├── test_fetcher.py
├── test_writer.py
└── test_e2e.py
```

## Dependencies (`requirements.txt`)

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
aiosqlite>=0.19.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
lark-oapi>=1.0.0
browser-use>=0.1.0
playwright>=1.40.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
httpx>=0.25.0
aiohttp>=3.9.0
```

## Configuration (`.env.example`)

```
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
FEISHU_ENCRYPT_KEY=
OBSIDIAN_REST_API_KEY=
OBSIDIAN_VAULT_PATH=
OBSIDIAN_REST_API_PORT=27123
AILY_DATA_DIR=~/.aily
```

## Tests Required

1. **`tests/test_bot.py`**
   - Valid webhook with URL → enqueued, returns 200
   - Duplicate `event_id` within 60s → dedup, returns 200
   - Invalid signature → returns 403
   - Missing URL → returns 200, no enqueue

2. **`tests/test_queue.py`**
   - `enqueue(type, payload)` → job in pending state
   - `dequeue()` → returns oldest pending, marks running
   - Job failure → retry_count increments, status back to pending
   - Max retries exceeded → status failed

3. **`tests/test_fetcher.py`**
   - Browser Use fetches local HTML fixture and extracts text
   - Timeout → raises `FetchError`
   - Empty content → returns empty string or raises

4. **`tests/test_writer.py`**
   - Successful write → mocked 200 OK
   - 404 from Obsidian → actionable error raised
   - Connection refused → retry then raise
   - Frontmatter included in payload

5. **`tests/test_e2e.py`**
   - Full flow: mock Feishu webhook → worker processes → mock Obsidian API → mock Feishu push
   - Verify job status transitions to `completed`
   - Verify Obsidian receives expected markdown
   - Verify Feishu push receives success message

## Error Taxonomy (passed through job result)

| Error Code | User-Facing Message |
|------------|---------------------|
| `FETCH_FAILED` | "Could not fetch the page. The link may be expired or require login." |
| `PARSE_FAILED` | "Could not extract content from this page type." |
| `OBSIDIAN_REJECTED` | "Obsidian Local REST API plugin is not running. Please start Obsidian and enable the plugin." |
| `OBSIDIAN_TIMEOUT` | "Obsidian did not respond. Please check that the vault is open." |
| `PUSH_FAILED` | "Saved to Obsidian, but could not send confirmation." |

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
- Feishu signature verification rejects bad payloads
