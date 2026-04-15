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
from aily.sessions.dikiwi_mind import DikiwiMind
from aily.sessions.innolaval_scheduler import InnolavalScheduler
from aily.sessions.entrepreneur_scheduler import EntrepreneurScheduler
from aily.llm.provider_routes import PrimaryLLMRoute
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter

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
llm_client = PrimaryLLMRoute.from_settings(SETTINGS)
digest_scheduler: DailyDigestScheduler | None = None
learning_loop: LearningLoop | None = None
claude_capture_scheduler: ClaudeCodeCaptureScheduler | None = None
ws_client = None

# Three-Mind System schedulers
dikiwi_mind: DikiwiMind | None = None
innovation_scheduler: InnolavalScheduler | None = None
entrepreneur_scheduler: EntrepreneurScheduler | None = None
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
    elif job["type"] == "file_attachment":
        await _process_file_job(job)
    elif job["type"] == "image_ocr":
        await _process_image_job(job)
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


async def _process_file_job(job: dict) -> None:
    """Process file attachment (PDF, document, etc) using universal processor."""
    from aily.processing.router import ProcessingRouter
    from aily.voice.downloader import FeishuVoiceDownloader

    payload = job["payload"]
    file_key = payload["file_key"]
    file_name = payload.get("file_name", "document")
    open_id = payload.get("open_id", "")

    logger.info("Processing file attachment: %s (%s)", file_name, file_key)

    # Download file from Feishu
    downloader = FeishuVoiceDownloader(
        app_id=SETTINGS.feishu_app_id,
        app_secret=SETTINGS.feishu_app_secret,
        temp_dir=SETTINGS.voice_temp_dir,
    )

    try:
        # Reuse voice downloader for file download (same API)
        download_result = await downloader.download_voice(file_key, file_name)
        file_bytes = Path(download_result.file_path).read_bytes()

        # Process with universal router
        router = ProcessingRouter()
        result = await router.process(file_bytes, filename=file_name)

        if not result.text or result.text.startswith("["):
            logger.warning("No text extracted from file: %s", file_name)
            if open_id:
                await pusher.send_message(open_id, f"Could not extract text from {file_name}")
            return

        # Create note from extracted content
        safe_title = "".join(c for c in file_name if c.isalnum() or c in " -_").rstrip()
        note_path = await writer.write_note(
            title=f"File: {safe_title[:80]}",
            markdown=result.text,
            source_url=f"feishu://file/{file_key}",
        )

        logger.info("File processed: %s -> %s", file_name, note_path)

        if open_id:
            await pusher.send_message(
                open_id,
                f"Processed {file_name} ({result.source_type}): {note_path}\n\nPreview: {result.text[:100]}..."
            )

    except FeishuVoiceError as e:
        logger.warning("File download failed: %s - %s", file_name, e)
        if open_id:
            await pusher.send_message(open_id, f"Could not download {file_name}: {e}")
        raise
    except Exception as e:
        logger.exception("Failed to process file: %s", file_name)
        if open_id:
            await pusher.send_message(open_id, f"Failed to process {file_name}: {e}")
        raise


async def _process_image_job(job: dict) -> None:
    """Process image with OCR."""
    from aily.processing.router import ProcessingRouter
    from aily.voice.downloader import FeishuVoiceDownloader

    payload = job["payload"]
    image_key = payload["image_key"]
    open_id = payload.get("open_id", "")

    logger.info("Processing image for OCR: %s", image_key)

    # Download image from Feishu
    downloader = FeishuVoiceDownloader(
        app_id=SETTINGS.feishu_app_id,
        app_secret=SETTINGS.feishu_app_secret,
        temp_dir=SETTINGS.voice_temp_dir,
    )

    try:
        download_result = await downloader.download_voice(image_key, "image.png")
        image_bytes = Path(download_result.file_path).read_bytes()

        # Process with universal router (will use ImageProcessor)
        router = ProcessingRouter()
        result = await router.process(image_bytes, filename="image.png")

        if not result.text:
            logger.warning("No text found in image: %s", image_key)
            if open_id:
                await pusher.send_message(open_id, "No text detected in image")
            return

        # Create note from OCR text
        note_path = await writer.write_note(
            title=f"Image OCR {job['id'][:8]}",
            markdown=f"""# Image OCR

**OCR Confidence:** {result.metadata.get('ocr_confidence', 'unknown')}
**Text Blocks:** {result.metadata.get('text_blocks', 0)}

## Extracted Text

{result.text}
""",
            source_url=f"feishu://image/{image_key}",
        )

        logger.info("Image OCR complete: %s -> %s", image_key, note_path)

        if open_id:
            await pusher.send_message(
                open_id,
                f"OCR complete! Found {result.metadata.get('text_blocks', 0)} text blocks.\n\nPreview: {result.text[:100]}..."
            )

    except Exception as e:
        logger.exception("Failed to process image: %s", image_key)
        if open_id:
            await pusher.send_message(open_id, f"Failed to process image: {e}")
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


async def _tool_executor(action: str, **kwargs) -> dict:
    """Execute tools for GStack Agent - actually runs tests, checks, etc."""
    import subprocess
    import os

    if action == "run_tests":
        # Look for test commands in common locations
        test_commands = [
            ["python", "-m", "pytest", "-xvs"],
            ["pytest", "-xvs"],
            ["python", "-m", "unittest", "discover"],
        ]
        for cmd in test_commands:
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60, cwd=os.getcwd()
                )
                return {
                    "passed": result.returncode == 0,
                    "total": len(result.stdout.split("\n")),
                    "coverage": "unknown",
                    "output": result.stdout[:1000] if result.stdout else result.stderr[:1000],
                }
            except Exception:
                continue
        return {"passed": False, "error": "No test runner found"}

    elif action == "health_check":
        # Check if the app can start
        try:
            # Simple import check
            import aily.main
            return {"status": "ok", "checks": {"import": "pass"}}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    elif action == "analyze_codebase":
        # Count files, LOC, etc
        try:
            py_files = list(Path(".").rglob("*.py"))
            total_lines = sum(len(f.read_text().split("\n")) for f in py_files[:50])
            return {
                "files": len(py_files),
                "lines_of_code": total_lines,
                "test_files": len([f for f in py_files if "test" in f.name]),
            }
        except Exception as e:
            return {"error": str(e)}

    return {"status": "unknown_action", "action": action}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker, scheduler, digest_scheduler, learning_loop, claude_capture_scheduler, ws_client
    global dikiwi_mind, innovation_scheduler, entrepreneur_scheduler
    await db.initialize()
    await graph_db.initialize()

    # Initialize Three-Mind System FIRST (needed for WebSocket routing)
    try:
        dikiwi_writer = None
        if SETTINGS.obsidian_vault_path:
            dikiwi_writer = DikiwiObsidianWriter(
                vault_path=SETTINGS.obsidian_vault_path,
                zettelkasten_only=True,
            )

        # DIKIWI Mind - continuous knowledge processing
        dikiwi_mind = DikiwiMind(
            llm_client=llm_client,
            graph_db=graph_db,
            enabled=SETTINGS.minds.dikiwi_enabled,
            obsidian_writer=writer,
            dikiwi_obsidian_writer=dikiwi_writer,
        )
        logger.info("DIKIWI Mind initialized (enabled=%s)", SETTINGS.minds.dikiwi_enabled)
    except Exception:
        logger.exception("Failed to initialize DIKIWI Mind")
        dikiwi_mind = None

    # Start Feishu WebSocket client for receiving messages
    # Pass dikiwi_mind for Three-Mind message routing
    # Note: feishu_input_channel is None here (legacy gating system), we use DIKIWI now
    ws_client = get_ws_client(db, pusher, None, dikiwi_mind)
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

    # Three-Mind System is the primary architecture
    # All inputs flow through DIKIWI Mind (WebSocket -> _route_to_dikiwi -> process_input)
    logger.info("Three-Mind System active: DIKIWI (continuous) + Innovation (8am) + Entrepreneur (9am)")

    if SETTINGS.obsidian_vault_path:
        learning_loop = LearningLoop(
            vault_path=Path(SETTINGS.obsidian_vault_path),
            queue_db=db,
            graph_db=graph_db,
            llm=llm_client,
        )
        await learning_loop.start()
    registry.register(r"^https://(www\.)?kimi\.(moonshot\.cn|com)/share/", parse_kimi)
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

    # Initialize and start Innovation and Entrepreneur Minds
    # (DIKIWI Mind was already initialized earlier for WebSocket routing)
    try:
        # Innovation Mind - Innolaval: 8 methods running in parallel
        from aily.sessions.innolaval_scheduler import NozzleConfig
        nozzle_config = NozzleConfig(
            min_confidence=SETTINGS.minds.proposal_min_confidence,
            max_proposals_per_session=SETTINGS.minds.proposal_max_per_session,
        )
        innovation_scheduler = InnolavalScheduler(
            llm_client=llm_client,
            graph_db=graph_db,
            obsidian_writer=writer,
            feishu_pusher=pusher,
            schedule_hour=SETTINGS.minds.innovation_time.hour,
            schedule_minute=SETTINGS.minds.innovation_time.minute,
            circuit_breaker_threshold=SETTINGS.minds.circuit_breaker_threshold,
            enabled=SETTINGS.minds.innovation_enabled,
            nozzle_config=nozzle_config,
        )
        if SETTINGS.minds.innovation_enabled:
            innovation_scheduler.start()
            logger.info("Innolaval Innovation Mind started (8am daily - 8 methods in parallel)")

        # Entrepreneur Mind - 9am daily GStack analysis with agentic execution
        entrepreneur_scheduler = EntrepreneurScheduler(
            llm_client=llm_client,
            graph_db=graph_db,
            innovation_scheduler=innovation_scheduler,
            obsidian_writer=writer,
            feishu_pusher=pusher,
            schedule_hour=SETTINGS.minds.entrepreneur_time.hour,
            schedule_minute=SETTINGS.minds.entrepreneur_time.minute,
            proposal_min_confidence=SETTINGS.minds.proposal_min_confidence,
            proposal_max_per_session=SETTINGS.minds.proposal_max_per_session,
            circuit_breaker_threshold=SETTINGS.minds.circuit_breaker_threshold,
            enabled=SETTINGS.minds.entrepreneur_enabled,
            tool_executor=_tool_executor,
        )
        if SETTINGS.minds.entrepreneur_enabled:
            entrepreneur_scheduler.start()
            logger.info("Entrepreneur Mind (Agentic) started (9am daily GStack with real actions)")

        # Wire Entrepreneur into DIKIWI Mind for per-pipeline business evaluation
        if dikiwi_mind and entrepreneur_scheduler:
            dikiwi_mind.entrepreneur_scheduler = entrepreneur_scheduler

        logger.info("Three-Mind System initialized")
    except Exception:
        logger.exception("Failed to initialize Three-Mind System")
        # Don't raise - system can work without minds

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
    # Shutdown Three-Mind System
    if innovation_scheduler:
        innovation_scheduler.stop()
    if entrepreneur_scheduler:
        entrepreneur_scheduler.stop()
    if worker:
        await worker.stop()
    await fetcher.stop()
    logger.info("Aily shutdown complete")


app = FastAPI(lifespan=lifespan)
app.include_router(webhook.router)


if __name__ == "__main__":
    uvicorn.run("aily.main:app", host="127.0.0.1", port=8000, reload=False)
