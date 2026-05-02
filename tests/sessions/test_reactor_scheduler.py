from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import aily.sessions.reactor_scheduler as reactor_scheduler_module
from aily.sessions.reactor_scheduler import (
    DEFAULT_REACTOR_METHODS,
    InnovationMethod,
    ReactorScheduler,
    MethodResult,
    NozzleConfig,
)
from aily.sessions.models import Proposal
from aily.thinking.models import (
    FrameworkInsight,
    FrameworkType,
    InsightPriority,
    PrincipleRecommendation,
)


@pytest.fixture
def mock_llm_client():
    return MagicMock()


@pytest.fixture
def mock_graph_db():
    db = AsyncMock()
    db.get_recent_nodes = AsyncMock(
        return_value=[{"label": "Retrieval quality", "type": "concept"}]
    )
    return db


@pytest.fixture
def mock_obsidian_writer():
    writer = AsyncMock()
    writer.write_note = AsyncMock(return_value="Aily/Proposals/Innovation/test.md")
    return writer


class TestReactorScheduler:
    def test_init_defaults(self, mock_llm_client, mock_graph_db):
        scheduler = ReactorScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        assert scheduler.mind_name == "reactor"
        assert scheduler.schedule_hour == 8
        assert scheduler.schedule_minute == 0
        assert scheduler.nozzle_config.enabled_methods == DEFAULT_REACTOR_METHODS
        assert InnovationMethod.TRIZ in scheduler.nozzle_config.enabled_methods

    @pytest.mark.asyncio
    async def test_run_session_stores_current_proposals(
        self,
        mock_llm_client,
        mock_graph_db,
        mock_obsidian_writer,
        monkeypatch,
    ):
        proposal = Proposal(
            mind_name="reactor",
            title="Faster Context Routing",
            content="Route context by task shape before retrieval.",
            summary="Route context by task shape before retrieval.",
            confidence=0.91,
        )
        scheduler = ReactorScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            obsidian_writer=mock_obsidian_writer,
            nozzle_config=NozzleConfig(enabled_methods={InnovationMethod.TRIZ}),
        )

        async def fake_run_method(method, context, budget=None):
            return MethodResult(
                method=method,
                proposals=[proposal],
                confidence=0.91,
            )

        monkeypatch.setattr(scheduler, "_run_method", fake_run_method)

        result = await scheduler._run_session()

        assert result["proposals_generated"] == 1
        assert scheduler.get_current_proposals() == [proposal]
        mock_obsidian_writer.write_note.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_persist_framework_proposals_enqueues_for_entrepreneur(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        scheduler = ReactorScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )
        proposal = Proposal(
            id="reactor_prop_1",
            mind_name="reactor",
            title="TRIZ Principle 10: Prior Action for Timing Closure",
            content="Use precomputed ECO hypotheses before signoff.",
            summary="Use precomputed ECO hypotheses before signoff.",
            confidence=0.82,
            framework_used="TRIZ",
        )

        await scheduler._persist_framework_proposals([proposal])

        mock_graph_db.insert_node.assert_any_await(
            node_id="reactor_prop_1",
            node_type="reactor_proposal",
            label="TRIZ Principle 10: Prior Action for Timing Closure: Use precomputed ECO hypotheses before signoff.",
            source="reactor",
        )
        mock_graph_db.set_node_property.assert_any_await(
            "reactor_prop_1", "status", "pending_business"
        )

    @pytest.mark.asyncio
    async def test_evaluate_context_can_persist_and_output_proposals(
        self,
        mock_llm_client,
        mock_graph_db,
        mock_obsidian_writer,
        monkeypatch,
    ):
        proposal = Proposal(
            id="reactor_prop_2",
            mind_name="reactor",
            title="Constraint Debugging Theater",
            content="Show constraint lineage as an interactive debugging graph.",
            summary="Show constraint lineage as an interactive debugging graph.",
            confidence=0.88,
            framework_used="TRIZ",
        )
        scheduler = ReactorScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            obsidian_writer=mock_obsidian_writer,
            nozzle_config=NozzleConfig(enabled_methods={InnovationMethod.TRIZ}),
        )

        async def fake_run_method(method, context, budget=None):
            return MethodResult(method=method, proposals=[proposal], confidence=0.88)

        monkeypatch.setattr(scheduler, "_run_method", fake_run_method)

        proposals = await scheduler.evaluate_context(
            {"focus_areas": ["eda"]},
            persist=True,
            output=True,
        )

        assert proposals == [proposal]
        mock_graph_db.insert_node.assert_awaited()
        mock_obsidian_writer.write_note.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_context_bounds_slow_methods(
        self,
        mock_llm_client,
        mock_graph_db,
        monkeypatch,
    ):
        scheduler = ReactorScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            nozzle_config=NozzleConfig(enabled_methods={InnovationMethod.TRIZ}),
            method_timeout_seconds=0.01,
        )

        async def slow_run_method(method, context, budget=None):
            await asyncio.sleep(1)
            return MethodResult(method=method, proposals=[], confidence=0.0)

        monkeypatch.setattr(scheduler, "_run_method", slow_run_method)

        proposals = await scheduler.evaluate_context({"focus_areas": ["eda"]})

        assert proposals == []

    @pytest.mark.asyncio
    async def test_run_method_adapts_triz_framework_output(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        scheduler = ReactorScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            nozzle_config=NozzleConfig(enabled_methods={InnovationMethod.TRIZ}),
        )

        fake_triz = MagicMock()
        fake_triz.analyze = AsyncMock(
            return_value=FrameworkInsight(
                framework_type=FrameworkType.TRIZ,
                insights=["Precompute fixes before timing closure loops begin."],
                confidence=0.83,
                priority=InsightPriority.HIGH,
                raw_analysis={
                    "contradictions": [],
                    "principle_recommendations": [
                        PrincipleRecommendation(
                            principle_number=10,
                            principle_name="Prior action",
                            application="Precompute fixes before timing closure loops begin.",
                            confidence_score=0.83,
                        )
                    ],
                },
                processing_time_ms=123,
            )
        )
        scheduler._analyzers[InnovationMethod.TRIZ] = fake_triz

        result = await scheduler._run_method(
            InnovationMethod.TRIZ,
            {"focus_areas": ["eda"], "recent_insights": [{"label": "Timing ECO loops", "type": "problem"}]},
        )

        assert isinstance(result, MethodResult)
        assert result.method == InnovationMethod.TRIZ
        assert result.proposals
        assert result.proposals[0].framework_used == "TRIZ"

    def test_node_to_proposal_keeps_structured_residual_metadata(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        scheduler = ReactorScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        proposal = scheduler._node_to_proposal(
            {
                "id": "residual_1234",
                "label": "Fallback Title: fallback description",
                "properties": {
                    "title": "Timing Closure Copilot",
                    "description": "Insert a ranked-fix assistant into signoff.",
                    "target_user": "Physical design engineers",
                    "economic_buyer": "VP of Silicon Engineering",
                    "proof_artifact": "Replay benchmark on ECO history",
                },
            },
            {"confidence": 0.82},
        )

        assert proposal.title == "Timing Closure Copilot"
        assert proposal.content == "Insert a ranked-fix assistant into signoff."
        assert proposal.metadata["target_user"] == "Physical design engineers"
        assert proposal.metadata["economic_buyer"] == "VP of Silicon Engineering"

    @pytest.mark.asyncio
    async def test_score_proposal_uses_structured_fields_in_prompt(
        self,
        mock_llm_client,
        mock_graph_db,
        monkeypatch,
    ):
        scheduler = ReactorScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )
        captured: dict[str, str] = {}

        async def fake_chat_json(*, llm_client, stage, messages, temperature, budget):
            captured["prompt"] = messages[0]["content"]
            return {
                "novelty": 0.74,
                "feasibility": 0.71,
                "confidence": 0.79,
                "source_grounding": 0.8,
                "buyer_clarity": 0.76,
                "workflow_insertion_clarity": 0.82,
                "validation_readiness": 0.7,
                "pass": True,
                "reason": "Strong structured brief",
            }

        monkeypatch.setattr(reactor_scheduler_module, "chat_json", fake_chat_json)

        score = await scheduler._score_proposal(
            {
                "id": "residual_1234",
                "label": "Fallback Title: fallback description",
                "properties": {
                    "title": "Timing Closure Copilot",
                    "problem": "Timing ECO loops are slow and manual.",
                    "solution": "Insert a ranked-fix assistant into signoff.",
                    "target_user": "Physical design engineers",
                    "economic_buyer": "VP of Silicon Engineering",
                    "workflow_insertion": "timing signoff",
                    "proof_artifact": "Replay benchmark on ECO history",
                },
            }
        )

        assert score["pass"] is True
        assert "Economic Buyer: VP of Silicon Engineering" in captured["prompt"]
        assert "Workflow Insertion: timing signoff" in captured["prompt"]
        assert "workflow_insertion_clarity" in captured["prompt"]

    @pytest.mark.asyncio
    async def test_evaluate_residual_proposals_accepts_legacy_ready_for_screening(
        self,
        mock_llm_client,
        mock_graph_db,
        monkeypatch,
    ):
        scheduler = ReactorScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        async def fake_get_nodes_by_property(node_type, key, value):
            if value == "ready_for_screening":
                return [
                    {
                        "id": "residual_legacy",
                        "label": "Timing Closure Copilot: Assistant",
                        "properties": {
                            "title": "Timing Closure Copilot",
                            "description": "Assistant for signoff ECOs.",
                        },
                    }
                ]
            return []

        async def fake_score(node, budget=None):
            return {"pass": True, "confidence": 0.82}

        mock_graph_db.get_nodes_by_property.side_effect = fake_get_nodes_by_property
        monkeypatch.setattr(scheduler, "_score_proposal", fake_score)

        approved = await scheduler._evaluate_residual_proposals()

        assert len(approved) == 1
        queried_statuses = [call.args[2] for call in mock_graph_db.get_nodes_by_property.await_args_list]
        assert "pending_innovation" in queried_statuses
        assert "ready_for_screening" in queried_statuses
        mock_graph_db.set_node_property.assert_any_await(
            "residual_legacy", "status", "pending_business"
        )
