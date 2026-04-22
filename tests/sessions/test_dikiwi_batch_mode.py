from __future__ import annotations

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


def _drop(label: str) -> RainDrop:
    return RainDrop(
        id=f"drop_{label}",
        rain_type=RainType.DOCUMENT,
        content=f"content {label}",
        source="chaos_processor",
        stream_type=StreamType.EXTRACT_ANALYZE,
        metadata={"source_paths": [f"/tmp/{label}.pdf"]},
    )


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
