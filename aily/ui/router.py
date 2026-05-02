from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from starlette.requests import HTTPConnection

from aily.ui.events import emit_ui_event, ui_event_hub
from aily.verify.run_registry import RunNotFoundError, RunRegistry
from aily.security.rate_limit import FixedWindowRateLimiter


def create_ui_router(
    *,
    upload_handler: Callable[[UploadFile, str], Awaitable[dict[str, Any]]] | None,
    batch_upload_handler: Callable[[list[tuple[UploadFile, str]], str], Awaitable[dict[str, Any]]] | None = None,
    status_provider: Callable[[], Awaitable[dict[str, Any]]],
    graph_provider: Callable[[], Awaitable[dict[str, Any]]],
    pipeline_provider: Callable[[str], Awaitable[dict[str, Any] | None]],
    url_handler: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
    source_provider: Callable[[int, int], Awaitable[dict[str, Any]]] | None = None,
    source_detail_provider: Callable[[str], Awaitable[dict[str, Any] | None]] | None = None,
    proposal_provider: Callable[[int], Awaitable[dict[str, Any]]] | None = None,
    entrepreneurship_provider: Callable[[int], Awaitable[dict[str, Any]]] | None = None,
    control_handler: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
    rate_limiter: FixedWindowRateLimiter | None = None,
    run_registry: RunRegistry | None = None,
    enable_uploads: bool = True,
    max_files_per_request: int = 8,
    max_upload_bytes: int | None = None,
    auth_token: str = "",
) -> APIRouter:
    def _request_authorized(request: HTTPConnection) -> bool:
        if not auth_token:
            return True
        bearer = request.headers.get("authorization", "")
        explicit_token = request.headers.get("x-aily-token", "")
        query_token = request.query_params.get("token", "")
        return bearer == f"Bearer {auth_token}" or explicit_token == auth_token or query_token == auth_token

    async def _require_auth(request: HTTPConnection) -> None:
        if not _request_authorized(request):
            raise HTTPException(status_code=401, detail="Aily Studio authentication required")

    def _websocket_authorized(websocket: WebSocket) -> bool:
        if not auth_token:
            return True
        bearer = websocket.headers.get("authorization", "")
        explicit_token = websocket.headers.get("x-aily-token", "")
        query_token = websocket.query_params.get("token", "")
        return bearer == f"Bearer {auth_token}" or explicit_token == auth_token or query_token == auth_token

    router = APIRouter(prefix="/api/ui", tags=["ui"], dependencies=[Depends(_require_auth)])

    def _client_key(request: HTTPConnection) -> str:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        return request.client.host if request.client else "unknown"

    def _check_rate_limit(request: HTTPConnection) -> None:
        if rate_limiter is None:
            return
        allowed, retry_after = rate_limiter.allow(_client_key(request))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

    if enable_uploads:
        @router.post("/uploads")
        async def upload_files(request: Request, files: list[UploadFile] = File(...)) -> dict[str, Any]:
            _check_rate_limit(request)
            if upload_handler is None:
                raise HTTPException(status_code=503, detail="Upload handler unavailable")
            if not files:
                raise HTTPException(status_code=400, detail="No files uploaded")
            if len(files) > max_files_per_request:
                raise HTTPException(
                    status_code=400,
                    detail=f"Too many files uploaded; limit is {max_files_per_request}",
                )
            if max_upload_bytes is not None:
                oversized = [
                    file.filename or "unknown"
                    for file in files
                    if getattr(file, "size", None) is not None and file.size > max_upload_bytes
                ]
                if oversized:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds max upload size of {max_upload_bytes} bytes: {oversized[0]}",
                    )

            upload_refs = [(file, str(uuid4())) for file in files]
            if len(upload_refs) > 1 and batch_upload_handler is not None:
                batch_id = str(uuid4())
                await emit_ui_event(
                    "upload_batch_started",
                    batch_id=batch_id,
                    file_count=len(upload_refs),
                )
                return await batch_upload_handler(upload_refs, batch_id)

            accepted: list[dict[str, Any]] = []
            for file, upload_id in upload_refs:
                size_bytes = getattr(file, "size", None)
                await emit_ui_event(
                    "source_uploaded",
                    upload_id=upload_id,
                    filename=file.filename or "unknown",
                    content_type=file.content_type or "application/octet-stream",
                    size_bytes=size_bytes,
                )
                accepted.append(await upload_handler(file, upload_id))
            return {"uploads": accepted}
    else:
        @router.post("/uploads")
        async def upload_files_unavailable(request: Request) -> dict[str, Any]:
            _check_rate_limit(request)
            raise HTTPException(
                status_code=503,
                detail="File uploads require python-multipart to be installed",
            )

    @router.post("/sources/urls")
    async def submit_url(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
        _check_rate_limit(request)
        if url_handler is None:
            raise HTTPException(status_code=503, detail="URL intake unavailable")
        url = str(payload.get("url", "")).strip()
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(status_code=400, detail="Only http(s) URLs are supported")
        source = await url_handler(url)
        await emit_ui_event(
            "source_stored",
            source_id=source.get("source_id"),
            source_type="url",
            url=url,
            duplicate=source.get("duplicate"),
            sha256=source.get("sha256"),
        )
        return source

    @router.get("/status")
    async def ui_status() -> dict[str, Any]:
        return await status_provider()

    @router.get("/graph")
    async def graph_snapshot() -> dict[str, Any]:
        return await graph_provider()

    @router.get("/pipelines/{pipeline_id}")
    async def pipeline_trace(pipeline_id: str) -> dict[str, Any]:
        payload = await pipeline_provider(pipeline_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        return payload

    @router.get("/uploads/{upload_id}")
    async def upload_trace(upload_id: str) -> dict[str, Any]:
        return {
            "upload_id": upload_id,
            "events": ui_event_hub.upload_trace(upload_id),
        }

    @router.get("/events/query")
    async def query_events(
        run_id: str | None = None,
        pipeline_id: str | None = None,
        upload_id: str | None = None,
        event_type: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        events = await ui_event_hub.query_persisted(
            run_id=run_id,
            pipeline_id=pipeline_id,
            upload_id=upload_id,
            event_type=event_type,
            limit=limit,
        )
        return {
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "upload_id": upload_id,
            "event_type": event_type,
            "events": events,
        }

    @router.get("/sources")
    async def list_sources(limit: int = 100, offset: int = 0) -> dict[str, Any]:
        if source_provider is None:
            return {"total": 0, "sources": []}
        return await source_provider(limit, offset)

    @router.get("/sources/{source_id}")
    async def source_detail(source_id: str) -> dict[str, Any]:
        if source_detail_provider is None:
            raise HTTPException(status_code=404, detail="Source store unavailable")
        payload = await source_detail_provider(source_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Source not found")
        return payload

    @router.get("/proposals")
    async def list_proposals(limit: int = 50) -> dict[str, Any]:
        if proposal_provider is None:
            return {"total": 0, "items": []}
        return await proposal_provider(limit)

    @router.get("/entrepreneurship")
    async def list_entrepreneurship(limit: int = 50) -> dict[str, Any]:
        if entrepreneurship_provider is None:
            return {"total": 0, "items": []}
        return await entrepreneurship_provider(limit)

    @router.post("/control")
    async def control(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
        _check_rate_limit(request)
        if control_handler is None:
            raise HTTPException(status_code=503, detail="Studio controls unavailable")
        action = str(payload.get("action", "")).strip()
        if not action:
            raise HTTPException(status_code=400, detail="Control action is required")
        return await control_handler(action, payload)

    @router.get("/logs")
    async def recent_logs(limit: int = 200) -> dict[str, Any]:
        return {"events": ui_event_hub.recent_events(limit=limit)}

    @router.get("/runs")
    async def list_runs(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        if run_registry is None:
            return {"root_dir": "", "total": 0, "runs": []}
        return run_registry.list_runs(limit=limit, offset=offset)

    @router.get("/runs/{run_id}")
    async def run_detail(run_id: str) -> dict[str, Any]:
        if run_registry is None:
            raise HTTPException(status_code=404, detail="Run registry unavailable")
        try:
            return run_registry.get_run(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/runs/{run_id}/events")
    async def run_events(run_id: str, limit: int = 500) -> dict[str, Any]:
        if run_registry is None:
            raise HTTPException(status_code=404, detail="Run registry unavailable")
        try:
            return run_registry.get_events(run_id, limit=limit)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/runs/{run_id}/llm-calls")
    async def run_llm_calls(run_id: str, limit: int = 500) -> dict[str, Any]:
        if run_registry is None:
            raise HTTPException(status_code=404, detail="Run registry unavailable")
        try:
            return run_registry.get_llm_calls(run_id, limit=limit)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.websocket("/events")
    async def ui_events_socket(websocket: WebSocket) -> None:
        if not _websocket_authorized(websocket):
            await websocket.close(code=1008, reason="Aily Studio authentication required")
            return
        await websocket.accept()
        queue = ui_event_hub.subscribe()
        try:
            for event in ui_event_hub.recent_events(limit=50):
                await websocket.send_json(event)
            while True:
                event = await queue.get()
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            ui_event_hub.unsubscribe(queue)
            with contextlib.suppress(Exception):
                await websocket.close()

    return router
