from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
import uvicorn

from aily.config import SETTINGS
from aily.queue.db import QueueDB
from aily.queue.worker import JobWorker
from aily.browser.fetcher import BrowserFetcher, FetchError
from aily.push.feishu import FeishuPusher
from aily.writer.obsidian import ObsidianWriter, ObsidianAPIError
from aily.bot import webhook
from aily.bot.ws_client import get_ws_client
from aily.parser import registry
from aily.parser.parsers import (
    parse_kimi,
    parse_monica,
    parse_arxiv,
    parse_github,
    parse_youtube,
)
from aily.graph.db import GraphDB
from aily.scheduler.jobs import PassiveCaptureScheduler, DailyDigestScheduler, ClaudeCodeCaptureScheduler
from aily.llm.client import LLMClient
from aily.digest.pipeline import DigestPipeline
from aily.agent.registry import AgentRegistry
from aily.agent.agents import (
    summarizer_agent,
    researcher_agent,
    connector_agent,
    zettel_suggester_agent,
)
from aily.agent.pipeline import PlannerPipeline
from aily.learning.loop import LearningLoop
from aily.voice.downloader import FeishuVoiceDownloader, FeishuVoiceError
from aily.voice.transcriber import WhisperTranscriber, TranscriptionError
from aily.network.tailscale import TailscaleClient

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
    queue_db=db,
)
worker: JobWorker | None = None
scheduler: PassiveCaptureScheduler | None = None
llm_client = LLMClient(
    base_url=SETTINGS.llm_base_url,
    api_key=SETTINGS.llm_api_key,
    model=SETTINGS.llm_model,
)
digest_scheduler: DailyDigestScheduler | None = None
learning_loop: LearningLoop | None = None
claude_capture_scheduler: ClaudeCodeCaptureScheduler | None = None
ws_client = None
agent_registry = AgentRegistry()
tailscale_client = TailscaleClient()

ERROR_MESSAGES = {
    "FETCH_FAILED": "Could not fetch the page. The link may be expired or require login.",
    "PARSE_FAILED": "Could not extract content from this page type.",
    "OBSIDIAN_REJECTED": "Obsidian Local REST API plugin is not running. Please start Obsidian and enable the plugin.",
    "OBSIDIAN_TIMEOUT": "Obsidian did not respond. Please check that the vault is open.",
    "PUSH_FAILED": "Saved to Obsidian, but could not send confirmation.",
}


async def _enqueue_url(url: str, open_id: str = "") -> None:
    source = "passive" if not open_id else "manual"
    enqueued = await db.enqueue_url(url, open_id=open_id, source=source)
    if not enqueued:
        logger.info("Deduplicated URL: %s", url)
        return
    logger.info("Enqueued URL: %s", url)


async def _dispatch_job(job: dict) -> None:
    if job["type"] == "url_fetch":
        await _process_url_job(job)
    elif job["type"] == "daily_digest":
        await _process_digest_job(job)
    elif job["type"] == "agent_request":
        await _process_agent_job(job)
    elif job["type"] == "voice_message":
        await _process_voice_job(job)
    elif job["type"] == "claude_session":
        await _process_claude_session_job(job)
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


async def _process_agent_job(job: dict) -> None:
    request = job["payload"]["request"]
    open_id = job["payload"].get("open_id", "")
    pipeline = PlannerPipeline(graph_db, llm_client, agent_registry, writer, pusher)
    await pipeline.run(request=request, open_id=open_id)


async def _process_voice_job(job: dict) -> None:
    """Process a voice message: download, transcribe, and create note."""
    payload = job["payload"]
    file_key = payload["file_key"]
    file_name = payload.get("file_name", "voice.mp3")
    open_id = payload.get("open_id", "")

    # Get Whisper API key (fallback to LLM API key for OpenAI)
    whisper_key = SETTINGS.whisper_api_key or SETTINGS.llm_api_key
    if not whisper_key:
        logger.error("No Whisper API key configured")
        if open_id:
            await pusher.send_message(open_id, "Voice transcription not configured.")
        return

    downloader = FeishuVoiceDownloader(
        app_id=SETTINGS.feishu_app_id,
        app_secret=SETTINGS.feishu_app_secret,
        temp_dir=SETTINGS.voice_temp_dir,
    )
    transcriber = WhisperTranscriber(
        api_key=whisper_key,
        model=SETTINGS.whisper_model,
    )

    try:
        # Download voice file
        download_result = await downloader.download_voice(file_key, file_name)

        # Transcribe
        transcription = await transcriber.transcribe(download_result.file_path)

        if not transcription.text:
            if open_id:
                await pusher.send_message(open_id, "Could not transcribe voice message.")
            return

        # Create note from transcription
        note_title = f"Voice Memo {job['id'][:8]}"
        note_content = f"""# Voice Memo

**Transcribed:** {transcription.text}

**Language:** {transcription.language or "unknown"}
**Duration:** {transcription.duration_seconds or "unknown"}s

**Original file:** {file_name}
"""
        note_path = await writer.write_note(
            note_title,
            note_content,
            f"feishu://voice/{file_key}",
        )

        if open_id:
            await pusher.send_message(
                open_id,
                f"Voice memo transcribed and saved: {note_path}\n\nPreview: {transcription.text[:100]}..."
            )

        logger.info("Voice message processed: %s -> %s", file_key, note_path)

    except FeishuVoiceError as e:
        logger.exception("Failed to download voice message")
        if open_id:
            await pusher.send_message(open_id, f"Failed to download voice: {e}")
        raise
    except TranscriptionError as e:
        logger.exception("Failed to transcribe voice message")
        if open_id:
            await pusher.send_message(open_id, f"Failed to transcribe: {e}")
        raise
    finally:
        await transcriber.close()


async def _process_claude_session_job(job: dict) -> None:
    """Process a Claude Code session capture job."""
    from aily.capture.claude_code import ClaudeCodeSessionCapture, SessionMetadata
    from datetime import datetime, timezone

    file_path = Path(job["payload"]["file_path"])

    try:
        capture = ClaudeCodeSessionCapture()
        entries = await capture.parse_session(file_path)

        if not entries:
            logger.warning("No entries found in session: %s", file_path)
            return

        # Get title from first user message
        title = await capture.get_session_title(entries)

        # Create metadata for formatting
        stat = file_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        session_id = capture._extract_session_id(file_path.name)

        metadata = SessionMetadata(
            session_id=session_id,
            project=None,  # Could extract from first entry
            started_at=mtime,
            file_path=file_path,
        )

        markdown = await capture.format_as_markdown(entries, metadata)
        note_path = await writer.write_note(
            title=f"Claude: {title[:60]}",
            markdown=markdown,
            source_url=f"claude://session/{session_id}",
        )

        logger.info("Claude session captured: %s -> %s", file_path, note_path)

    except Exception:
        logger.exception("Failed to capture Claude session: %s", file_path)
        raise


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


async def _enqueue_claude_session(file_path: Path) -> None:
    await db.enqueue("claude_session", {"file_path": str(file_path)})
    logger.info("Enqueued Claude session capture: %s", file_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker, scheduler, digest_scheduler, learning_loop, claude_capture_scheduler, ws_client
    await db.initialize()
    await graph_db.initialize()

    # Start Feishu WebSocket client for receiving messages
    ws_client = get_ws_client(db)
    ws_client.start()
    logger.info("Feishu WebSocket client started")

    # Check Tailscale status
    try:
        ts_status = await tailscale_client.get_status()
        if ts_status.is_running and ts_status.is_logged_in:
            url = tailscale_client.get_aily_url(ts_status)
            logger.info("Tailscale connected: %s (%s)", ts_status.magic_dns_name or ts_status.ip_addresses[0], url)
        elif ts_status.is_running:
            logger.info("Tailscale running but not logged in")
        else:
            logger.info("Tailscale not running - remote access unavailable")
    except Exception:
        logger.debug("Tailscale status check failed", exc_info=True)
    if SETTINGS.obsidian_vault_path:
        learning_loop = LearningLoop(
            vault_path=Path(SETTINGS.obsidian_vault_path),
            queue_db=db,
            graph_db=graph_db,
            llm=llm_client,
        )
        await learning_loop.start()
    registry.register(r"^https://kimi\.moonshot\.cn/share/", parse_kimi)
    registry.register(r"^https://monica\.im/", parse_monica)
    registry.register(r"^https://arxiv\.org/abs/", parse_arxiv)
    registry.register(r"^https://github\.com/", parse_github)
    registry.register(r"^https://(www\.)?youtube\.com/watch", parse_youtube)
    agent_registry.register("summarizer", summarizer_agent, "Summarize a piece of text into bullets.")
    agent_registry.register("researcher", researcher_agent, "Answer a research question.")
    agent_registry.register("connector", connector_agent, "Find graph connections for a node.")
    agent_registry.register("zettel_suggester", zettel_suggester_agent, "Suggest Zettelkasten links for a note.")
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
    claude_capture_scheduler = ClaudeCodeCaptureScheduler(enqueue_session_fn=_enqueue_claude_session)
    claude_capture_scheduler.start()
    logger.info("Aily startup complete")
    yield
    if ws_client:
        ws_client.stop()
    if learning_loop:
        await learning_loop.stop()
    if claude_capture_scheduler:
        claude_capture_scheduler.stop()
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
