from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aily.dikiwi.agents.context import AgentContext
from aily.dikiwi.agents.residual_agent import ResidualAgent


@pytest.mark.asyncio
async def test_persist_proposals_stores_structured_fields():
    graph_db = AsyncMock()
    ctx = AgentContext(
        pipeline_id="pipe_1",
        correlation_id="corr_1",
        drop=MagicMock(),
        graph_db=graph_db,
    )
    agent = ResidualAgent()

    await agent._persist_proposals(
        proposals=[
            {
                "title": "Timing Closure Copilot",
                "description": "Insert a ranked-fix assistant into signoff.",
                "problem": "Timing ECO loops are slow and manual.",
                "target_user": "Physical design engineers",
                "economic_buyer": "VP of Silicon Engineering",
                "proof_artifact": "Replay benchmark on ECO history",
                "recommended_next_validation": "Run a pilot on one signoff team",
            }
        ],
        report_note_id="07-Proposal/report.md",
        ctx=ctx,
    )

    assert graph_db.insert_node.await_count == 1
    persisted_keys = [call.args[1] for call in graph_db.set_node_property.await_args_list]
    assert "status" in persisted_keys
    assert "validation_attempts" in persisted_keys
    assert "title" in persisted_keys
    assert "problem" in persisted_keys
    assert "target_user" in persisted_keys
    assert "economic_buyer" in persisted_keys
    assert "proof_artifact" in persisted_keys
