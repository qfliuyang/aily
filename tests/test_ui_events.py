from __future__ import annotations

import asyncio

import pytest

from aily.ui.events import UIEventHub


@pytest.mark.asyncio
async def test_ui_event_hub_buffers_and_indexes_events() -> None:
    hub = UIEventHub(max_events=10)

    await hub.emit("pipeline_started", pipeline_id="pipe-1", upload_id="up-1")
    await hub.emit("stage_started", pipeline_id="pipe-1", stage="DATA")
    await hub.emit("pipeline_completed", pipeline_id="pipe-1")

    assert len(hub.recent_events()) == 3
    assert len(hub.pipeline_trace("pipe-1")) == 3
    assert len(hub.upload_trace("up-1")) == 1
    assert hub.active_pipeline_ids() == []


@pytest.mark.asyncio
async def test_ui_event_hub_broadcasts_to_subscribers() -> None:
    hub = UIEventHub(max_events=10)
    queue = hub.subscribe()

    await hub.emit("llm_request_started", pipeline_id="pipe-2", stage="DATA")
    event = await asyncio.wait_for(queue.get(), timeout=1)

    assert event["type"] == "llm_request_started"
    assert event["pipeline_id"] == "pipe-2"

