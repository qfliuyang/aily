from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

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
def mock_innolaval_scheduler():
    scheduler = MagicMock()
    scheduler._current_session_proposals = [
        Proposal(
            mind_name="innolaval",
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
        mock_innolaval_scheduler,
    ):
        scheduler = EntrepreneurScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            innovation_scheduler=mock_innolaval_scheduler,
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
