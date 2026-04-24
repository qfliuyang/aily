from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from aily.sessions.gstack_agent import ActionResult, GStackPanelResult, GStackSession
from aily.sessions.entrepreneur_scheduler import EntrepreneurScheduler
from aily.sessions.models import Proposal, ProposalStatus


@pytest.fixture
def mock_graph_db():
    db = MagicMock()
    db._db = MagicMock()
    return db


@pytest.fixture
def mock_llm_client():
    return MagicMock()


@pytest.fixture
def mock_obsidian_writer():
    writer = AsyncMock()
    writer.write_note = AsyncMock(return_value="Aily/Proposals/Business/test.md")
    return writer


@pytest.fixture
def mock_reactor_scheduler():
    scheduler = MagicMock()
    scheduler._current_session_proposals = [
        Proposal(
            mind_name="reactor",
            title="Latency Reduction",
            content="Build a thinner serving path.",
            summary="Reduce serving latency with a thinner path.",
            confidence=0.84,
        )
    ]
    return scheduler


class TestEntrepreneurScheduler:
    def test_init_defaults(self, mock_llm_client, mock_graph_db):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        assert scheduler.mind_name == "entrepreneur"
        assert scheduler.schedule_hour == 9
        assert scheduler.schedule_minute == 0
        assert scheduler.proposal_min_confidence == 0.7

    def test_get_innovation_proposals_uses_current_schema(
        self,
        mock_llm_client,
        mock_graph_db,
        mock_reactor_scheduler,
    ):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            innovation_scheduler=mock_reactor_scheduler,
        )

        proposals = scheduler._get_innovation_proposals()

        assert proposals == [
            {
                "title": "Latency Reduction",
                "description": "Reduce serving latency with a thinner path.",
                "confidence": 0.84,
            }
        ]

    @pytest.mark.asyncio
    async def test_deliver_proposals_writes_current_content_field(
        self,
        mock_llm_client,
        mock_graph_db,
        mock_obsidian_writer,
    ):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            obsidian_writer=mock_obsidian_writer,
        )
        proposal = Proposal(
            mind_name="entrepreneur",
            title="AI Workflow Audit",
            content="Run a structured audit of the onboarding funnel.",
            summary="Audit the onboarding funnel.",
            confidence=0.9,
        )

        await scheduler._deliver_proposals([proposal])

        mock_obsidian_writer.write_note.assert_awaited_once()
        assert proposal.status == ProposalStatus.DELIVERED

    def test_gstack_persona_prompt_uses_deeptech_framing(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        prompt = scheduler.gstack_agent._persona_system_prompt(
            "engineer",
            {"solution": "EDA timing signoff acceleration for semiconductor verification"},
        )

        assert "signoff trust" in prompt
        assert "pilotability" in prompt

    def test_build_hypothesis_from_node_prefers_structured_properties(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        hypothesis = scheduler._build_hypothesis_from_node(
            {
                "id": "residual_1234",
                "label": "Loose Label: vague text",
                "properties": {
                    "title": "Timing Closure Copilot",
                    "hypothesis": "A timing closure copilot can reduce ECO turnaround.",
                    "problem": "Timing ECO loops are slow and manual.",
                    "solution": "Insert a ranked-fix assistant into the ECO workflow.",
                    "target_user": "Physical design engineers",
                    "economic_buyer": "VP of Silicon Engineering",
                    "proof_artifact": "Benchmark delta on historical ECO runs",
                },
            }
        )

        assert hypothesis["title"] == "Timing Closure Copilot"
        assert hypothesis["problem"] == "Timing ECO loops are slow and manual."
        assert hypothesis["target_user"] == "Physical design engineers"
        assert hypothesis["economic_buyer"] == "VP of Silicon Engineering"
        assert hypothesis["proof_artifact"] == "Benchmark delta on historical ECO runs"

    def test_init_accepts_dedicated_gstack_and_guru_clients(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        gstack_client = MagicMock()
        guru_client = MagicMock()

        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            gstack_llm_client=gstack_client,
            guru_llm_client=guru_client,
            graph_db=mock_graph_db,
        )

        assert scheduler.gstack_agent.llm_client is gstack_client
        assert scheduler.gstack_agent.guru_llm_client is guru_client

    @pytest.mark.asyncio
    async def test_run_session_passes_structured_context_to_gstack_panel(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )
        scheduler._query_pending_business_proposals = AsyncMock(
            return_value=[
                {
                    "id": "residual_1234",
                    "label": "Timing Closure Copilot: generic fallback",
                    "properties": {
                        "status": "pending_business",
                        "title": "Timing Closure Copilot",
                        "hypothesis": "A timing closure copilot can reduce ECO turnaround.",
                        "problem": "Timing ECO loops are slow and manual.",
                        "solution": "Insert a ranked-fix assistant into the ECO workflow.",
                        "target_user": "Physical design engineers",
                        "economic_buyer": "VP of Silicon Engineering",
                        "current_workaround": "Manual triage in signoff tools",
                        "workflow_insertion": "timing signoff",
                        "proof_artifact": "Replay benchmark on past ECO runs",
                    },
                }
            ]
        )
        scheduler._get_innovation_proposals = MagicMock(return_value=[])
        scheduler._process_gstack_panel_verdict = AsyncMock(return_value=None)
        scheduler._write_proposal_note = AsyncMock()
        scheduler.gstack_agent.evaluate_panel = AsyncMock(
            return_value=GStackPanelResult(
                sessions=[
                    GStackSession(
                        session_id="g1",
                        hypothesis="A timing closure copilot can reduce ECO turnaround.",
                        problem="Timing ECO loops are slow and manual.",
                        solution="Insert a ranked-fix assistant into the ECO workflow.",
                        target_user="Physical design engineers",
                    )
                ]
            )
        )

        await scheduler._run_session()

        call = scheduler.gstack_agent.evaluate_panel.await_args
        context = call.kwargs["context"]
        assert context["hypothesis"] == "A timing closure copilot can reduce ECO turnaround."
        assert context["problem"] == "Timing ECO loops are slow and manual."
        assert context["solution"] == "Insert a ranked-fix assistant into the ECO workflow."
        assert context["target_user"] == "Physical design engineers"
        assert context["economic_buyer"] == "VP of Silicon Engineering"
        assert context["current_workaround"] == "Manual triage in signoff tools"
        assert context["workflow_insertion"] == "timing signoff"
        assert context["proof_artifact"] == "Replay benchmark on past ECO runs"

    @pytest.mark.asyncio
    async def test_query_pending_business_proposals_includes_reactor_queue(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        async def fake_get_nodes_by_property(node_type, key, value):
            if node_type == "residual_proposal":
                return [{"id": "residual_1", "type": "residual_proposal", "properties": {"status": "pending_business"}}]
            if node_type == "reactor_proposal":
                return [{"id": "reactor_1", "type": "reactor_proposal", "properties": {"status": "pending_business"}}]
            return []

        mock_graph_db.get_nodes_by_property.side_effect = fake_get_nodes_by_property

        nodes = await scheduler._query_pending_business_proposals()

        assert {node["id"] for node in nodes} == {"residual_1", "reactor_1"}

    @pytest.mark.asyncio
    async def test_guru_prompt_requests_hypothesis_and_simulation_driven_plans(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        mock_llm_client.chat_json = AsyncMock(
            return_value={
                "executive_take": "Promising if benchmark delta is real.",
                "decision_posture": "validate_then_build",
                "fact_base": [],
                "business_plan": {},
                "development_plan": {},
                "briefing_notes": {},
            }
        )
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        await scheduler.gstack_agent.generate_guru_plan(
            {
                "title": "Timing Closure Copilot",
                "hypothesis": "A timing closure copilot can reduce ECO turnaround.",
                "problem": "Timing ECO loops are slow and manual.",
                "solution": "Insert a ranked-fix assistant into signoff.",
                "target_user": "Physical design engineers",
            },
            GStackPanelResult(
                sessions=[
                    GStackSession(
                        session_id="g1",
                        hypothesis="A timing closure copilot can reduce ECO turnaround.",
                        problem="Timing ECO loops are slow and manual.",
                        solution="Insert a ranked-fix assistant into signoff.",
                        target_user="Physical design engineers",
                        verdict="needs_more_validation",
                        confidence=0.64,
                    )
                ],
                final_verdict="needs_more_validation",
                final_confidence=0.64,
                synthesis_reasoning="Needs benchmark proof.",
            ),
        )

        messages = mock_llm_client.chat_json.await_args.kwargs["messages"]
        assert "hypothesis-driven, fact-based logical insight" in messages[0]["content"]
        assert "simulation-driven, constraint-based, feedback-evolving" in messages[1]["content"]
        assert "Every idea deserves a serious salvage" in messages[0]["content"]

    def test_gstack_reports_keep_full_hypothesis_title(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )
        hypothesis = (
            "This business hypothesis should remain fully intact without artificial truncation "
            "because shortening it changes the decision context"
        )
        session = GStackSession(
            session_id="g1",
            hypothesis=hypothesis,
            problem="Problem",
            solution="Solution",
            target_user="Target user",
            verdict="needs_more_validation",
            confidence=0.61,
        )
        panel = GStackPanelResult(
            sessions=[session],
            final_verdict="needs_more_validation",
            final_confidence=0.61,
            synthesis_reasoning="Need more evidence.",
        )

        session_report = scheduler.gstack_agent.get_session_report(session)
        panel_report = scheduler.gstack_agent.get_panel_report(panel)

        assert f"# GStack Evaluation: {hypothesis}" in session_report
        assert f"# GStack Panel Evaluation: {hypothesis}" in panel_report

    @pytest.mark.asyncio
    async def test_build_guru_appendix_markdown_handles_nested_output(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        mock_llm_client.chat_json = AsyncMock(
            return_value={
                "executive_take": "The idea is denied today but salvageable with benchmark proof.",
                "decision_posture": "reframe",
                "fact_base": [
                    {
                        "type": "fact",
                        "statement": "Current flow is manual.",
                        "implication": "Automation leverage exists.",
                    }
                ],
                "business_plan": {
                    "core_thesis": "Win by reducing ECO turnaround.",
                    "validation_program": [
                        {
                            "step": "Run one replay benchmark",
                            "artifact": "before/after ECO report",
                        }
                    ],
                    "decision_gates": ["Show >20% faster turnaround"],
                    "salvage_or_acceleration": ["Narrow to one signoff workflow"],
                },
                "development_plan": {
                    "technical_thesis": "Start as an offline recommendation engine.",
                    "simulation_program": ["Replay 50 historical ECO cases"],
                    "constraints": ["No change to signoff golden flow"],
                    "feedback_loops": ["Review false positives weekly"],
                    "milestones": ["Produce ranked fixes report"],
                    "team_and_dependencies": ["1 PD engineer, 1 ML engineer"],
                    "kill_criteria": ["No measurable QoR or runtime gain"],
                },
                "briefing_notes": {
                    "ceo": "Sell the pilot around schedule protection.",
                    "cto": "Keep the first version offline and benchmarked.",
                },
            }
        )
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        markdown = await scheduler._build_guru_appendix_markdown(
            proposal_node={
                "id": "residual_1234",
                "label": "Timing Closure Copilot: fallback",
                "properties": {
                    "title": "Timing Closure Copilot",
                    "hypothesis": "A timing closure copilot can reduce ECO turnaround.",
                    "problem": "Timing ECO loops are slow and manual.",
                    "solution": "Insert a ranked-fix assistant into signoff.",
                    "target_user": "Physical design engineers",
                },
            },
            panel_or_session=GStackPanelResult(
                sessions=[
                    GStackSession(
                        session_id="g1",
                        hypothesis="A timing closure copilot can reduce ECO turnaround.",
                        problem="Timing ECO loops are slow and manual.",
                        solution="Insert a ranked-fix assistant into signoff.",
                        target_user="Physical design engineers",
                        verdict="kill_it",
                        confidence=0.42,
                    )
                ],
                final_verdict="kill_it",
                final_confidence=0.42,
                synthesis_reasoning="Insufficient evidence today.",
            ),
            innovation_proposals=[],
        )

        assert markdown is not None
        assert "## Hypothesis-Driven Business Plan" in markdown
        assert "## Simulation-Driven Development Plan" in markdown
        assert "before/after ECO report" in markdown

    @pytest.mark.asyncio
    async def test_write_proposal_note_appends_guru_and_preserves_full_text(
        self,
        mock_llm_client,
        mock_graph_db,
        mock_obsidian_writer,
    ):
        long_title = (
            "Constraint Verification Platform Pre-Physical-Design Constraint Quality Assurance "
            "Without Misleading Truncated Titles"
        )
        long_output = (
            "This action output contains the complete evaluation details and must not be cut after "
            "an arbitrary character boundary because the omitted tail changes the conclusion."
        )
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            obsidian_writer=mock_obsidian_writer,
        )

        await scheduler._write_proposal_note(
            proposal_node={
                "id": "residual_5678",
                "label": f"{long_title}: fallback",
                "properties": {
                    "title": long_title,
                    "hypothesis": "A complete-title plan can avoid misleading operators.",
                    "problem": "Truncated notes hide material context.",
                    "solution": "Preserve full titles and outputs in the plan.",
                    "target_user": "CEO and CTO reviewers",
                },
            },
            panel_or_session=GStackPanelResult(
                sessions=[
                    GStackSession(
                        session_id="g2",
                        hypothesis="A complete-title plan can avoid misleading operators.",
                        problem="Truncated notes hide material context.",
                        solution="Preserve full titles and outputs in the plan.",
                        target_user="CEO and CTO reviewers",
                        verdict="needs_more_validation",
                        confidence=0.62,
                        actions=[
                            ActionResult(
                                action="validate_problem",
                                status="success",
                                output=long_output,
                            )
                        ],
                    )
                ],
                final_verdict="needs_more_validation",
                final_confidence=0.62,
                synthesis_reasoning="Needs more validation.",
            ),
            approved=False,
            guru_appendix_markdown="# Guru Appendix: Full\n\nAppendix body",
        )

        write_call = mock_obsidian_writer.write_note.await_args
        assert write_call.kwargs["title"] == f"denied-{long_title}"
        assert write_call.kwargs["source_url"] == "aily://entrepreneur"
        assert f"# {long_title}" in write_call.kwargs["markdown"]
        assert long_output in write_call.kwargs["markdown"]
        assert "# Guru Appendix: Full" in write_call.kwargs["markdown"]
        assert "[[appendix-" not in write_call.kwargs["markdown"]

    @pytest.mark.asyncio
    async def test_evaluate_business_case_falls_back_after_panel_timeout(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            innovation_timeout_minutes=1,
            use_gstack_panel=True,
        )
        scheduler.gstack_agent.evaluate_panel = AsyncMock(side_effect=asyncio.TimeoutError())
        fallback_session = GStackSession(
            session_id="gstack_fallback",
            hypothesis="A timing closure copilot can reduce ECO turnaround.",
            problem="Timing ECO loops are slow and manual.",
            solution="Insert a ranked-fix assistant into the ECO workflow.",
            target_user="Physical design engineers",
            persona="general",
            verdict="needs_more_validation",
            confidence=0.44,
        )
        scheduler.gstack_agent.evaluate = AsyncMock(return_value=fallback_session)

        result = await scheduler._evaluate_business_case(
            {
                "title": "Timing Closure Copilot",
                "hypothesis": fallback_session.hypothesis,
                "problem": fallback_session.problem,
                "solution": fallback_session.solution,
                "target_user": fallback_session.target_user,
            },
            {"proposal_node_id": "residual_1234"},
        )

        assert isinstance(result, GStackPanelResult)
        assert result.final_verdict == "needs_more_validation"
        assert result.sessions[0].session_id == "gstack_fallback"
        assert "fell back" in result.synthesis_reasoning
        scheduler.gstack_agent.evaluate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_business_case_creates_timeout_session_when_all_paths_timeout(
        self,
        mock_llm_client,
        mock_graph_db,
    ):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            innovation_timeout_minutes=1,
            use_gstack_panel=False,
        )
        scheduler.gstack_agent.evaluate = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await scheduler._evaluate_business_case(
            {
                "title": "Timing Closure Copilot",
                "hypothesis": "A timing closure copilot can reduce ECO turnaround.",
                "problem": "Timing ECO loops are slow and manual.",
                "solution": "Insert a ranked-fix assistant into the ECO workflow.",
                "target_user": "Physical design engineers",
            },
            {"proposal_node_id": "residual_1234"},
        )

        assert isinstance(result, GStackSession)
        assert result.verdict == "needs_more_validation"
        assert result.actions[0].action == "evaluation_timeout"
