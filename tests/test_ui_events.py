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


@pytest.mark.asyncio
async def test_ui_event_hub_bounds_pipeline_and_upload_traces() -> None:
    hub = UIEventHub(max_events=20, trace_limit=2)

    for idx in range(4):
        await hub.emit("stage_completed", pipeline_id="pipe-3", upload_id="up-3", stage=f"S{idx}")

    pipeline_events = hub.pipeline_trace("pipe-3")
    upload_events = hub.upload_trace("up-3")

    assert len(pipeline_events) == 2
    assert len(upload_events) == 2
    assert [event["stage"] for event in pipeline_events] == ["S2", "S3"]


@pytest.mark.asyncio
async def test_ui_event_hub_persists_and_reloads_events(tmp_path) -> None:
    event_log = tmp_path / "ui-events.jsonl"
    hub = UIEventHub(max_events=10)
    hub.configure_persistence(event_log)

    await hub.emit(
        "stage_completed",
        run_id="run-1",
        pipeline_id="pipe-1",
        upload_id="upload-1",
        stage="DATA",
    )

    restored = UIEventHub(max_events=10)
    restored.configure_persistence(event_log)
    loaded = await restored.load_persisted()

    assert loaded == 1
    assert restored.recent_events()[0]["type"] == "stage_completed"
    assert restored.pipeline_trace("pipe-1")[0]["stage"] == "DATA"
    assert restored.upload_trace("upload-1")[0]["stage"] == "DATA"
    assert restored.run_trace("run-1")[0]["stage"] == "DATA"


@pytest.mark.asyncio
async def test_ui_event_hub_queries_persisted_events_by_lineage_ids(tmp_path) -> None:
    event_log = tmp_path / "ui-events.jsonl"
    hub = UIEventHub(max_events=10)
    hub.configure_persistence(event_log)

    await hub.emit("stage_started", run_id="run-1", pipeline_id="pipe-1", upload_id="up-1", stage="DATA")
    await hub.emit("stage_started", run_id="run-2", pipeline_id="pipe-2", upload_id="up-2", stage="IMPACT")

    restored = UIEventHub(max_events=10)
    restored.configure_persistence(event_log)

    by_run = await restored.query_persisted(run_id="run-1")
    by_pipeline = await restored.query_persisted(pipeline_id="pipe-2")
    by_upload = await restored.query_persisted(upload_id="up-1", event_type="stage_started")

    assert [event["stage"] for event in by_run] == ["DATA"]
    assert [event["stage"] for event in by_pipeline] == ["IMPACT"]
    assert [event["pipeline_id"] for event in by_upload] == ["pipe-1"]
