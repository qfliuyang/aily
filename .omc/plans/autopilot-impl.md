# Aily — Week 1 Reactive Pipeline Implementation Plan (Revised)

**Goal:** Build the end-to-end reactive URL pipeline so 小刘 can send a Feishu URL and receive a verified Obsidian draft within 60 seconds.

**Environment Constraints:**
- macOS local daemon
- Python 3.11+ required (`/opt/homebrew/bin/python3.11` installed)
- Single-user system; secrets live in `.env` only.
- Browser Use serialized in-process via `asyncio.Semaphore(1)`

---

## 1. Exact File-by-File Build Order

### Phase A: Bootstrap + Config
1. `pyproject.toml`
2. `requirements.txt`
3. `.gitignore`
4. `pytest.ini`
5. `.env.example`
6. `aily/__init__.py`
7. `aily/config.py`

### Phase B: Queue + Worker
8. `aily/queue/__init__.py`
9. `aily/queue/db.py`
10. `aily/queue/worker.py`
11. `tests/test_queue.py`

### Phase C: IO Clients
12. `aily/push/__init__.py`
13. `aily/push/feishu.py`
14. `aily/writer/__init__.py`
15. `aily/writer/obsidian.py`
16. `tests/test_writer.py`

### Phase D: Browser + Parser
17. `aily/browser/__init__.py`
18. `aily/browser/fetcher.py`
19. `aily/parser/__init__.py`
20. `aily/parser/parsers.py`
21. `aily/parser/registry.py`
22. `tests/test_fetcher.py`

### Phase E: Bot Webhook
23. `aily/bot/__init__.py`
24. `aily/bot/webhook.py`
25. `tests/test_bot.py`

### Phase F: Integration + E2E
26. `aily/main.py`
27. `tests/test_e2e.py`

---

## 2. Per-File Implementation Spec

### File 1: `pyproject.toml`

```toml
[project]
name = "aily"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "aiosqlite>=0.19.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "lark-oapi>=1.0.0",
    "browser-use>=0.1.0",
    "playwright>=1.40.0",
    "httpx>=0.25.0",
    "aiohttp>=3.9.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
]
```

---

### File 2: `requirements.txt`

```text
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

---

### File 3: `.gitignore`

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.env
.venv/
venv/
*.db
.pytest_cache/
.mypy_cache/
~/.aily/
```

---

### File 4: `pytest.ini`

```ini
[pytest]
asyncio_mode = auto
```

---

### File 5: `.env.example`

```bash
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
FEISHU_ENCRYPT_KEY=
OBSIDIAN_REST_API_KEY=
OBSIDIAN_VAULT_PATH=
OBSIDIAN_REST_API_PORT=27123
AILY_DATA_DIR=~/.aily
```

---

### File 6-7: `aily/config.py`

```python
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    feishu_app_id: str
    feishu_app_secret: str
    feishu_verification_token: str
    feishu_encrypt_key: str
    obsidian_rest_api_key: str
    obsidian_vault_path: str
    obsidian_rest_api_port: int = 27123
    aily_data_dir: Path = Path.home() / ".aily"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def queue_db_path(self) -> Path:
        return self.aily_data_dir / "aily_queue.db"


SETTINGS = Settings()
```

---

### File 8-10: `aily/queue/db.py`

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','running','completed','failed')),
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
```

**Class:** `QueueDB`

```python
import json
import uuid
from pathlib import Path
from typing import Optional

import aiosqlite


class QueueDB:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','running','completed','failed')),
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at)"
            )
            await db.commit()

    async def enqueue(self, job_type: str, payload: dict) -> str:
        job_id = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO jobs (id, type, payload, status) VALUES (?, ?, ?, ?)",
                (job_id, job_type, json.dumps(payload), "pending"),
            )
            await db.commit()
        return job_id

    async def dequeue(self) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                "SELECT id, type, payload, retry_count FROM jobs WHERE status = ? ORDER BY created_at LIMIT 1",
                ("pending",),
            )
            row = await cursor.fetchone()
            if row is None:
                await db.commit()
                return None
            job_id, job_type, payload, retry_count = row
            await db.execute(
                "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                ("running", job_id),
            )
            await db.commit()
            return {
                "id": job_id,
                "type": job_type,
                "payload": json.loads(payload),
                "retry_count": retry_count,
            }

    async def complete_job(self, job_id: str, success: bool, error_message: Optional[str] = None) -> None:
        status = "completed" if success else "failed"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, error_message, job_id),
            )
            await db.commit()

    async def retry_job(self, job_id: str, max_retries: int = 3) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT retry_count FROM jobs WHERE id = ?", (job_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return False
            retry_count = row[0] + 1
            if retry_count >= max_retries:
                await db.execute(
                    "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    ("failed", job_id),
                )
            else:
                await db.execute(
                    "UPDATE jobs SET retry_count = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (retry_count, "pending", job_id),
                )
            await db.commit()
            return retry_count < max_retries
```

---

### File 11: `aily/queue/worker.py`

```python
import asyncio
import logging
from typing import Callable, Awaitable

from aily.queue.db import QueueDB

logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(
        self,
        db: QueueDB,
        processor: Callable[[dict], Awaitable[None]],
        poll_interval: float = 2.0,
    ) -> None:
        self.db = db
        self.processor = processor
        self.poll_interval = poll_interval
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            job = await self.db.dequeue()
            if job is None:
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.poll_interval
                    )
                except asyncio.TimeoutError:
                    continue
                return
            try:
                await self.processor(job)
                await self.db.complete_job(job["id"], success=True)
            except Exception as exc:
                logger.exception("Job %s failed", job["id"])
                will_retry = await self.db.retry_job(job["id"])
                if not will_retry:
                    await self.db.complete_job(job["id"], success=False, error_message=str(exc))
```

---

### File 12-13: `aily/push/feishu.py`

```python
from __future__ import annotations

import json

from lark_oapi import Client
from lark_oapi.api.im.v1 import (
    CreateMessageRequestBodyBuilder,
    CreateMessageRequestBuilder,
)


class FeishuPusher:
    def __init__(self, app_id: str, app_secret: str) -> None:
        self.client = (
            Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .build()
        )

    async def send_message(self, receive_id: str, content: str) -> bool:
        body = (
            CreateMessageRequestBodyBuilder()
            .receive_id(receive_id)
            .msg_type("text")
            .content(json.dumps({"text": content}, ensure_ascii=False))
            .build()
        )
        req = (
            CreateMessageRequestBuilder()
            .receive_id_type("open_id")
            .request_body(body)
            .build()
        )
        resp = await self.client.im.v1.message.create.arequest(req)
        return resp.success()
```

---

### File 14-15: `aily/writer/obsidian.py`

```python
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp


class ObsidianAPIError(Exception):
    pass


class ObsidianWriter:
    def __init__(
        self,
        api_key: str,
        vault_path: str,
        port: int = 27123,
        draft_folder: str = "Aily Drafts",
    ) -> None:
        self.api_key = api_key
        self.vault_path = Path(vault_path)
        self.base_url = f"http://127.0.0.1:{port}"
        self.draft_folder = draft_folder

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "text/markdown",
        }

    def _file_path(self, title: str) -> str:
        safe = title.replace("/", "_")[:120]
        return f"{self.draft_folder}/{safe}.md"

    def _frontmatter(self, source_url: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return f"---\naily_generated: true\naily_written_at: \"{ts}\"\nsource_url: \"{source_url}\"\n---\n\n"

    async def write_note(
        self,
        title: str,
        markdown: str,
        source_url: str,
    ) -> str:
        path = self._file_path(title)
        payload = self._frontmatter(source_url) + markdown
        async with aiohttp.ClientSession() as session:
            try:
                await self._put_with_retry(session, path, payload, retries=1)
            except aiohttp.ClientConnectionError as exc:
                await asyncio.sleep(2)
                try:
                    await self._put_with_retry(session, path, payload, retries=0)
                except aiohttp.ClientConnectionError:
                    raise ObsidianAPIError(
                        "Obsidian Local REST API plugin is not running. Please start Obsidian and enable the plugin."
                    ) from exc
            except Exception as exc:
                raise ObsidianAPIError(str(exc)) from exc
        return path

    async def _put_with_retry(
        self,
        session: aiohttp.ClientSession,
        path: str,
        payload: str,
        retries: int,
    ) -> None:
        url = f"{self.base_url}/vault/{path}"
        async with session.put(url, headers=self._headers(), data=payload) as resp:
            if resp.status == 404:
                raise ObsidianAPIError(
                    "Obsidian Local REST API plugin is not running. Please start Obsidian and enable the plugin."
                )
            resp.raise_for_status()
```

---

### File 16-17: `aily/browser/fetcher.py`

```python
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from browser_use import Agent
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

_BROWSER_SEMAPHORE = asyncio.Semaphore(1)


class FetchError(Exception):
    pass


class BrowserFetcher:
    def __init__(self, profile_dir: Path | None = None) -> None:
        self.profile_dir = profile_dir or (Path.home() / ".aily" / "browser_profile")
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    async def fetch(self, url: str, timeout: int = 60) -> str:
        async with _BROWSER_SEMAPHORE:
            try:
                return await asyncio.wait_for(
                    self._fetch_text(url), timeout=timeout
                )
            except asyncio.TimeoutError as exc:
                raise FetchError(f"Timeout fetching {url}") from exc
            except Exception as exc:
                raise FetchError(str(exc)) from exc

    async def _fetch_text(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=True,
            )
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="networkidle")
                text = await page.inner_text("body")
                return text or ""
            finally:
                await browser.close()
```

---

### File 18-20: Parser Registry

#### `aily/parser/parsers.py`

```python
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParseResult:
    title: str
    markdown: str
    source_type: str


def _extract_title(raw_html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip())
    m = re.search(r"<h1[^>]*>(.*?)</h1>", raw_html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1)).strip())
    return "Untitled"


def parse_kimi(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="kimi")


def parse_monica(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="monica")


def parse_arxiv(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="arxiv")


def parse_github(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="github")


def parse_youtube(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="youtube")


def parse_generic(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="generic")
```

#### `aily/parser/registry.py`

```python
from __future__ import annotations

import re
from typing import Callable

from aily.parser.parsers import ParseResult, parse_generic

_REGISTRY: list[tuple[re.Pattern, Callable[[str, str], ParseResult]]] = []


def register(pattern: str, parser: Callable[[str, str], ParseResult]) -> None:
    _REGISTRY.append((re.compile(pattern), parser))


def detect_parser(url: str) -> Callable[[str, str], ParseResult]:
    for pat, fn in _REGISTRY:
        if pat.search(url):
            return fn
    return parse_generic


def parse(url: str, raw_text: str) -> ParseResult:
    parser = detect_parser(url)
    return parser(url, raw_text)
```

---

### File 21-22: `aily/bot/webhook.py`

```python
from __future__ import annotations

import base64
import hmac
import hashlib
import json
import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Request, HTTPException

from aily.config import SETTINGS
from aily.queue.db import QueueDB

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory dedup cache: event_id -> timestamp
dedup_cache: dict[str, float] = {}
DEDUP_TTL = 60.0


def _extract_url(text: str) -> Optional[str]:
    m = re.search(r"https?://\S+", text)
    return m.group(0) if m else None


def _clean_dedup() -> None:
    now = time.time()
    expired = [k for k, v in dedup_cache.items() if now - v > DEDUP_TTL]
    for k in expired:
        dedup_cache.pop(k, None)


def _verify_signature(body: bytes, timestamp: str, signature: str, encrypt_key: str) -> bool:
    if not signature or not timestamp:
        return False
    sign = signature[len("sha256="):]
    expected = hmac.new(
        encrypt_key.encode(),
        f"{timestamp}\n{body.decode()}\n".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sign, expected)


@router.post("/webhook/feishu")
async def feishu_webhook(request: Request) -> dict:
    body = await request.body()
    timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
    signature = request.headers.get("X-Lark-Signature", "")

    if not _verify_signature(body, timestamp, signature, SETTINGS.feishu_encrypt_key):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = json.loads(body)

    if "challenge" in data:
        return {"challenge": data["challenge"]}

    event_id = data.get("header", {}).get("event_id", "")
    _clean_dedup()
    now = time.time()
    if event_id in dedup_cache:
        return {"status": "ok"}
    dedup_cache[event_id] = now

    event = data.get("event", {})
    message = event.get("message", {})
    if message.get("message_type") != "text":
        return {"status": "ok"}

    content = json.loads(message.get("content", "{}"))
    text = content.get("text", "")
    url = _extract_url(text)

    if url is None:
        return {"status": "ok"}

    db = QueueDB(SETTINGS.queue_db_path)
    await db.initialize()
    open_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")
    await db.enqueue("url_fetch", {"url": url, "open_id": open_id})
    logger.info("Enqueued URL from Feishu: %s", url)
    return {"status": "ok"}
```

---

### File 23: `aily/main.py`

```python
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from aily.config import SETTINGS
from aily.queue.db import QueueDB
from aily.queue.worker import JobWorker
from aily.browser.fetcher import BrowserFetcher, FetchError
from aily.push.feishu import FeishuPusher
from aily.writer.obsidian import ObsidianWriter, ObsidianAPIError
from aily.bot import webhook
from aily.parser import registry
from aily.parser.parsers import (
    parse_kimi,
    parse_monica,
    parse_arxiv,
    parse_github,
    parse_youtube,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

db = QueueDB(SETTINGS.queue_db_path)
fetcher = BrowserFetcher()
pusher = FeishuPusher(SETTINGS.feishu_app_id, SETTINGS.feishu_app_secret)
writer = ObsidianWriter(
    SETTINGS.obsidian_rest_api_key,
    SETTINGS.obsidian_vault_path,
    SETTINGS.obsidian_rest_api_port,
)
worker: JobWorker | None = None


ERROR_MESSAGES = {
    "FETCH_FAILED": "Could not fetch the page. The link may be expired or require login.",
    "PARSE_FAILED": "Could not extract content from this page type.",
    "OBSIDIAN_REJECTED": "Obsidian Local REST API plugin is not running. Please start Obsidian and enable the plugin.",
    "OBSIDIAN_TIMEOUT": "Obsidian did not respond. Please check that the vault is open.",
    "PUSH_FAILED": "Saved to Obsidian, but could not send confirmation.",
}


async def process_job(job: dict) -> None:
    url = job["payload"]["url"]
    open_id = job["payload"]["open_id"]
    note_path = ""
    try:
        raw_text = await fetcher.fetch(url)
        parsed = registry.parse(url, raw_text)
        note_path = await writer.write_note(parsed.title, parsed.markdown, url)
    except FetchError as exc:
        await _notify_failure(open_id, "FETCH_FAILED")
        raise
    except ObsidianAPIError:
        await _notify_failure(open_id, "OBSIDIAN_REJECTED")
        raise
    except Exception:
        await _notify_failure(open_id, "PARSE_FAILED")
        raise

    try:
        await pusher.send_message(open_id, f"Saved to Obsidian: {note_path}")
    except Exception:
        logger.exception("Push failed for job %s", job["id"])
        await _notify_failure(open_id, "PUSH_FAILED")


async def _notify_failure(open_id: str, code: str) -> None:
    try:
        await pusher.send_message(open_id, ERROR_MESSAGES[code])
    except Exception:
        logger.exception("Failed to send failure notification")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker
    await db.initialize()
    registry.register(r"^https://kimi\.moonshot\.cn/share/", parse_kimi)
    registry.register(r"^https://monica\.im/", parse_monica)
    registry.register(r"^https://arxiv\.org/abs/", parse_arxiv)
    registry.register(r"^https://github\.com/", parse_github)
    registry.register(r"^https://(www\.)?youtube\.com/watch", parse_youtube)
    worker = JobWorker(db, process_job)
    await worker.start()
    logger.info("Aily startup complete")
    yield
    if worker:
        await worker.stop()
    logger.info("Aily shutdown complete")


app = FastAPI(lifespan=lifespan)
app.include_router(webhook.router)


if __name__ == "__main__":
    uvicorn.run("aily.main:app", host="127.0.0.1", port=8000, reload=False)
```

---

## 3. Test Spec

### `tests/test_queue.py`

- `test_enqueue` → job in pending state
- `test_dequeue` → returns oldest pending, marks running
- `test_retry_and_fail` → retry_count increments, max retries exceeded → failed

### `tests/test_writer.py`

- `test_successful_write` → mock 200 OK, verify frontmatter
- `test_404` → actionable `ObsidianAPIError`
- `test_connection_refused` → retry once then raise

### `tests/test_fetcher.py`

- `test_fetch_local_html` → Browser Use fetches local HTML fixture and extracts text
- `test_timeout` → raises `FetchError`
- `test_empty_content` → returns empty string

### `tests/test_bot.py`

- `test_valid_webhook_with_url` → enqueued, returns 200
- `test_duplicate_event_id` → dedup within 60s, returns 200
- `test_invalid_signature` → returns 403
- `test_missing_url` → returns 200, no enqueue
- `test_challenge` → returns challenge response

### `tests/test_e2e.py`

- Mock Feishu webhook → worker processes → mock Obsidian API → mock Feishu push
- Verify job transitions to completed
- Verify Obsidian receives expected markdown with frontmatter
- Verify Feishu push receives success message

---

## 4. Critical Trade-offs

### Browser Use in-process Semaphore
- **Why:** Week 1 scope was simplified after critic review. Subprocess queue deferred.
- **Risk:** Playwright process leak if code crashes mid-session. Mitigated by `async with` context manager on browser context.

### Feishu Signature Verification
- HMAC-SHA256 over `timestamp\nbody\n` using `FEISHU_ENCRYPT_KEY`. Rejects invalid signatures with 403.

### Obsidian Draft Folder
- All notes written to `Aily Drafts/{title}.md` with frontmatter. If the folder does not exist, the Local REST API should create it automatically.
