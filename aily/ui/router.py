from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from aily.ui.events import emit_ui_event, ui_event_hub


def create_ui_router(
    *,
    upload_handler: Callable[[UploadFile, str], Awaitable[dict[str, Any]]] | None,
    status_provider: Callable[[], Awaitable[dict[str, Any]]],
    graph_provider: Callable[[], Awaitable[dict[str, Any]]],
    pipeline_provider: Callable[[str], Awaitable[dict[str, Any] | None]],
    enable_uploads: bool = True,
) -> APIRouter:
    router = APIRouter(prefix="/api/ui", tags=["ui"])

    if enable_uploads:
        @router.post("/uploads")
        async def upload_files(files: list[UploadFile] = File(...)) -> dict[str, Any]:
            if upload_handler is None:
                raise HTTPException(status_code=503, detail="Upload handler unavailable")
            if not files:
                raise HTTPException(status_code=400, detail="No files uploaded")

            accepted: list[dict[str, Any]] = []
            for file in files:
                upload_id = str(uuid4())
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

    @router.get("/logs")
    async def recent_logs(limit: int = 200) -> dict[str, Any]:
        return {"events": ui_event_hub.recent_events(limit=limit)}

    @router.websocket("/events")
    async def ui_events_socket(websocket: WebSocket) -> None:
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
