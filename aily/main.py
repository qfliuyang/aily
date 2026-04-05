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
