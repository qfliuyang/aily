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
from aily.graph.db import GraphDB
from aily.scheduler.jobs import PassiveCaptureScheduler, DailyDigestScheduler
from aily.llm.client import LLMClient
from aily.digest.pipeline import DigestPipeline

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

db = QueueDB(SETTINGS.queue_db_path)
graph_db = GraphDB(SETTINGS.graph_db_path)
fetcher = BrowserFetcher()
pusher = FeishuPusher(SETTINGS.feishu_app_id, SETTINGS.feishu_app_secret)
writer = ObsidianWriter(
    SETTINGS.obsidian_rest_api_key,
    SETTINGS.obsidian_vault_path,
    SETTINGS.obsidian_rest_api_port,
)
worker: JobWorker | None = None
scheduler: PassiveCaptureScheduler | None = None
llm_client = LLMClient(
    base_url=SETTINGS.llm_base_url,
    api_key=SETTINGS.llm_api_key,
    model=SETTINGS.llm_model,
)
digest_scheduler: DailyDigestScheduler | None = None

ERROR_MESSAGES = {
    "FETCH_FAILED": "Could not fetch the page. The link may be expired or require login.",
    "PARSE_FAILED": "Could not extract content from this page type.",
    "OBSIDIAN_REJECTED": "Obsidian Local REST API plugin is not running. Please start Obsidian and enable the plugin.",
    "OBSIDIAN_TIMEOUT": "Obsidian did not respond. Please check that the vault is open.",
    "PUSH_FAILED": "Saved to Obsidian, but could not send confirmation.",
}


async def _enqueue_url(url: str, open_id: str = "") -> None:
    log_id = await db.insert_raw_log(url, source="passive" if not open_id else "manual")
    if log_id is None:
        logger.info("Deduplicated URL: %s", url)
        return
    await db.enqueue("url_fetch", {"url": url, "open_id": open_id})
    logger.info("Enqueued URL: %s", url)


async def _dispatch_job(job: dict) -> None:
    if job["type"] == "url_fetch":
        await _process_url_job(job)
    elif job["type"] == "daily_digest":
        await _process_digest_job(job)
    else:
        raise ValueError(f"Unknown job type: {job['type']}")


async def _process_url_job(job: dict) -> None:
    url = job["payload"]["url"]
    open_id = job["payload"].get("open_id", "")
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

    if open_id:
        try:
            await pusher.send_message(open_id, f"Saved to Obsidian: {note_path}")
        except Exception:
            logger.exception("Push failed for job %s", job["id"])
            await _notify_failure(open_id, "PUSH_FAILED")


async def _process_digest_job(job: dict) -> None:
    open_id = job["payload"].get("open_id", SETTINGS.aily_digest_feishu_open_id)
    pipeline = DigestPipeline(graph_db, db, llm_client, writer, pusher)
    await pipeline.run(open_id=open_id)


async def _notify_failure(open_id: str, code: str) -> None:
    if not open_id:
        return
    try:
        await pusher.send_message(open_id, ERROR_MESSAGES[code])
    except Exception:
        logger.exception("Failed to send failure notification")


async def _enqueue_digest() -> None:
    if not SETTINGS.aily_digest_enabled:
        return
    open_id = SETTINGS.aily_digest_feishu_open_id
    await db.enqueue("daily_digest", {"open_id": open_id})
    logger.info("Enqueued daily digest")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker, scheduler, digest_scheduler
    await db.initialize()
    await graph_db.initialize()
    registry.register(r"^https://kimi\.moonshot\.cn/share/", parse_kimi)
    registry.register(r"^https://monica\.im/", parse_monica)
    registry.register(r"^https://arxiv\.org/abs/", parse_arxiv)
    registry.register(r"^https://github\.com/", parse_github)
    registry.register(r"^https://(www\.)?youtube\.com/watch", parse_youtube)
    worker = JobWorker(db, _dispatch_job)
    await worker.start()
    scheduler = PassiveCaptureScheduler(enqueue_fn=_enqueue_url)
    scheduler.start()
    digest_scheduler = DailyDigestScheduler(
        enqueue_digest_fn=_enqueue_digest,
        hour=SETTINGS.aily_digest_hour,
        minute=SETTINGS.aily_digest_minute,
    )
    digest_scheduler.start()
    logger.info("Aily startup complete")
    yield
    if digest_scheduler:
        digest_scheduler.stop()
    if scheduler:
        scheduler.stop()
    if worker:
        await worker.stop()
    await fetcher.stop()
    logger.info("Aily shutdown complete")


app = FastAPI(lifespan=lifespan)
app.include_router(webhook.router)


if __name__ == "__main__":
    uvicorn.run("aily.main:app", host="127.0.0.1", port=8000, reload=False)
