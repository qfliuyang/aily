from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aily.sessions.innolaval_scheduler import (
    InnovationMethod,
    InnolavalScheduler,
    MethodResult,
    NozzleConfig,
)
from aily.sessions.models import Proposal


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


class TestInnolavalScheduler:
    def test_init_defaults(self, mock_llm_client, mock_graph_db):
        scheduler = InnolavalScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
        )

        assert scheduler.mind_name == "innolaval"
        assert scheduler.schedule_hour == 8
        assert scheduler.schedule_minute == 0

    @pytest.mark.asyncio
    async def test_run_session_stores_current_proposals(
        self,
        mock_llm_client,
        mock_graph_db,
        mock_obsidian_writer,
        monkeypatch,
    ):
        proposal = Proposal(
            mind_name="innolaval",
            title="Faster Context Routing",
            content="Route context by task shape before retrieval.",
            summary="Route context by task shape before retrieval.",
            confidence=0.91,
        )
        scheduler = InnolavalScheduler(
            llm_client=mock_llm_client,
            graph_db=mock_graph_db,
            obsidian_writer=mock_obsidian_writer,
            nozzle_config=NozzleConfig(enabled_methods={InnovationMethod.TRIZ}),
        )

        async def fake_run_method(method, context):
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
