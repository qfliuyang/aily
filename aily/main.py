from __future__ import annotations

import asyncio
import importlib.util
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile
from fastapi import Request
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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
from aily.sessions.reactor_scheduler import ReactorScheduler
from aily.sessions.entrepreneur_scheduler import EntrepreneurScheduler
from aily.llm.provider_routes import PrimaryLLMRoute
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter
from aily.gating.drainage import RainDrop, RainType, StreamType
from aily.processing.canonical_markdown import CanonicalMarkdownConverter
from aily.processing.router import ProcessingRouter
from aily.runtime.backpressure import provider_backpressure
from aily.inbox import WatchedInboxService
from aily.orchestration.checkpoint import async_sqlite_checkpointer
from aily.orchestration.runs import WorkflowRunStore
from aily.orchestration.source_foundation_graph import (
    SourceFoundationDependencies,
    build_source_foundation_graph,
)
from aily.source_store import SourceJobCapacityError, SourceStore
from aily.ui.events import emit_ui_event, ui_event_hub
from aily.ui.router import create_ui_router
from aily.verify.run_registry import RunRegistry
from aily.security.audit import AuditLogger
from aily.security.backup import create_backup, restore_backup
from aily.security.rate_limit import FixedWindowRateLimiter

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
FRONTEND_DIST_PATH = Path(__file__).resolve().parent.parent / "frontend" / "dist"
HAS_MULTIPART = importlib.util.find_spec("python_multipart") is not None

db = QueueDB(SETTINGS.queue_db_path)
graph_db = GraphDB(SETTINGS.graph_db_path)
source_store = SourceStore(
    SETTINGS.source_store_db_path,
    SETTINGS.source_object_dir,
    SETTINGS.canonical_markdown_dir,
)
workflow_run_store = WorkflowRunStore(SETTINGS.workflow_runs_db_path)
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
llm_resolver = PrimaryLLMRoute.build_settings_resolver(SETTINGS)
llm_client = llm_resolver("default")
digest_scheduler: DailyDigestScheduler | None = None
learning_loop: LearningLoop | None = None
claude_capture_scheduler: ClaudeCodeCaptureScheduler | None = None
ws_client = None
browser_manager_instance = None
ui_upload_tasks: dict[str, asyncio.Task[Any]] = {}
source_worker_tasks: list[asyncio.Task[Any]] = []
source_worker_stop: asyncio.Event | None = None
inbox_watcher: WatchedInboxService | None = None
workflow_tasks: dict[str, asyncio.Task[Any]] = {}
ui_upload_semaphore = asyncio.Semaphore(max(1, SETTINGS.ui_upload_concurrency))
ui_rate_limiter = FixedWindowRateLimiter(
    max_requests=max(1, SETTINGS.ui_rate_limit_requests),
    window_seconds=max(1.0, SETTINGS.ui_rate_limit_window_seconds),
) if SETTINGS.hosted_mode else None
audit_logger = AuditLogger(SETTINGS.resolved_audit_log_path)

# Three-Mind System schedulers
dikiwi_mind: DikiwiMind | None = None
innovation_scheduler: ReactorScheduler | None = None
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


def _retry_delay_for_attempt(attempt_count: int) -> float:
    base = max(1.0, float(SETTINGS.source_retry_base_delay_seconds))
    cap = max(base, float(SETTINGS.source_retry_max_delay_seconds))
    return min(cap, base * (2 ** max(0, attempt_count - 1)))


def _is_retryable_processing_error(message: str) -> bool:
    lowered = (message or "").lower()
    retry_markers = (
        "timed out",
        "timeout",
        "llm failed",
        "provider",
        "rate limit",
        "temporarily",
        "connection",
        "network",
        "circuit breaker",
    )
    return any(marker in lowered for marker in retry_markers)


def _failed_stage(result: Any) -> Any | None:
    return next((stage for stage in getattr(result, "stage_results", []) if not stage.success), None)


def _stage_provider_model(result: Any, stage: Any | None) -> tuple[str, str]:
    data = getattr(stage, "data", {}) if stage else {}
    return str(data.get("provider", "")), str(data.get("model", ""))


def _source_queue_active_count(counts: dict[str, int]) -> int:
    return int(counts.get("queued", 0)) + int(counts.get("retry_pending", 0)) + int(counts.get("running", 0))


async def _ensure_source_queue_capacity(additional_jobs: int) -> None:
    max_pending = int(SETTINGS.source_job_max_pending)
    if max_pending <= 0 or additional_jobs <= 0:
        return
    counts = await source_store.get_source_job_counts()
    active = _source_queue_active_count(counts)
    if active + additional_jobs > max_pending:
        await emit_ui_event(
            "source_queue_rejected",
            active_jobs=active,
            requested_jobs=additional_jobs,
            max_pending=max_pending,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "source_queue_full",
                "active_jobs": active,
                "requested_jobs": additional_jobs,
                "max_pending": max_pending,
            },
        )


def _should_enqueue_upload_source(source_record: dict[str, Any]) -> bool:
    if not source_record.get("duplicate"):
        return True
    return str(source_record.get("status") or "") in {
        "stored",
        "deferred",
        "failed",
        "failed_retry_exhausted",
        "cancelled",
        "retry_pending",
    }


def _canonical_markdown_converter() -> CanonicalMarkdownConverter:
    return CanonicalMarkdownConverter(source_store=source_store)


async def _process_dikiwi_ingestion(drop: RainDrop) -> Any:
    if not dikiwi_mind:
        raise RuntimeError("DIKIWI Mind is not initialized")
    if (
        SETTINGS.dikiwi_foundation_only_ingestion
        and hasattr(dikiwi_mind, "process_input_foundation")
        and not getattr(dikiwi_mind, "_drop_requests_full_dikiwi", lambda _drop: False)(drop)
    ):
        return await dikiwi_mind.process_input_foundation(drop)
    return await dikiwi_mind.process_input(drop)


async def _process_source_job_with_foundation_graph(job: dict[str, Any]) -> str:
    payload = dict(job.get("payload") or {})
    source_id = str(job.get("source_id") or payload.get("source_id") or "")
    job_id = str(job.get("job_id") or payload.get("job_id") or "")
    job_type = str(job.get("job_type") or payload.get("job_type") or "")
    input_summary = source_id
    if job_type == "process_url_source":
        source = await source_store.get_source(source_id)
        input_summary = str((source or {}).get("normalized_source") or payload.get("url") or source_id)
    run = await workflow_run_store.create_run(
        workflow_kind="source_foundation",
        input_summary=input_summary[:500],
        metadata={
            "source_id": source_id,
            "job_id": job_id,
            "job_type": job_type,
            "job_payload": {
                **payload,
                "source_id": source_id,
                "job_id": job_id,
                "job_type": job_type,
            },
        },
    )
    await emit_ui_event(
        "workflow_run_queued",
        workflow_run_id=run.workflow_run_id,
        workflow_kind=run.workflow_kind,
        source_id=source_id,
        job_id=job_id,
        job_type=job_type,
    )
    await workflow_run_store.update_status(
        run.workflow_run_id,
        status="running",
        current_node="source_foundation",
        metadata={"source_id": source_id, "job_id": job_id, "job_type": job_type},
    )
    await emit_ui_event(
        "workflow_run_started",
        workflow_run_id=run.workflow_run_id,
        workflow_kind=run.workflow_kind,
        source_id=source_id,
        job_id=job_id,
        job_type=job_type,
    )
    dependencies = SourceFoundationDependencies(
        source_store=source_store,
        processing_router_factory=lambda: ProcessingRouter(browser_manager=browser_manager_instance),
        canonical_markdown_converter_factory=_canonical_markdown_converter,
        dikiwi_ingestion=_process_dikiwi_ingestion,
        emit_event=emit_ui_event,
        browser_manager=browser_manager_instance,
        workflow_run_store=workflow_run_store,
        failed_stage=_failed_stage,
    )
    state = {
        "workflow_run_id": run.workflow_run_id,
        "langgraph_thread_id": run.langgraph_thread_id,
        "workflow_kind": "source_foundation",
        "status": "queued",
        "steps": [],
        "source_id": source_id,
        "job_id": job_id,
        "job_type": job_type,
        "metadata": {
            "source_id": source_id,
            "job_id": job_id,
            "job_type": job_type,
            "job_payload": {
                **payload,
                "source_id": source_id,
                "job_id": job_id,
                "job_type": job_type,
            },
        },
    }
    config = {"configurable": {"thread_id": run.langgraph_thread_id}}
    try:
        async with async_sqlite_checkpointer(SETTINGS.langgraph_checkpoint_db_path) as checkpointer:
            graph = build_source_foundation_graph(checkpointer, dependencies=dependencies)
            result = await graph.ainvoke(state, config)
    except Exception as exc:
        error = str(exc)
        await workflow_run_store.update_status(
            run.workflow_run_id,
            status="failed",
            current_node="source_foundation",
            last_error=error,
        )
        await emit_ui_event(
            "workflow_run_failed",
            workflow_run_id=run.workflow_run_id,
            workflow_kind=run.workflow_kind,
            source_id=source_id,
            job_id=job_id,
            job_type=job_type,
            error=error,
        )
        raise
    if result.get("status") == "completed":
        await emit_ui_event(
            "workflow_run_completed",
            workflow_run_id=run.workflow_run_id,
            workflow_kind=run.workflow_kind,
            source_id=source_id,
            job_id=job_id,
            job_type=job_type,
            pipeline_id=result.get("pipeline_id"),
            final_stage=result.get("final_stage"),
        )
        return "completed"
    error = str(result.get("error") or "source foundation graph failed")
    await workflow_run_store.update_status(
        run.workflow_run_id,
        status="failed",
        current_node=str(result.get("current_node") or "source_foundation"),
        last_error=error,
    )
    await emit_ui_event(
        "workflow_run_failed",
        workflow_run_id=run.workflow_run_id,
        workflow_kind=run.workflow_kind,
        source_id=source_id,
        job_id=job_id,
        job_type=job_type,
        error=error,
    )
    return f"failed:{error}"


async def _process_dikiwi_batch_ingestion(drops: list[RainDrop]) -> Any:
    if not dikiwi_mind:
        raise RuntimeError("DIKIWI Mind is not initialized")
    try:
        return await dikiwi_mind.process_inputs_batched(
            drops,
            foundation_only=SETTINGS.dikiwi_foundation_only_ingestion,
        )
    except TypeError as exc:
        if "foundation_only" not in str(exc):
            raise
        return await dikiwi_mind.process_inputs_batched(drops)


def _source_foundation_graph_enabled(job: dict[str, Any]) -> bool:
    return (
        SETTINGS.orchestrator_enabled
        and not SETTINGS.orchestrator_shadow_mode
        and job.get("job_type") in {"process_upload_source", "process_url_source"}
    )


def _workflow_snapshot_payload(snapshot: Any) -> dict[str, Any]:
    return {
        "workflow_run_id": snapshot.workflow_run_id,
        "langgraph_thread_id": snapshot.langgraph_thread_id,
        "workflow_kind": snapshot.workflow_kind,
        "status": snapshot.status,
        "current_node": snapshot.current_node,
        "input_summary": snapshot.input_summary,
        "metadata": snapshot.metadata,
        "created_at": snapshot.created_at,
        "updated_at": snapshot.updated_at,
        "completed_at": snapshot.completed_at,
        "last_error": snapshot.last_error,
    }


async def _enqueue_url(url: str, open_id: str = "") -> None:
    source = "passive" if not open_id else "manual"
    enqueued = await db.enqueue_url(url, open_id=open_id, source=source)
    if not enqueued:
        logger.info("Deduplicated URL: %s", url)
        return
    logger.info("Enqueued URL: %s", url)


async def _dispatch_job(job: dict) -> None:
    await emit_ui_event(
        "worker_status_changed",
        worker="queue_worker",
        state="processing",
        job_id=job.get("id"),
        job_type=job.get("type"),
    )
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
    elif job["type"] == "reactor_evaluate":
        await _process_reactor_job(job)
    elif job["type"] == "entrepreneur_evaluate":
        await _process_entrepreneur_job(job)
    else:
        raise ValueError(f"Unknown job type: {job['type']}")
    await emit_ui_event(
        "worker_status_changed",
        worker="queue_worker",
        state="idle",
        job_id=job.get("id"),
        job_type=job.get("type"),
    )


async def _process_reactor_job(job: dict) -> None:
    """Dispatch Reactor evaluation from queue."""
    if innovation_scheduler is None:
        logger.warning("Reactor scheduler not available, skipping job %s", job.get("id"))
        return
    context = job.get("payload", {}).get("context", {})
    proposals = await innovation_scheduler.evaluate_context(context, persist=True, output=True)
    logger.info(
        "Reactor evaluation completed for job %s: %d proposals",
        job.get("id"),
        len(proposals),
    )
    if (
        proposals
        and entrepreneur_scheduler is not None
        and getattr(entrepreneur_scheduler, "enabled", False) is True
        and SETTINGS.minds.entrepreneur_enabled
    ):
        await db.enqueue(
            "entrepreneur_evaluate",
            {
                "pipeline_id": context.get("pipeline_id"),
                "proposal_ids": [proposal.proposal_id for proposal in proposals],
            },
        )


async def _process_entrepreneur_job(job: dict) -> None:
    """Dispatch Entrepreneur evaluation from queue."""
    if entrepreneur_scheduler is None:
        logger.warning("Entrepreneur scheduler not available, skipping job %s", job.get("id"))
        return
    if not SETTINGS.minds.entrepreneur_enabled or getattr(entrepreneur_scheduler, "enabled", False) is not True:
        logger.info("Entrepreneur mind disabled, skipping job %s", job.get("id"))
        await emit_ui_event(
            "proposal_review_skipped",
            job_id=job.get("id"),
            pipeline_id=job.get("payload", {}).get("pipeline_id"),
            reason="entrepreneur_disabled",
        )
        return
    await emit_ui_event(
        "proposal_review_started",
        job_id=job.get("id"),
        pipeline_id=job.get("payload", {}).get("pipeline_id"),
        provider=getattr(entrepreneur_scheduler.llm_client, "_provider_name", lambda: "unknown")(),
        model=getattr(entrepreneur_scheduler.llm_client, "model", ""),
    )
    await entrepreneur_scheduler._run_session_wrapper()
    await emit_ui_event(
        "proposal_review_completed",
        job_id=job.get("id"),
        pipeline_id=job.get("payload", {}).get("pipeline_id"),
    )
    logger.info("Entrepreneur evaluation completed for job %s", job.get("id"))


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


async def _process_ui_upload(
    upload_id: str,
    source_id: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> None:
    await emit_ui_event(
        "source_ingest_started",
        upload_id=upload_id,
        source_id=source_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
    )
    try:
        async with ui_upload_semaphore:
            await source_store.update_status(source_id, "extracting")
            router = ProcessingRouter(browser_manager=browser_manager_instance)
            extracted = await router.process(data, filename=filename, http_content_type=content_type)
            await source_store.update_status(
                source_id,
                "extracted",
                {
                    "source_type": extracted.source_type,
                    "extracted_chars": len(extracted.text or ""),
                },
            )
            await emit_ui_event(
                "chaos_note_created",
                upload_id=upload_id,
                source_id=source_id,
                filename=filename,
                source_type=extracted.source_type,
                title=extracted.title or Path(filename).stem,
                text_length=len(extracted.text or ""),
            )

            title = extracted.title or Path(filename).stem
            content = extracted.text or ""
            if title:
                content = f"# {title}\n\n{content}".strip()

            drop = RainDrop(
                id="",
                rain_type=RainType.DOCUMENT,
                content=content,
                raw_bytes=b"",
                source="web_upload",
                source_id=source_id,
                stream_type=StreamType.EXTRACT_ANALYZE,
                metadata={
                    "ui_upload_id": upload_id,
                    "source_id": source_id,
                    "filename": filename,
                    "content_type": content_type,
                    "source_type": extracted.source_type,
                    **(extracted.metadata or {}),
                },
            )
            await source_store.update_status(source_id, "processing")
            result = await _process_dikiwi_ingestion(drop)
            await source_store.update_status(
                source_id,
                "completed",
                {
                    "pipeline_id": result.pipeline_id,
                    "final_stage": result.final_stage_reached.name if result.final_stage_reached else "",
                },
            )
            await emit_ui_event(
                "source_ingest_completed",
                upload_id=upload_id,
                source_id=source_id,
                filename=filename,
                pipeline_id=result.pipeline_id,
                final_stage=result.final_stage_reached.name if result.final_stage_reached else "",
                stage_count=len(result.stage_results),
            )
            if upload_id.startswith("retry-"):
                await emit_ui_event(
                    "source_retry_completed",
                    upload_id=upload_id,
                    source_id=source_id,
                    filename=filename,
                    pipeline_id=result.pipeline_id,
                    final_stage=result.final_stage_reached.name if result.final_stage_reached else "",
                )
    except asyncio.CancelledError:
        await emit_ui_event(
            "upload_cancelled",
            upload_id=upload_id,
            source_id=source_id,
            filename=filename,
        )
        await source_store.update_status(source_id, "cancelled")
        raise
    except Exception as exc:
        logger.exception("UI upload processing failed for %s", filename)
        await emit_ui_event(
            "pipeline_failed",
            upload_id=upload_id,
            source_id=source_id,
            error=str(exc),
        )
        if upload_id.startswith("retry-"):
            await emit_ui_event(
                "source_retry_failed",
                upload_id=upload_id,
                source_id=source_id,
                filename=filename,
                error=str(exc),
            )
        await source_store.update_status(source_id, "failed", {"error": str(exc)})
    finally:
        ui_upload_tasks.pop(upload_id, None)


async def _process_upload_source_job(job: dict[str, Any]) -> str:
    payload = dict(job.get("payload") or {})
    source_id = str(job.get("source_id") or payload.get("source_id") or "")
    upload_id = str(payload.get("upload_id") or f"source-job-{job.get('job_id', '')}")
    batch_id = str(payload.get("batch_id") or "")
    source = await source_store.get_source(source_id)
    if source is None:
        return "failed:source_not_found"
    filename = str(source.get("filename") or payload.get("filename") or source_id)
    content_type = str(source.get("content_type") or payload.get("content_type") or "application/octet-stream")

    await emit_ui_event(
        "source_job_started",
        job_id=job.get("job_id"),
        source_id=source_id,
        upload_id=upload_id,
        batch_id=batch_id or None,
        filename=filename,
        job_type=job.get("job_type"),
        attempt_count=job.get("attempt_count", 0),
    )
    await source_store.update_status(
        source_id,
        "extracting",
        {"job_id": job.get("job_id"), "batch_id": batch_id, "upload_id": upload_id},
    )
    data = await source_store.read_stored_object(source_id)
    router = ProcessingRouter(browser_manager=browser_manager_instance)
    extracted = await router.process(data, filename=filename, http_content_type=content_type)
    await source_store.update_status(
        source_id,
        "extracted",
        {
            "source_type": extracted.source_type,
            "extracted_chars": len(extracted.text or ""),
            "batch_id": batch_id,
            "job_id": job.get("job_id"),
        },
    )
    await emit_ui_event(
        "chaos_note_created",
        batch_id=batch_id or None,
        upload_id=upload_id,
        source_id=source_id,
        filename=filename,
        source_type=extracted.source_type,
        title=extracted.title or Path(filename).stem,
        text_length=len(extracted.text or ""),
    )
    markdown_package = await _canonical_markdown_converter().convert_extracted(
        source_id=source_id,
        extracted=extracted,
        fallback_title=filename,
        metadata={
            "job_id": job.get("job_id"),
            "upload_id": upload_id,
            "batch_id": batch_id,
            "filename": filename,
            "content_type": content_type,
        },
    )
    await emit_ui_event(
        "canonical_markdown_created",
        job_id=job.get("job_id"),
        batch_id=batch_id or None,
        upload_id=upload_id,
        source_id=source_id,
        package_id=markdown_package.package_id,
        markdown_sha256=markdown_package.markdown_sha256,
        package_path=markdown_package.package_path,
        title=markdown_package.title,
        text_length=len(markdown_package.markdown),
    )

    drop = RainDrop(
        id="",
        rain_type=RainType.DOCUMENT,
        content=markdown_package.markdown,
        raw_bytes=markdown_package.markdown.encode("utf-8"),
        source="web_upload_source_job",
        source_id=source_id,
        stream_type=StreamType.EXTRACT_ANALYZE,
        metadata={
            "ui_upload_id": upload_id,
            "batch_id": batch_id,
            "source_id": source_id,
            "filename": filename,
            "content_type": content_type,
            "source_type": extracted.source_type,
            "processing_method": "durable_source_job",
            "canonical_markdown_package_id": markdown_package.package_id,
            "canonical_markdown_path": markdown_package.package_path,
            "canonical_markdown_sha256": markdown_package.markdown_sha256,
            **(extracted.metadata or {}),
        },
    )
    await source_store.update_status(source_id, "processing", {"job_id": job.get("job_id"), "batch_id": batch_id})
    result = await _process_dikiwi_ingestion(drop)
    failed_stage = _failed_stage(result)
    if failed_stage is not None:
        error = failed_stage.error_message or f"{failed_stage.stage.name} failed"
        stage_name = getattr(getattr(failed_stage, "stage", None), "name", "")
        provider, model = _stage_provider_model(result, failed_stage)
        attempt_count = int(job.get("attempt_count") or 0)
        if _is_retryable_processing_error(error) and attempt_count < SETTINGS.source_max_retry_attempts:
            delay = _retry_delay_for_attempt(attempt_count)
            await source_store.mark_retry_pending(
                source_id,
                error=error,
                stage=stage_name,
                provider=provider,
                model=model,
                pipeline_id=result.pipeline_id,
                retry_delay_seconds=delay,
            )
            await emit_ui_event(
                "source_retry_scheduled",
                job_id=job.get("job_id"),
                source_id=source_id,
                upload_id=upload_id,
                batch_id=batch_id or None,
                pipeline_id=result.pipeline_id,
                stage=stage_name,
                error=error,
                retry_delay_seconds=delay,
                attempt_count=attempt_count,
            )
            return "retry"
        await source_store.update_status(
            source_id,
            "failed_retry_exhausted" if _is_retryable_processing_error(error) else "failed",
            {
                "job_id": job.get("job_id"),
                "batch_id": batch_id,
                "pipeline_id": result.pipeline_id,
                "error": error,
                "last_failed_stage": stage_name,
            },
        )
        await emit_ui_event(
            "pipeline_failed",
            job_id=job.get("job_id"),
            source_id=source_id,
            upload_id=upload_id,
            batch_id=batch_id or None,
            pipeline_id=result.pipeline_id,
            error=error,
        )
        return "failed"

    await source_store.update_status(
        source_id,
        "completed",
        {
            "job_id": job.get("job_id"),
            "batch_id": batch_id,
            "pipeline_id": result.pipeline_id,
            "final_stage": result.final_stage_reached.name if result.final_stage_reached else "",
        },
    )
    await emit_ui_event(
        "source_ingest_completed",
        job_id=job.get("job_id"),
        upload_id=upload_id,
        source_id=source_id,
        filename=filename,
        batch_id=batch_id or None,
        pipeline_id=result.pipeline_id,
        final_stage=result.final_stage_reached.name if result.final_stage_reached else "",
        stage_count=len(result.stage_results),
    )
    return "completed"


async def _process_url_source_job(job: dict[str, Any]) -> str:
    payload = dict(job.get("payload") or {})
    source_id = str(job.get("source_id") or payload.get("source_id") or "")
    upload_id = str(payload.get("upload_id") or f"source-job-{job.get('job_id', '')}")
    source = await source_store.get_source(source_id)
    if source is None:
        return "failed:source_not_found"
    url = str(source.get("normalized_source") or payload.get("url") or "")
    if not url:
        await source_store.update_status(source_id, "failed", {"error": "URL source has no normalized URL"})
        return "failed:missing_url"

    await emit_ui_event(
        "source_job_started",
        job_id=job.get("job_id"),
        source_id=source_id,
        upload_id=upload_id,
        url=url,
        job_type=job.get("job_type"),
        attempt_count=job.get("attempt_count", 0),
    )
    await source_store.update_status(source_id, "fetching", {"job_id": job.get("job_id"), "upload_id": upload_id})
    await emit_ui_event(
        "url_fetch_started",
        job_id=job.get("job_id"),
        source_id=source_id,
        upload_id=upload_id,
        url=url,
    )

    router = ProcessingRouter(browser_manager=browser_manager_instance)
    extracted = await router.process_url(url, browser_manager=browser_manager_instance)
    if not extracted.text or extracted.text.startswith("[Failed to fetch"):
        raise RuntimeError(extracted.text or "URL extraction returned no text")

    await source_store.update_status(
        source_id,
        "extracted",
        {
            "source_type": extracted.source_type,
            "extracted_chars": len(extracted.text or ""),
            "title": extracted.title or url,
            "job_id": job.get("job_id"),
            "upload_id": upload_id,
        },
    )
    await emit_ui_event(
        "chaos_note_created",
        job_id=job.get("job_id"),
        source_id=source_id,
        upload_id=upload_id,
        source_type=extracted.source_type,
        url=url,
        title=extracted.title or url,
        text_length=len(extracted.text or ""),
    )
    markdown_package = await _canonical_markdown_converter().convert_extracted(
        source_id=source_id,
        extracted=extracted,
        fallback_title=url,
        source_url=url,
        metadata={
            "job_id": job.get("job_id"),
            "upload_id": upload_id,
            "url": url,
        },
    )
    await emit_ui_event(
        "canonical_markdown_created",
        job_id=job.get("job_id"),
        source_id=source_id,
        upload_id=upload_id,
        package_id=markdown_package.package_id,
        markdown_sha256=markdown_package.markdown_sha256,
        package_path=markdown_package.package_path,
        title=markdown_package.title,
        text_length=len(markdown_package.markdown),
        url=url,
    )

    drop = RainDrop(
        id="",
        rain_type=RainType.URL,
        content=markdown_package.markdown,
        raw_bytes=markdown_package.markdown.encode("utf-8"),
        source="studio_url_source_job",
        source_id=source_id,
        stream_type=StreamType.FETCH_ANALYZE,
        metadata={
            "source_id": source_id,
            "upload_id": upload_id,
            "url": url,
            "source_type": extracted.source_type,
            "processing_method": "durable_studio_url_fetch_extract_dikiwi",
            "canonical_markdown_package_id": markdown_package.package_id,
            "canonical_markdown_path": markdown_package.package_path,
            "canonical_markdown_sha256": markdown_package.markdown_sha256,
            **(extracted.metadata or {}),
        },
    )
    await source_store.update_status(source_id, "processing", {"job_id": job.get("job_id"), "upload_id": upload_id})
    result = await _process_dikiwi_ingestion(drop)
    failed_stage = _failed_stage(result)
    if failed_stage is not None:
        error = failed_stage.error_message or f"{failed_stage.stage.name} failed"
        stage_name = getattr(getattr(failed_stage, "stage", None), "name", "")
        provider, model = _stage_provider_model(result, failed_stage)
        attempt_count = int(job.get("attempt_count") or 0)
        if _is_retryable_processing_error(error) and attempt_count < SETTINGS.source_max_retry_attempts:
            delay = _retry_delay_for_attempt(attempt_count)
            await source_store.mark_retry_pending(
                source_id,
                error=error,
                stage=stage_name,
                provider=provider,
                model=model,
                pipeline_id=result.pipeline_id,
                retry_delay_seconds=delay,
            )
            await emit_ui_event(
                "source_retry_scheduled",
                job_id=job.get("job_id"),
                source_id=source_id,
                upload_id=upload_id,
                url=url,
                pipeline_id=result.pipeline_id,
                stage=stage_name,
                error=error,
                retry_delay_seconds=delay,
                attempt_count=attempt_count,
            )
            return "retry"
        await source_store.update_status(
            source_id,
            "failed_retry_exhausted" if _is_retryable_processing_error(error) else "failed",
            {
                "job_id": job.get("job_id"),
                "upload_id": upload_id,
                "pipeline_id": result.pipeline_id,
                "error": error,
                "last_failed_stage": stage_name,
            },
        )
        await emit_ui_event(
            "pipeline_failed",
            job_id=job.get("job_id"),
            source_id=source_id,
            upload_id=upload_id,
            url=url,
            pipeline_id=result.pipeline_id,
            error=error,
        )
        return "failed"

    await source_store.update_status(
        source_id,
        "completed",
        {
            "job_id": job.get("job_id"),
            "upload_id": upload_id,
            "pipeline_id": result.pipeline_id,
            "final_stage": result.final_stage_reached.name if result.final_stage_reached else "",
        },
    )
    await emit_ui_event(
        "source_ingest_completed",
        job_id=job.get("job_id"),
        upload_id=upload_id,
        source_id=source_id,
        url=url,
        pipeline_id=result.pipeline_id,
        final_stage=result.final_stage_reached.name if result.final_stage_reached else "",
        stage_count=len(result.stage_results),
    )
    return "completed"


async def _source_worker_loop(worker_id: str) -> None:
    logger.info("Source worker %s started", worker_id)
    stale_lock_seconds = max(60.0, float(SETTINGS.source_job_stale_lock_seconds))
    while source_worker_stop is None or not source_worker_stop.is_set():
        try:
            recovered = await source_store.requeue_stale_running_source_jobs(
                stale_after_seconds=stale_lock_seconds
            )
            if recovered:
                await emit_ui_event(
                    "source_jobs_requeued_after_stale_lock",
                    worker_id=worker_id,
                    count=recovered,
                    stale_after_seconds=stale_lock_seconds,
                )
            job = await source_store.claim_next_source_job(worker_id=worker_id)
            if job is None:
                await asyncio.sleep(2)
                continue
            result = "failed"
            try:
                if _source_foundation_graph_enabled(job):
                    result = await _process_source_job_with_foundation_graph(job)
                elif job.get("job_type") == "process_upload_source":
                    result = await _process_upload_source_job(job)
                elif job.get("job_type") == "process_url_source":
                    result = await _process_url_source_job(job)
                else:
                    result = f"failed:unknown_job_type:{job.get('job_type')}"
                if result == "completed":
                    await source_store.complete_source_job(str(job["job_id"]))
                elif result == "retry":
                    delay = _retry_delay_for_attempt(int(job.get("attempt_count") or 1))
                    await source_store.retry_source_job(str(job["job_id"]), error="retryable processing failure", delay_seconds=delay)
                else:
                    await source_store.fail_source_job(str(job["job_id"]), error=result)
                    payload = dict(job.get("payload") or {})
                    upload_id = str(payload.get("upload_id") or "")
                    if upload_id.startswith("retry-"):
                        await emit_ui_event(
                            "source_retry_failed",
                            upload_id=upload_id,
                            source_id=str(job.get("source_id") or ""),
                            source_type="url" if job.get("job_type") == "process_url_source" else "upload",
                            error=result,
                        )
            except Exception as exc:
                logger.exception("Source job %s failed", job.get("job_id"))
                attempt_count = int(job.get("attempt_count") or 0)
                error = str(exc)
                payload = dict(job.get("payload") or {})
                upload_id = str(payload.get("upload_id") or "")
                if _is_retryable_processing_error(error) and attempt_count < SETTINGS.source_max_retry_attempts:
                    delay = _retry_delay_for_attempt(attempt_count)
                    await source_store.mark_retry_pending(
                        str(job.get("source_id")),
                        error=error,
                        retry_delay_seconds=delay,
                    )
                    await source_store.retry_source_job(str(job["job_id"]), error=error, delay_seconds=delay)
                else:
                    await source_store.update_status(str(job.get("source_id")), "failed", {"error": error})
                    await source_store.fail_source_job(str(job["job_id"]), error=error)
                    await emit_ui_event(
                        "pipeline_failed",
                        job_id=job.get("job_id"),
                        source_id=str(job.get("source_id") or ""),
                        upload_id=upload_id or None,
                        url=str(payload.get("url") or ""),
                        error=error,
                    )
                    if upload_id.startswith("retry-"):
                        await emit_ui_event(
                            "source_retry_failed",
                            upload_id=upload_id,
                            source_id=str(job.get("source_id") or ""),
                            source_type="url" if job.get("job_type") == "process_url_source" else "upload",
                            error=error,
                        )
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Source worker %s loop error", worker_id)
            await asyncio.sleep(5)
    logger.info("Source worker %s stopped", worker_id)


async def _retry_source(source: dict[str, Any]) -> dict[str, Any]:
    source_id = str(source.get("source_id") or "")
    previous_status = str(source.get("status") or "")
    kind = str(source.get("kind") or "")
    retry_id = f"retry-{source_id.split(':', 1)[-1][:12]}-{len(ui_upload_tasks) + 1}"
    await emit_ui_event(
        "source_retry_started",
        upload_id=retry_id,
        source_id=source_id,
        source_type=kind,
        previous_status=previous_status,
    )
    if kind == "url":
        url = str(source.get("normalized_source") or "")
        if not url:
            reason = "URL source has no normalized URL to retry."
            await source_store.update_status(source_id, "failed", {"retry_error": reason, "retry_upload_id": retry_id})
            await emit_ui_event(
                "source_retry_failed",
                upload_id=retry_id,
                source_id=source_id,
                source_type=kind,
                error=reason,
            )
            return {"source_id": source_id, "retry_id": retry_id, "started": False, "reason": reason}
        await source_store.update_status(source_id, "queued", {"retry_upload_id": retry_id})
        job = await source_store.enqueue_source_job(
            source_id=source_id,
            job_type="process_url_source",
            payload={"upload_id": retry_id, "url": url, "retry_of_status": previous_status},
            priority=50,
        )
        await emit_ui_event(
            "source_job_queued",
            upload_id=retry_id,
            source_id=source_id,
            job_id=job["job_id"],
            job_type=job["job_type"],
            url=url,
        )
        return {"source_id": source_id, "retry_id": retry_id, "started": True, "job_id": job["job_id"]}

    if kind != "upload":
        reason = "Only stored upload and URL sources can be retried through the current Studio processing path."
        await source_store.update_status(source_id, "failed", {"retry_error": reason, "retry_upload_id": retry_id})
        await emit_ui_event(
            "source_retry_failed",
            upload_id=retry_id,
            source_id=source_id,
            source_type=kind,
            error=reason,
        )
        return {"source_id": source_id, "retry_id": retry_id, "started": False, "reason": reason}

    try:
        await source_store.read_stored_object(source_id)
    except Exception as exc:
        await source_store.update_status(source_id, "failed", {"retry_error": str(exc), "retry_upload_id": retry_id})
        await emit_ui_event(
            "source_retry_failed",
            upload_id=retry_id,
            source_id=source_id,
            source_type=kind,
            error=str(exc),
        )
        return {"source_id": source_id, "retry_id": retry_id, "started": False, "reason": str(exc)}

    filename = str(source.get("filename") or f"retry-{retry_id}")
    content_type = str(source.get("content_type") or "application/octet-stream")
    await source_store.update_status(source_id, "queued", {"retry_upload_id": retry_id})
    job = await source_store.enqueue_source_job(
        source_id=source_id,
        job_type="process_upload_source",
        payload={
            "upload_id": retry_id,
            "filename": filename,
            "content_type": content_type,
            "retry_of_status": previous_status,
        },
        priority=50,
    )
    await emit_ui_event(
        "source_job_queued",
        upload_id=retry_id,
        source_id=source_id,
        job_id=job["job_id"],
        job_type=job["job_type"],
        filename=filename,
    )
    return {"source_id": source_id, "retry_id": retry_id, "started": True}


async def _process_ui_url(source_id: str, url: str, *, retry_id: str | None = None) -> None:
    await emit_ui_event("url_fetch_started", source_id=source_id, url=url)
    try:
        await source_store.update_status(source_id, "fetching")
        router = ProcessingRouter(browser_manager=browser_manager_instance)
        extracted = await router.process_url(url, browser_manager=browser_manager_instance)
        if not extracted.text or extracted.text.startswith("[Failed to fetch"):
            raise RuntimeError(extracted.text or "URL extraction returned no text")

        await source_store.update_status(
            source_id,
            "extracted",
            {
                "source_type": extracted.source_type,
                "extracted_chars": len(extracted.text or ""),
                "title": extracted.title or url,
            },
        )
        await emit_ui_event(
            "chaos_note_created",
            source_id=source_id,
            source_type=extracted.source_type,
            url=url,
            title=extracted.title or url,
            text_length=len(extracted.text or ""),
        )

        title = extracted.title or url
        content = extracted.text or ""
        if title:
            content = f"# {title}\n\n{content}".strip()

        drop = RainDrop(
            id="",
            rain_type=RainType.URL,
            content=content,
            raw_bytes=(extracted.text or "").encode("utf-8"),
            source="studio_url",
            source_id=source_id,
            stream_type=StreamType.FETCH_ANALYZE,
            metadata={
                "source_id": source_id,
                "url": url,
                "source_type": extracted.source_type,
                "processing_method": "studio_url_fetch_extract_dikiwi",
                **(extracted.metadata or {}),
            },
        )
        await source_store.update_status(source_id, "processing")
        result = await _process_dikiwi_ingestion(drop)
        await source_store.update_status(
            source_id,
            "completed",
            {
                "pipeline_id": result.pipeline_id,
                "final_stage": result.final_stage_reached.name if result.final_stage_reached else "",
            },
        )
        await emit_ui_event(
            "source_ingest_completed",
            upload_id=retry_id,
            source_id=source_id,
            url=url,
            pipeline_id=result.pipeline_id,
            final_stage=result.final_stage_reached.name if result.final_stage_reached else "",
            stage_count=len(result.stage_results),
        )
        if retry_id:
            await emit_ui_event(
                "source_retry_completed",
                upload_id=retry_id,
                source_id=source_id,
                source_type="url",
                url=url,
                pipeline_id=result.pipeline_id,
                final_stage=result.final_stage_reached.name if result.final_stage_reached else "",
            )
    except asyncio.CancelledError:
        await emit_ui_event("url_processing_cancelled", source_id=source_id, url=url)
        await source_store.update_status(source_id, "cancelled")
        raise
    except Exception as exc:
        logger.exception("UI URL processing failed for %s", url)
        await emit_ui_event("pipeline_failed", source_id=source_id, url=url, error=str(exc))
        if retry_id:
            await emit_ui_event(
                "source_retry_failed",
                upload_id=retry_id,
                source_id=source_id,
                source_type="url",
                url=url,
                error=str(exc),
            )
        await source_store.update_status(source_id, "failed", {"error": str(exc)})
    finally:
        ui_upload_tasks.pop(retry_id or f"url-{source_id}", None)


async def _read_upload_bytes(file: UploadFile, max_bytes: int) -> bytes:
    chunk_size = 1024 * 1024
    total = 0
    buffer = bytearray()

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds max upload size of {max_bytes} bytes",
            )
        buffer.extend(chunk)

    await file.seek(0)
    return bytes(buffer)


async def _handle_ui_upload(file: UploadFile, upload_id: str) -> dict[str, Any]:
    await _ensure_source_queue_capacity(1)
    data = await _read_upload_bytes(file, SETTINGS.max_file_size)
    filename = file.filename or f"upload-{upload_id}"
    content_type = file.content_type or "application/octet-stream"
    source_record = await source_store.store_upload(
        upload_id=upload_id,
        filename=filename,
        content_type=content_type,
        data=data,
        metadata={"intake": "studio_upload"},
    )
    await emit_ui_event(
        "source_stored",
        upload_id=upload_id,
        source_id=source_record["source_id"],
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        duplicate=source_record["duplicate"],
        sha256=source_record["sha256"],
    )
    should_enqueue = _should_enqueue_upload_source(source_record)
    if should_enqueue:
        await source_store.update_status(
            source_record["source_id"],
            "queued",
            {"upload_id": upload_id, "intake": "studio_upload"},
        )
        try:
            job = await source_store.enqueue_source_job(
                source_id=source_record["source_id"],
                job_type="process_upload_source",
                payload={
                    "upload_id": upload_id,
                    "filename": filename,
                    "content_type": content_type,
                },
                max_pending=SETTINGS.source_job_max_pending,
            )
        except SourceJobCapacityError as exc:
            await source_store.update_status(source_record["source_id"], "deferred", {"queue_error": str(exc)})
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        await emit_ui_event(
            "source_job_queued",
            upload_id=upload_id,
            source_id=source_record["source_id"],
            job_id=job["job_id"],
            job_type=job["job_type"],
            filename=filename,
        )
    return {
        "upload_id": upload_id,
        "source_id": source_record["source_id"],
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(data),
        "sha256": source_record["sha256"],
        "duplicate": source_record["duplicate"],
        "status": "queued" if should_enqueue else "duplicate",
    }


async def _handle_ui_upload_batch(files: list[tuple[UploadFile, str]], batch_id: str) -> dict[str, Any]:
    if not dikiwi_mind:
        raise HTTPException(status_code=503, detail="DIKIWI Mind is not initialized")
    await _ensure_source_queue_capacity(len(files))

    accepted: list[dict[str, Any]] = []
    stored_items: list[dict[str, Any]] = []
    for file, upload_id in files:
        data = await _read_upload_bytes(file, SETTINGS.max_file_size)
        filename = file.filename or f"upload-{upload_id}"
        content_type = file.content_type or "application/octet-stream"
        await emit_ui_event(
            "source_uploaded",
            batch_id=batch_id,
            upload_id=upload_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
        )
        source_record = await source_store.store_upload(
            upload_id=upload_id,
            filename=filename,
            content_type=content_type,
            data=data,
            metadata={"intake": "studio_upload", "batch_id": batch_id},
        )
        await emit_ui_event(
            "source_stored",
            batch_id=batch_id,
            upload_id=upload_id,
            source_id=source_record["source_id"],
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            duplicate=source_record["duplicate"],
            sha256=source_record["sha256"],
        )
        should_enqueue = _should_enqueue_upload_source(source_record)
        item = {
            "upload_id": upload_id,
            "source_id": source_record["source_id"],
            "filename": filename,
            "content_type": content_type,
            "size_bytes": len(data),
            "sha256": source_record["sha256"],
            "duplicate": source_record["duplicate"],
            "status": "queued" if should_enqueue else "duplicate",
        }
        if should_enqueue:
            await source_store.update_status(
                source_record["source_id"],
                "queued",
                {"upload_id": upload_id, "batch_id": batch_id, "intake": "studio_upload"},
            )
            try:
                job = await source_store.enqueue_source_job(
                    source_id=source_record["source_id"],
                    job_type="process_upload_source",
                    payload={
                        "upload_id": upload_id,
                        "batch_id": batch_id,
                        "filename": filename,
                        "content_type": content_type,
                    },
                    max_pending=SETTINGS.source_job_max_pending,
                )
            except SourceJobCapacityError as exc:
                await source_store.update_status(source_record["source_id"], "deferred", {"queue_error": str(exc)})
                raise HTTPException(status_code=429, detail=str(exc)) from exc
            await emit_ui_event(
                "source_job_queued",
                batch_id=batch_id,
                upload_id=upload_id,
                source_id=source_record["source_id"],
                job_id=job["job_id"],
                job_type=job["job_type"],
                filename=filename,
            )
        stored_items.append(item)
        accepted.append(dict(item))

    await emit_ui_event(
        "upload_batch_queued",
        batch_id=batch_id,
        queued=sum(1 for item in accepted if item["status"] == "queued"),
        duplicates=sum(1 for item in stored_items if item["duplicate"]),
    )
    return {"batch_id": batch_id, "uploads": accepted, "status": "queued"}


def _batch_reached_impact(batch: Any) -> bool:
    """Return true when a DIKIWI batch produced graph-level impact output."""
    if getattr(batch, "higher_order_triggered", False):
        return True
    for result in getattr(batch, "results", []) or []:
        stage = getattr(result, "final_stage_reached", None)
        if getattr(stage, "name", "") == "IMPACT":
            return True
    return False


async def _run_studio_business_flow(batch_id: str, batch: Any) -> dict[str, Any]:
    """Run Reactor and Entrepreneur from the same Studio batch path users exercise."""
    pipeline_ids = [result.pipeline_id for result in getattr(batch, "results", []) or []]
    if not _batch_reached_impact(batch):
        await emit_ui_event(
            "business_flow_skipped",
            batch_id=batch_id,
            pipeline_ids=pipeline_ids,
            reason="batch_did_not_reach_impact",
        )
        return {"ran": False, "reason": "batch_did_not_reach_impact", "proposal_count": 0}
    if innovation_scheduler is None:
        await emit_ui_event(
            "business_flow_skipped",
            batch_id=batch_id,
            pipeline_ids=pipeline_ids,
            reason="reactor_scheduler_unavailable",
        )
        return {"ran": False, "reason": "reactor_scheduler_unavailable", "proposal_count": 0}

    context = await innovation_scheduler._gather_context()
    context["studio_batch"] = {
        "batch_id": batch_id,
        "pipeline_ids": pipeline_ids,
        "incremental_ratio": getattr(batch, "incremental_ratio", 0.0),
        "incremental_threshold": getattr(batch, "incremental_threshold", 0.0),
        "higher_order_triggered": getattr(batch, "higher_order_triggered", False),
    }

    provider = getattr(innovation_scheduler.llm_client, "_provider_name", lambda: "unknown")()
    await emit_ui_event(
        "proposal_generation_started",
        batch_id=batch_id,
        pipeline_ids=pipeline_ids,
        provider=provider,
        model=getattr(innovation_scheduler.llm_client, "model", ""),
    )
    proposals = await innovation_scheduler.evaluate_context(context, persist=True, output=True)
    await emit_ui_event(
        "proposal_generation_completed",
        batch_id=batch_id,
        pipeline_ids=pipeline_ids,
        proposal_count=len(proposals),
    )

    if proposals and entrepreneur_scheduler is not None:
        await emit_ui_event(
            "proposal_review_started",
            batch_id=batch_id,
            pipeline_ids=pipeline_ids,
            provider=getattr(entrepreneur_scheduler.llm_client, "_provider_name", lambda: "unknown")(),
            model=getattr(entrepreneur_scheduler.llm_client, "model", ""),
        )
        await entrepreneur_scheduler._run_session_wrapper()
        await emit_ui_event(
            "proposal_review_completed",
            batch_id=batch_id,
            pipeline_ids=pipeline_ids,
            proposal_count=len(proposals),
        )

    return {"ran": True, "reason": "", "proposal_count": len(proposals)}


async def _process_ui_upload_batch(batch_id: str, items: list[dict[str, Any]]) -> None:
    process_items = [item for item in items if not item["duplicate"]]
    try:
        if not process_items:
            await emit_ui_event("upload_batch_completed", batch_id=batch_id, processed=0, duplicates=len(items))
            return

        router = ProcessingRouter(browser_manager=browser_manager_instance)
        drops: list[RainDrop] = []
        item_by_source: dict[str, dict[str, Any]] = {}

        await emit_ui_event(
            "batch_chaos_started",
            batch_id=batch_id,
            source_count=len(process_items),
        )
        for item in process_items:
            await source_store.update_status(item["source_id"], "extracting")
            data = await source_store.read_stored_object(item["source_id"])
            extracted = await router.process(
                data,
                filename=item["filename"],
                http_content_type=item["content_type"],
            )
            await source_store.update_status(
                item["source_id"],
                "extracted",
                {
                    "source_type": extracted.source_type,
                    "extracted_chars": len(extracted.text or ""),
                    "batch_id": batch_id,
                },
            )
            await emit_ui_event(
                "chaos_note_created",
                batch_id=batch_id,
                upload_id=item["upload_id"],
                source_id=item["source_id"],
                filename=item["filename"],
                source_type=extracted.source_type,
                title=extracted.title or Path(item["filename"]).stem,
                text_length=len(extracted.text or ""),
            )
            markdown_package = await _canonical_markdown_converter().convert_extracted(
                source_id=item["source_id"],
                extracted=extracted,
                fallback_title=item["filename"],
                metadata={
                    "batch_id": batch_id,
                    "upload_id": item["upload_id"],
                    "filename": item["filename"],
                    "content_type": item["content_type"],
                },
            )
            await emit_ui_event(
                "canonical_markdown_created",
                batch_id=batch_id,
                upload_id=item["upload_id"],
                source_id=item["source_id"],
                package_id=markdown_package.package_id,
                markdown_sha256=markdown_package.markdown_sha256,
                package_path=markdown_package.package_path,
                title=markdown_package.title,
                text_length=len(markdown_package.markdown),
            )

            drop = RainDrop(
                id="",
                rain_type=RainType.DOCUMENT,
                content=markdown_package.markdown,
                raw_bytes=markdown_package.markdown.encode("utf-8"),
                source="web_upload_batch",
                source_id=item["source_id"],
                stream_type=StreamType.EXTRACT_ANALYZE,
                metadata={
                    "ui_upload_id": item["upload_id"],
                    "batch_id": batch_id,
                    "source_id": item["source_id"],
                    "filename": item["filename"],
                    "content_type": item["content_type"],
                    "source_type": extracted.source_type,
                    "canonical_markdown_package_id": markdown_package.package_id,
                    "canonical_markdown_path": markdown_package.package_path,
                    "canonical_markdown_sha256": markdown_package.markdown_sha256,
                    **(extracted.metadata or {}),
                },
            )
            drops.append(drop)
            item_by_source[item["source_id"]] = item

        await emit_ui_event(
            "batch_chaos_completed",
            batch_id=batch_id,
            source_count=len(drops),
        )
        for item in process_items:
            await source_store.update_status(item["source_id"], "processing", {"batch_id": batch_id})

        batch = await _process_dikiwi_batch_ingestion(drops)
        for drop, result in zip(drops, batch.results):
            item = item_by_source.get(drop.source_id)
            if item is None:
                continue
            final_stage = result.final_stage_reached.name if result.final_stage_reached else ""
            failed_stage = next((stage for stage in result.stage_results if not stage.success), None)
            if failed_stage is None:
                await source_store.update_status(
                    item["source_id"],
                    "completed",
                    {
                        "batch_id": batch_id,
                        "pipeline_id": result.pipeline_id,
                        "final_stage": final_stage,
                    },
                )
            else:
                await source_store.update_status(
                    item["source_id"],
                    "failed",
                    {
                        "batch_id": batch_id,
                        "pipeline_id": result.pipeline_id,
                        "error": failed_stage.error_message or f"{failed_stage.stage.name} failed",
                    },
                )

        business_result = await _run_studio_business_flow(batch_id, batch)
        await emit_ui_event(
            "upload_batch_completed",
            batch_id=batch_id,
            processed=len(process_items),
            duplicates=len(items) - len(process_items),
            incremental_ratio=batch.incremental_ratio,
            incremental_threshold=batch.incremental_threshold,
            higher_order_triggered=batch.higher_order_triggered,
            pipeline_ids=[result.pipeline_id for result in batch.results],
            business_flow=business_result,
        )
    except asyncio.CancelledError:
        await emit_ui_event("upload_batch_cancelled", batch_id=batch_id, source_count=len(process_items))
        for item in process_items:
            await source_store.update_status(item["source_id"], "cancelled", {"batch_id": batch_id})
        raise
    except Exception as exc:
        logger.exception("UI upload batch processing failed for %s", batch_id)
        await emit_ui_event("pipeline_failed", batch_id=batch_id, error=str(exc))
        for item in process_items:
            await source_store.update_status(item["source_id"], "failed", {"batch_id": batch_id, "error": str(exc)})
    finally:
        ui_upload_tasks.pop(batch_id, None)


async def _handle_ui_url(url: str) -> dict[str, Any]:
    await _ensure_source_queue_capacity(1)
    source = await source_store.store_url(url=url, metadata={"intake": "studio_url"})
    should_enqueue = (not source["duplicate"]) or str(source.get("status") or "") in {
        "stored",
        "deferred",
        "failed",
        "failed_retry_exhausted",
        "cancelled",
        "retry_pending",
    }
    job: dict[str, Any] | None = None
    if should_enqueue:
        await source_store.update_status(source["source_id"], "queued", {"intake": "studio_url", "url": url})
        try:
            job = await source_store.enqueue_source_job(
                source_id=source["source_id"],
                job_type="process_url_source",
                payload={"upload_id": f"url-{source['source_id']}", "url": url},
                max_pending=SETTINGS.source_job_max_pending,
            )
        except SourceJobCapacityError as exc:
            await source_store.update_status(source["source_id"], "deferred", {"queue_error": str(exc)})
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        await emit_ui_event(
            "source_job_queued",
            upload_id=f"url-{source['source_id']}",
            source_id=source["source_id"],
            job_id=job["job_id"],
            job_type=job["job_type"],
            url=url,
        )
    return {
        **source,
        "status": "queued" if should_enqueue else "duplicate",
        "processing": should_enqueue,
        "job_id": job["job_id"] if job else None,
    }


async def _handle_ui_text(title: str, text: str) -> dict[str, Any]:
    await _ensure_source_queue_capacity(1)
    source = await source_store.store_text(text=text, title=title, metadata={"intake": "studio_text"})
    text_id = f"text-{source['source_id']}"
    should_enqueue = (not source["duplicate"]) or str(source.get("status") or "") in {
        "stored",
        "deferred",
        "failed",
        "failed_retry_exhausted",
        "cancelled",
        "retry_pending",
    }
    job: dict[str, Any] | None = None
    if should_enqueue:
        await source_store.update_status(
            source["source_id"],
            "queued",
            {"intake": "studio_text", "title": source["title"], "upload_id": text_id},
        )
        try:
            job = await source_store.enqueue_source_job(
                source_id=source["source_id"],
                job_type="process_upload_source",
                payload={
                    "upload_id": text_id,
                    "filename": source["filename"],
                    "content_type": source["content_type"],
                    "source_kind": "text",
                },
                max_pending=SETTINGS.source_job_max_pending,
            )
        except SourceJobCapacityError as exc:
            await source_store.update_status(source["source_id"], "deferred", {"queue_error": str(exc)})
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        await emit_ui_event(
            "source_job_queued",
            upload_id=text_id,
            source_id=source["source_id"],
            job_id=job["job_id"],
            job_type=job["job_type"],
            source_type="text",
            title=source["title"],
        )
    return {
        **source,
        "status": "queued" if should_enqueue else "duplicate",
        "processing": should_enqueue,
        "job_id": job["job_id"] if job else None,
    }


async def _ui_status_provider() -> dict[str, Any]:
    queue_counts = await db.get_job_counts()
    source_job_counts = await source_store.get_source_job_counts()
    provider_pressure = await provider_backpressure.snapshot()
    graph_counts = {}
    for node_type in [
        "data",
        "information",
        "knowledge",
        "insight",
        "wisdom",
        "impact",
        "proposal",
        "business",
    ]:
        try:
            graph_counts[node_type] = await graph_db.count_nodes_by_type(node_type)
        except Exception:
            graph_counts[node_type] = 0

    worker_running = bool(worker and worker._task and not worker._task.done())
    source_workers_running = sum(1 for task in source_worker_tasks if not task.done())
    inbox_snapshot = inbox_watcher.snapshot() if inbox_watcher else {
        "running": False,
        "inbox_path": str(SETTINGS.inbox_path),
    }
    workflow_counts = {
        "active": sum(1 for task in workflow_tasks.values() if not task.done()),
    }
    return {
        "queue": queue_counts,
        "source_jobs": source_job_counts,
        "provider_pressure": provider_pressure,
        "graph": graph_counts,
        "active_pipelines": [
            pipeline_id
            for pipeline_id in ui_event_hub.active_pipeline_ids()
            if source_job_counts.get("running", 0) > 0
        ],
        "active_uploads": sorted(ui_upload_tasks.keys()),
        "daemons": {
            "queue_worker": worker_running,
            "source_workers": source_workers_running,
            "inbox_watcher": bool(inbox_watcher and inbox_watcher.running),
            "workflow_runner": workflow_counts["active"],
            "passive_capture_scheduler": scheduler is not None,
            "daily_digest_scheduler": digest_scheduler is not None,
            "claude_capture_scheduler": claude_capture_scheduler is not None,
            "feishu_ws_client": ws_client is not None,
        },
        "minds": {
            "dikiwi": dikiwi_mind is not None,
            "reactor": innovation_scheduler is not None,
            "entrepreneur": entrepreneur_scheduler is not None,
        },
        "inbox": inbox_snapshot,
        "workflows": workflow_counts,
    }


async def _ui_graph_provider() -> dict[str, Any]:
    return await graph_db.get_graph_snapshot()


async def _ui_pipeline_provider(pipeline_id: str) -> dict[str, Any] | None:
    events = ui_event_hub.pipeline_trace(pipeline_id)
    if not events:
        return None
    last = events[-1]
    return {
        "pipeline_id": pipeline_id,
        "status": last.get("type"),
        "events": events,
    }


async def _ui_sources_provider(limit: int, offset: int) -> dict[str, Any]:
    return await source_store.list_sources(limit=limit, offset=offset)


async def _ui_source_detail_provider(source_id: str) -> dict[str, Any] | None:
    return await source_store.get_source(source_id)


async def _ui_source_jobs_provider(limit: int, offset: int, status: str | None = None) -> dict[str, Any]:
    return await source_store.list_source_jobs(limit=limit, offset=offset, status=status)


async def _ui_workflows_provider(limit: int, offset: int, status: str | None = None) -> dict[str, Any]:
    safe_status = status if status in {"queued", "running", "interrupted", "completed", "failed", "cancelled"} else None
    runs = await workflow_run_store.list_runs(limit=limit, offset=offset, status=safe_status)
    return {
        "total": len(runs),
        "workflows": [_workflow_snapshot_payload(run) for run in runs],
    }


async def _run_iwi_workflow(workflow_run_id: str, *, motive: str, node_ids: list[str]) -> None:
    await workflow_run_store.update_status(
        workflow_run_id,
        status="running",
        current_node="trigger_iwi",
        metadata={"node_ids": node_ids},
    )
    await emit_ui_event(
        "workflow_run_started",
        workflow_run_id=workflow_run_id,
        workflow_kind="triggered_iwi",
        motive=motive,
        node_ids=node_ids,
    )
    try:
        if dikiwi_mind is None or not hasattr(dikiwi_mind, "process_triggered_iwi"):
            raise RuntimeError("DIKIWI triggered I/W/I runner is unavailable")
        result = await dikiwi_mind.process_triggered_iwi(
            motive=motive,
            workflow_run_id=workflow_run_id,
            node_ids=node_ids,
        )
        failed_stage = _failed_stage(result)
        final_stage = result.final_stage_reached.name if result.final_stage_reached else ""
        if failed_stage is not None:
            error = failed_stage.error_message or f"{failed_stage.stage.name} failed"
            await workflow_run_store.update_status(
                workflow_run_id,
                status="failed",
                current_node=failed_stage.stage.name,
                metadata={
                    "pipeline_id": result.pipeline_id,
                    "final_stage": final_stage,
                    "stage_count": len(result.stage_results),
                },
                last_error=error,
            )
            await emit_ui_event(
                "workflow_run_failed",
                workflow_run_id=workflow_run_id,
                workflow_kind="triggered_iwi",
                pipeline_id=result.pipeline_id,
                final_stage=final_stage,
                error=error,
            )
            return
        await workflow_run_store.update_status(
            workflow_run_id,
            status="completed",
            current_node=final_stage or "completed",
            metadata={
                "pipeline_id": result.pipeline_id,
                "final_stage": final_stage,
                "stage_count": len(result.stage_results),
            },
        )
        await emit_ui_event(
            "workflow_run_completed",
            workflow_run_id=workflow_run_id,
            workflow_kind="triggered_iwi",
            pipeline_id=result.pipeline_id,
            final_stage=final_stage,
            stage_count=len(result.stage_results),
        )
    except Exception as exc:
        logger.exception("Triggered I/W/I workflow failed: %s", workflow_run_id)
        await workflow_run_store.update_status(
            workflow_run_id,
            status="failed",
            current_node="trigger_iwi",
            last_error=str(exc),
        )
        await emit_ui_event(
            "workflow_run_failed",
            workflow_run_id=workflow_run_id,
            workflow_kind="triggered_iwi",
            error=str(exc),
        )
    finally:
        workflow_tasks.pop(workflow_run_id, None)


async def _ui_iwi_workflow_trigger(payload: dict[str, Any]) -> dict[str, Any]:
    motive = str(payload.get("motive", "")).strip()
    node_ids = [str(item).strip() for item in payload.get("node_ids", []) if str(item).strip()]
    run = await workflow_run_store.create_run(
        workflow_kind="triggered_iwi",
        input_summary=motive[:500],
        metadata={
            "motive": motive,
            "node_ids": node_ids,
            "trigger": "ui_workflow",
        },
    )
    await emit_ui_event(
        "workflow_run_queued",
        workflow_run_id=run.workflow_run_id,
        workflow_kind=run.workflow_kind,
        motive=motive,
        node_ids=node_ids,
    )
    if payload.get("run_inline") is True:
        await _run_iwi_workflow(run.workflow_run_id, motive=motive, node_ids=node_ids)
    else:
        workflow_tasks[run.workflow_run_id] = asyncio.create_task(
            _run_iwi_workflow(run.workflow_run_id, motive=motive, node_ids=node_ids)
        )
    updated = await workflow_run_store.get_run(run.workflow_run_id)
    return _workflow_snapshot_payload(updated or run)


def _studio_vault_path() -> Path:
    return Path(SETTINGS.obsidian_vault_path or SETTINGS.dikiwi_vault_path).expanduser()


def _read_vault_notes(stage_dir: str, limit: int) -> dict[str, Any]:
    safe_limit = min(max(1, limit), 200)
    directory = _studio_vault_path() / stage_dir
    if not directory.exists():
        return {"stage": stage_dir, "total": 0, "items": []}
    files = sorted(directory.rglob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    items: list[dict[str, Any]] = []
    for path in files[:safe_limit]:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        title = path.stem
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip() or title
                break
        items.append(
            {
                "title": title,
                "note_path": str(path),
                "relative_path": str(path.relative_to(_studio_vault_path())),
                "size_bytes": path.stat().st_size,
                "updated_at": path.stat().st_mtime,
                "preview": content[:1200],
            }
        )
    return {"stage": stage_dir, "total": len(files), "items": items}


async def _ui_proposals_provider(limit: int) -> dict[str, Any]:
    payload = await asyncio.to_thread(_read_vault_notes, "07-Proposal", limit)
    try:
        graph_count = await graph_db.count_nodes_by_type("reactor_proposal")
    except Exception:
        graph_count = 0
    payload["graph_reactor_proposal_count"] = graph_count
    return payload


async def _ui_entrepreneurship_provider(limit: int) -> dict[str, Any]:
    payload = await asyncio.to_thread(_read_vault_notes, "08-Entrepreneurship", limit)
    try:
        business_count = await graph_db.count_nodes_by_type("business")
    except Exception:
        business_count = 0
    payload["graph_business_count"] = business_count
    return payload


async def _ui_vault_notes_provider(stage: str, limit: int) -> dict[str, Any]:
    return await asyncio.to_thread(_read_vault_notes, stage, limit)


async def _ui_control_handler(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action in {"cancel_upload", "cancel_batch"}:
        target_id = str(payload.get("upload_id") or payload.get("batch_id") or "").strip()
        if not target_id:
            raise HTTPException(status_code=400, detail="upload_id or batch_id is required")
        task = ui_upload_tasks.get(target_id)
        if task is None:
            return {"action": action, "target_id": target_id, "cancelled": False, "reason": "not_active"}
        task.cancel()
        await emit_ui_event("upload_cancel_requested", upload_id=target_id)
        return {"action": action, "target_id": target_id, "cancelled": True}

    if action == "cancel_all_uploads":
        target_ids = sorted(ui_upload_tasks)
        for task in list(ui_upload_tasks.values()):
            task.cancel()
        source_job_ids = await source_store.cancel_running_source_jobs()
        await emit_ui_event("uploads_cancel_requested", upload_ids=target_ids, count=len(target_ids))
        return {
            "action": action,
            "cancelled": len(target_ids),
            "upload_ids": target_ids,
            "source_job_ids": source_job_ids,
        }

    if action == "retry_failed_sources":
        failed = await source_store.list_failed_sources(limit=500)
        await emit_ui_event(
            "retry_failed_sources_requested",
            source_ids=[source["source_id"] for source in failed],
            count=len(failed),
        )
        retries = [await _retry_source(source) for source in failed]
        return {
            "action": action,
            "retry_requested": len(failed),
            "retry_started": sum(1 for retry in retries if retry.get("started")),
            "source_ids": [source["source_id"] for source in failed],
            "retries": retries,
        }

    if action == "create_backup":
        backup_path_raw = str(payload.get("backup_path") or "").strip()
        backup_path = Path(backup_path_raw).expanduser() if backup_path_raw else SETTINGS.aily_data_dir / "backups" / "aily-backup.zip"
        manifest = await asyncio.to_thread(
            create_backup,
            vault_path=_studio_vault_path(),
            graph_db_path=SETTINGS.graph_db_path,
            source_store_db_path=SETTINGS.source_store_db_path,
            source_object_dir=SETTINGS.source_object_dir,
            output_path=backup_path,
        )
        await audit_logger.log("backup_created", backup_path=str(backup_path), manifest=manifest.to_dict())
        return {"action": action, "backup_path": str(backup_path), "manifest": manifest.to_dict()}

    if action == "restore_backup_dry_run":
        backup_path = Path(str(payload.get("backup_path") or "")).expanduser()
        if not backup_path.exists():
            raise HTTPException(status_code=400, detail="backup_path does not exist")
        restore_dir = SETTINGS.aily_data_dir / "restore-dry-run"
        restored = await asyncio.to_thread(restore_backup, backup_path=backup_path, restore_dir=restore_dir)
        await audit_logger.log("backup_restore_dry_run", backup_path=str(backup_path), restore_dir=str(restore_dir))
        return {"action": action, **restored}

    raise HTTPException(status_code=400, detail=f"Unsupported control action: {action}")


async def _tool_executor(action: str, **kwargs) -> dict:
    """Execute lightweight tools for GStack Agent."""

    if action == "run_tests":
        return {
            "passed": False,
            "disabled": True,
            "error": "Legacy test runner removed for the Aily V1 test redesign",
        }

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


def _validate_runtime_security_config() -> None:
    errors = SETTINGS.validate_runtime_security()
    if errors:
        raise RuntimeError("; ".join(errors))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker, scheduler, digest_scheduler, learning_loop, claude_capture_scheduler, ws_client
    global dikiwi_mind, innovation_scheduler, entrepreneur_scheduler
    global browser_manager_instance
    global source_worker_stop, source_worker_tasks, inbox_watcher
    _validate_runtime_security_config()
    await db.initialize()
    await graph_db.initialize()
    await source_store.initialize()
    await workflow_run_store.initialize()
    ui_event_hub.configure_persistence(SETTINGS.ui_event_log_path)
    loaded_ui_events = await ui_event_hub.load_persisted(limit=SETTINGS.ui_event_trace_limit)
    if loaded_ui_events:
        logger.info("Loaded %d persisted UI events", loaded_ui_events)

    # Initialize browser manager for JS-rendered pages (Monica, etc.)
    browser_manager = None
    try:
        from aily.browser.manager import BrowserUseManager
        browser_manager = BrowserUseManager()
        await browser_manager.start()
    except Exception:
        logger.warning("Browser manager failed to start, continuing without JS rendering support")
    browser_manager_instance = browser_manager

    # Initialize Three-Mind System FIRST (needed for WebSocket routing)
    try:
        dikiwi_writer = None
        vault_path_for_dikiwi = SETTINGS.obsidian_vault_path or SETTINGS.dikiwi_vault_path
        if vault_path_for_dikiwi:
            dikiwi_writer = DikiwiObsidianWriter(
                vault_path=vault_path_for_dikiwi,
                folder_prefix="",
                zettelkasten_only=True,
            )

        # DIKIWI Mind - continuous knowledge processing
        dikiwi_mind = DikiwiMind(
            llm_client=llm_resolver("dikiwi"),
            llm_client_resolver=llm_resolver,
            graph_db=graph_db,
            enabled=SETTINGS.minds.dikiwi_enabled,
            obsidian_writer=writer,
            dikiwi_obsidian_writer=dikiwi_writer,
            queue_db=db,
            browser_manager=browser_manager,
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
    source_worker_stop = asyncio.Event()
    source_worker_tasks = [
        asyncio.create_task(_source_worker_loop(f"source-worker-{index + 1}"))
        for index in range(max(0, int(SETTINGS.source_worker_count)))
    ]
    if SETTINGS.inbox_watcher_enabled:
        inbox_watcher = WatchedInboxService(
            source_store=source_store,
            inbox_path=SETTINGS.inbox_path,
            poll_interval_seconds=SETTINGS.inbox_poll_interval_seconds,
            file_stable_seconds=SETTINGS.inbox_file_stable_seconds,
            max_pending_jobs=SETTINGS.source_job_max_pending,
            emit_event=emit_ui_event,
        )
        await inbox_watcher.start()
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
        # Innovation Mind - Reactor: 8 methods running in parallel
        from aily.sessions.reactor_scheduler import NozzleConfig
        nozzle_config = NozzleConfig(
            min_confidence=SETTINGS.minds.proposal_min_confidence,
            max_proposals_per_session=SETTINGS.minds.proposal_max_per_session,
        )
        innovation_scheduler = ReactorScheduler(
            llm_client=llm_resolver("reactor"),
            graph_db=graph_db,
            obsidian_writer=dikiwi_writer or writer,
            feishu_pusher=pusher,
            schedule_hour=SETTINGS.minds.innovation_time.hour,
            schedule_minute=SETTINGS.minds.innovation_time.minute,
            circuit_breaker_threshold=SETTINGS.minds.circuit_breaker_threshold,
            enabled=SETTINGS.minds.innovation_enabled,
            nozzle_config=nozzle_config,
            method_timeout_seconds=SETTINGS.reactor_method_timeout_seconds,
        )
        if SETTINGS.minds.innovation_enabled:
            innovation_scheduler.start()
            logger.info("Reactor Innovation Mind started (8am daily - 8 methods in parallel)")

        # Entrepreneur Mind - 9am daily GStack analysis with agentic execution
        entrepreneur_scheduler = EntrepreneurScheduler(
            llm_client=llm_resolver("entrepreneur"),
            graph_db=graph_db,
            innovation_scheduler=innovation_scheduler,
            obsidian_writer=dikiwi_writer or writer,
            feishu_pusher=pusher,
            schedule_hour=SETTINGS.minds.entrepreneur_time.hour,
            schedule_minute=SETTINGS.minds.entrepreneur_time.minute,
            proposal_min_confidence=SETTINGS.minds.proposal_min_confidence,
            proposal_max_per_session=SETTINGS.minds.proposal_max_per_session,
            circuit_breaker_threshold=SETTINGS.minds.circuit_breaker_threshold,
            enabled=SETTINGS.minds.entrepreneur_enabled,
            tool_executor=_tool_executor,
            gstack_llm_client=llm_resolver("gstack"),
            guru_llm_client=llm_resolver("guru"),
        )
        if SETTINGS.minds.entrepreneur_enabled:
            entrepreneur_scheduler.start()
            logger.info("Entrepreneur Mind (Agentic) started (9am daily GStack with real actions)")

        # Wire Innovation and Entrepreneur into DIKIWI Mind for per-pipeline evaluation
        if dikiwi_mind and innovation_scheduler:
            dikiwi_mind.reactor_scheduler = innovation_scheduler
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
    if source_worker_stop:
        source_worker_stop.set()
    for task in workflow_tasks.values():
        task.cancel()
    if workflow_tasks:
        await asyncio.gather(*workflow_tasks.values(), return_exceptions=True)
        workflow_tasks.clear()
    if inbox_watcher:
        await inbox_watcher.stop()
        inbox_watcher = None
    for task in source_worker_tasks:
        task.cancel()
    if source_worker_tasks:
        await asyncio.gather(*source_worker_tasks, return_exceptions=True)
        source_worker_tasks = []
    if worker:
        await worker.stop()
    await workflow_run_store.close()
    await source_store.close()
    await fetcher.stop()
    if browser_manager:
        try:
            await browser_manager.stop()
        except Exception:
            pass
    logger.info("Aily shutdown complete")


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def hosted_mode_guard(request: Request, call_next):
    if SETTINGS.hosted_mode and (request.url.path == "/" or request.url.path.startswith("/assets/")):
        token = SETTINGS.ui_auth_token
        bearer = request.headers.get("authorization", "")
        explicit_token = request.headers.get("x-aily-token", "")
        query_token = request.query_params.get("token", "")
        cookie_token = request.cookies.get("aily_ui_token", "")
        if not token or (
            bearer != f"Bearer {token}"
            and explicit_token != token
            and query_token != token
            and cookie_token != token
        ):
            await audit_logger.log(
                "hosted_static_rejected",
                path=request.url.path,
                client=request.client.host if request.client else "unknown",
            )
            return JSONResponse({"detail": "Aily hosted mode authentication required"}, status_code=401)
    response = await call_next(request)
    if SETTINGS.hosted_mode and SETTINGS.ui_auth_token and request.query_params.get("token") == SETTINGS.ui_auth_token:
        response.set_cookie(
            "aily_ui_token",
            SETTINGS.ui_auth_token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
    if request.url.path.startswith("/api/ui"):
        await audit_logger.log(
            "ui_request",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            client=request.client.host if request.client else "unknown",
        )
    return response


@app.post("/api/ui/logout", include_in_schema=False)
async def ui_logout(request: Request) -> JSONResponse:
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(
        "aily_ui_token",
        path="/",
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    await audit_logger.log(
        "ui_logout",
        client=request.client.host if request.client else "unknown",
    )
    return response


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, Any]:
    return {"status": "ok", "hosted_mode": SETTINGS.hosted_mode}


@app.get("/ready", include_in_schema=False)
async def ready() -> dict[str, Any]:
    return {
        "status": "ready",
        "graph_db_configured": bool(SETTINGS.graph_db_path),
        "source_store_configured": bool(SETTINGS.source_store_db_path),
        "vault_configured": bool(SETTINGS.obsidian_vault_path or SETTINGS.dikiwi_vault_path),
        "studio_auth_required": SETTINGS.hosted_mode or SETTINGS.ui_auth_enabled,
    }

app.include_router(webhook.router)
app.include_router(
    create_ui_router(
        upload_handler=_handle_ui_upload,
        batch_upload_handler=_handle_ui_upload_batch,
        url_handler=_handle_ui_url,
        text_handler=_handle_ui_text,
        status_provider=_ui_status_provider,
        graph_provider=_ui_graph_provider,
        pipeline_provider=_ui_pipeline_provider,
        source_provider=_ui_sources_provider,
        source_detail_provider=_ui_source_detail_provider,
        source_jobs_provider=_ui_source_jobs_provider,
        workflow_trigger_handler=_ui_iwi_workflow_trigger,
        workflow_provider=_ui_workflows_provider,
        proposal_provider=_ui_proposals_provider,
        entrepreneurship_provider=_ui_entrepreneurship_provider,
        vault_notes_provider=_ui_vault_notes_provider,
        control_handler=_ui_control_handler,
        run_registry=RunRegistry(SETTINGS.evidence_runs_dir),
        enable_uploads=HAS_MULTIPART,
        max_files_per_request=SETTINGS.ui_max_upload_files,
        max_upload_bytes=SETTINGS.max_file_size,
        auth_token=SETTINGS.ui_auth_token if (SETTINGS.ui_auth_enabled or SETTINGS.hosted_mode) else "",
        rate_limiter=ui_rate_limiter,
        trust_proxy_headers=SETTINGS.trusted_proxy_headers,
    )
)


def _configure_frontend_static(fastapi_app: FastAPI, dist_path: Path = FRONTEND_DIST_PATH) -> None:
    """Serve the built Aily Studio frontend when `frontend/dist` exists."""
    index_path = dist_path / "index.html"
    if not index_path.exists():
        logger.info("Aily Studio frontend build not found at %s; skipping static mount", dist_path)
        return

    assets_path = dist_path / "assets"
    if assets_path.exists():
        fastapi_app.mount("/assets", StaticFiles(directory=assets_path), name="aily_studio_assets")

    @fastapi_app.get("/", include_in_schema=False)
    async def _frontend_index() -> FileResponse:
        return FileResponse(index_path)

    @fastapi_app.get("/{full_path:path}", include_in_schema=False)
    async def _frontend_spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith(("api/", "webhook")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (dist_path / full_path).resolve()
        dist_root = dist_path.resolve()
        if candidate.is_file() and (candidate == dist_root or dist_root in candidate.parents):
            return FileResponse(candidate)
        return FileResponse(index_path)


_configure_frontend_static(app)


if __name__ == "__main__":
    uvicorn.run("aily.main:app", host="127.0.0.1", port=8000, reload=False)
