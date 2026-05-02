from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UIEventHub:
    """In-memory event hub for Aily Studio.

    This is intentionally simple for the first frontend iteration:
    - stores a rolling event buffer for replay
    - broadcasts events to websocket subscribers
    - indexes events by pipeline_id and upload_id for trace views
    """

    def __init__(self, max_events: int = 5000) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._pipelines: dict[str, list[dict[str, Any]]] = {}
        self._uploads: dict[str, list[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def emit(self, event_type: str, **payload: Any) -> dict[str, Any]:
        event = {
            "id": payload.pop("id", str(uuid4())),
            "type": event_type,
            "timestamp": payload.pop("timestamp", _utc_now_iso()),
            **payload,
        }
        async with self._lock:
            self._events.append(event)
            pipeline_id = event.get("pipeline_id")
            if pipeline_id:
                self._pipelines.setdefault(str(pipeline_id), []).append(event)
            upload_id = event.get("upload_id")
            if upload_id:
                self._uploads.setdefault(str(upload_id), []).append(event)
            dead: list[asyncio.Queue[dict[str, Any]]] = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    dead.append(queue)
            for queue in dead:
                self._subscribers.discard(queue)
        return event

    def subscribe(self, max_queue_size: int = 500) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def recent_events(self, limit: int = 200) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return list(self._events)[-limit:]

    def pipeline_trace(self, pipeline_id: str) -> list[dict[str, Any]]:
        return list(self._pipelines.get(str(pipeline_id), []))

    def upload_trace(self, upload_id: str) -> list[dict[str, Any]]:
        return list(self._uploads.get(str(upload_id), []))

    def active_pipeline_ids(self) -> list[str]:
        recent = {}
        for event in self._events:
            pipeline_id = event.get("pipeline_id")
            if pipeline_id:
                recent[str(pipeline_id)] = event
        active = []
        for pipeline_id, event in recent.items():
            if event.get("type") not in {"pipeline_completed", "pipeline_failed"}:
                active.append(pipeline_id)
        return active


ui_event_hub = UIEventHub()


async def emit_ui_event(event_type: str, **payload: Any) -> dict[str, Any]:
    return await ui_event_hub.emit(event_type, **payload)

