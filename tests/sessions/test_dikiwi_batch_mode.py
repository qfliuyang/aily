from __future__ import annotations

import asyncio
from dataclasses import dataclass

from aily.config import SETTINGS
from aily.gating.drainage import RainDrop, RainType, StreamType
from aily.sessions.dikiwi_mind import DikiwiMind, DikiwiStage, StageResult


@dataclass
class FakeGraphDB:
    counts: list[int]

    async def count_nodes_by_type(self, node_type: str) -> int:
        assert node_type == "information"
        return self.counts.pop(0)


class FakeAgent:
    def __init__(self, stage: DikiwiStage, log: list[tuple[str, str]], trigger_map: dict[str, bool] | None = None):
        self.stage = stage
        self.log = log
        self.trigger_map = trigger_map or {}

    async def execute(self, ctx) -> StageResult:
        self.log.append((self.stage.name, ctx.pipeline_id))
        data = {}
        if self.stage == DikiwiStage.KNOWLEDGE:
            data["network_synthesis_triggered"] = self.trigger_map.get(ctx.drop.id, False)
        return StageResult(stage=self.stage, success=True, data=data)


class SlowAgent:
    async def execute(self, ctx) -> StageResult:
        await asyncio.sleep(1)
        return StageResult(stage=DikiwiStage.DATA, success=True)


class FailingAgent:
    def __init__(self, stage: DikiwiStage):
        self.stage = stage

    async def execute(self, ctx) -> StageResult:
        return StageResult(stage=self.stage, success=False, error_message=f"{self.stage.name} failed")


def _drop(label: str) -> RainDrop:
    return RainDrop(
        id=f"drop_{label}",
        rain_type=RainType.DOCUMENT,
        content=f"content {label}",
        source="chaos_processor",
        stream_type=StreamType.EXTRACT_ANALYZE,
        metadata={"source_paths": [f"/tmp/{label}.pdf"]},
    )


async def test_batch_mode_emits_batch_stage_barrier_events(monkeypatch):
    log: list[tuple[str, str]] = []
    events: list[tuple[str, dict]] = []
    mind = DikiwiMind(graph_db=FakeGraphDB([100, 103]), llm_client=object())

    def fake_registry():
        return {
            DikiwiStage.DATA: FakeAgent(DikiwiStage.DATA, log),
            DikiwiStage.INFORMATION: FakeAgent(DikiwiStage.INFORMATION, log),
            DikiwiStage.KNOWLEDGE: FakeAgent(DikiwiStage.KNOWLEDGE, log, trigger_map={}),
            DikiwiStage.INSIGHT: FakeAgent(DikiwiStage.INSIGHT, log),
            DikiwiStage.WISDOM: FakeAgent(DikiwiStage.WISDOM, log),
            DikiwiStage.IMPACT: FakeAgent(DikiwiStage.IMPACT, log),
        }

    async def fake_emit(event_type: str, **payload):
        events.append((event_type, payload))
        return {"type": event_type, **payload}

    monkeypatch.setattr(mind, "_build_agent_registry", fake_registry)
    monkeypatch.setattr("aily.sessions.dikiwi_mind.emit_ui_event", fake_emit)

    await mind.process_inputs_batched([_drop("a"), _drop("b")], incremental_threshold=0.05)

    barrier_events = [
        (event_type, payload["stage"])
        for event_type, payload in events
        if event_type in {"batch_stage_started", "batch_stage_completed"}
    ]
    assert barrier_events == [
        ("batch_stage_started", "DATA"),
        ("batch_stage_completed", "DATA"),
        ("batch_stage_started", "INFORMATION"),
        ("batch_stage_completed", "INFORMATION"),
        ("batch_stage_started", "KNOWLEDGE"),
        ("batch_stage_completed", "KNOWLEDGE"),
    ]


async def test_batch_mode_is_stage_latched_and_threshold_gated(monkeypatch):
    log: list[tuple[str, str]] = []
    mind = DikiwiMind(graph_db=FakeGraphDB([100, 103]), llm_client=object())

    def fake_registry():
        return {
            DikiwiStage.DATA: FakeAgent(DikiwiStage.DATA, log),
            DikiwiStage.INFORMATION: FakeAgent(DikiwiStage.INFORMATION, log),
            DikiwiStage.KNOWLEDGE: FakeAgent(DikiwiStage.KNOWLEDGE, log, trigger_map={}),
            DikiwiStage.INSIGHT: FakeAgent(DikiwiStage.INSIGHT, log),
            DikiwiStage.WISDOM: FakeAgent(DikiwiStage.WISDOM, log),
            DikiwiStage.IMPACT: FakeAgent(DikiwiStage.IMPACT, log),
        }

    monkeypatch.setattr(mind, "_build_agent_registry", fake_registry)

    batch = await mind.process_inputs_batched([_drop("a"), _drop("b")], incremental_threshold=0.05)

    assert batch.higher_order_triggered is False
    assert batch.incremental_ratio == 0.03
    assert [stage for stage, _ in log] == [
        "DATA", "DATA",
        "INFORMATION", "INFORMATION",
        "KNOWLEDGE", "KNOWLEDGE",
    ]


async def test_batch_mode_runs_higher_order_only_for_affected_contexts(monkeypatch):
    log: list[tuple[str, str]] = []
    mind = DikiwiMind(graph_db=FakeGraphDB([100, 110]), llm_client=object())

    trigger_map: dict[str, bool] = {"drop_a": True, "drop_b": False}

    def fake_registry():
        return {
            DikiwiStage.DATA: FakeAgent(DikiwiStage.DATA, log),
            DikiwiStage.INFORMATION: FakeAgent(DikiwiStage.INFORMATION, log),
            DikiwiStage.KNOWLEDGE: FakeAgent(DikiwiStage.KNOWLEDGE, log, trigger_map=trigger_map),
            DikiwiStage.INSIGHT: FakeAgent(DikiwiStage.INSIGHT, log),
            DikiwiStage.WISDOM: FakeAgent(DikiwiStage.WISDOM, log),
            DikiwiStage.IMPACT: FakeAgent(DikiwiStage.IMPACT, log),
        }

    monkeypatch.setattr(mind, "_build_agent_registry", fake_registry)
    batch = await mind.process_inputs_batched([_drop("a"), _drop("b")], incremental_threshold=0.05)

    assert batch.higher_order_triggered is True
    insight_calls = [pipeline_id for stage, pipeline_id in log if stage == "INSIGHT"]
    wisdom_calls = [pipeline_id for stage, pipeline_id in log if stage == "WISDOM"]
    impact_calls = [pipeline_id for stage, pipeline_id in log if stage == "IMPACT"]
    assert len(insight_calls) == 1
    assert insight_calls == wisdom_calls == impact_calls


async def test_batch_stage_timeout_records_stage_failure(monkeypatch):
    original_timeout = SETTINGS.dikiwi_stage_timeout_seconds
    events: list[tuple[str, dict]] = []
    mind = DikiwiMind(graph_db=None, llm_client=object())
    contexts = [mind._build_agent_context(_drop("slow"), "pipeline-slow")]

    async def fake_emit(event_type: str, **payload):
        events.append((event_type, payload))
        return {"type": event_type, **payload}

    try:
        SETTINGS.dikiwi_stage_timeout_seconds = 0.01
        monkeypatch.setattr("aily.sessions.dikiwi_mind.emit_ui_event", fake_emit)

        results = await mind._execute_batch_stage(
            contexts,
            stage=DikiwiStage.DATA,
            agent=SlowAgent(),
            max_concurrency=1,
        )
    finally:
        SETTINGS.dikiwi_stage_timeout_seconds = original_timeout

    assert results[0].success is False
    assert "timed out" in (results[0].error_message or "")
    assert any(event_type == "stage_failed" for event_type, _ in events)
    assert events[-1][0] == "batch_stage_completed"
    assert events[-1][1]["failure_count"] == 1


async def test_empty_batch_stage_does_not_emit_fake_events(monkeypatch):
    events: list[tuple[str, dict]] = []
    mind = DikiwiMind(graph_db=None, llm_client=object())

    async def fake_emit(event_type: str, **payload):
        events.append((event_type, payload))
        return {"type": event_type, **payload}

    monkeypatch.setattr("aily.sessions.dikiwi_mind.emit_ui_event", fake_emit)

    results = await mind._execute_batch_stage(
        [],
        stage=DikiwiStage.IMPACT,
        agent=FakeAgent(DikiwiStage.IMPACT, []),
        max_concurrency=1,
    )

    assert results == []
    assert events == []


async def test_batch_threshold_event_requires_successful_knowledge(monkeypatch):
    events: list[tuple[str, dict]] = []
    mind = DikiwiMind(graph_db=FakeGraphDB([100, 100]), llm_client=object())

    def fake_registry():
        return {
            DikiwiStage.DATA: FailingAgent(DikiwiStage.DATA),
            DikiwiStage.INFORMATION: FakeAgent(DikiwiStage.INFORMATION, []),
            DikiwiStage.KNOWLEDGE: FakeAgent(DikiwiStage.KNOWLEDGE, []),
            DikiwiStage.INSIGHT: FakeAgent(DikiwiStage.INSIGHT, []),
            DikiwiStage.WISDOM: FakeAgent(DikiwiStage.WISDOM, []),
            DikiwiStage.IMPACT: FakeAgent(DikiwiStage.IMPACT, []),
        }

    async def fake_emit(event_type: str, **payload):
        events.append((event_type, payload))
        return {"type": event_type, **payload}

    monkeypatch.setattr(mind, "_build_agent_registry", fake_registry)
    monkeypatch.setattr("aily.sessions.dikiwi_mind.emit_ui_event", fake_emit)

    batch = await mind.process_inputs_batched([_drop("a"), _drop("b")], incremental_threshold=0.05)

    assert batch.higher_order_triggered is False
    assert not any(event_type.startswith("threshold_") for event_type, _ in events)
    assert not any(payload.get("stage") == "KNOWLEDGE" for event_type, payload in events if event_type.startswith("batch_stage_"))


async def test_single_drop_chaos_processing_is_suppressed_when_batch_lock_active(tmp_path):
    original_lock_path = SETTINGS.dikiwi_batch_lock_path
    try:
        SETTINGS.dikiwi_batch_lock_path = tmp_path / "dikiwi_batch.lock"
        SETTINGS.dikiwi_batch_lock_path.write_text("active", encoding="utf-8")
        mind = DikiwiMind(graph_db=None, llm_client=object())

        result = await mind.process_input(_drop("locked"))

        assert result.stage_results
        assert result.stage_results[0].success is False
        assert "batch lock" in (result.stage_results[0].error_message or "")
    finally:
        SETTINGS.dikiwi_batch_lock_path = original_lock_path
