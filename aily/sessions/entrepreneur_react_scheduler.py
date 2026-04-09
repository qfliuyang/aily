"""Entrepreneur Mind - ReAct-powered GStack evaluation.

Runs daily at 9am using ReAct pattern.
Talks like Garry Tan - direct, concrete, pushes toward shipping.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from aily.sessions.base import BaseMindScheduler
from aily.sessions.models import Proposal, ProposalType, ProposalStatus
from aily.sessions.gstack_react_mind import GStackReactMind

logger = logging.getLogger(__name__)


class EntrepreneurReactScheduler(BaseMindScheduler):
    """Entrepreneur Mind with ReAct reasoning - evaluates like a human VC."""

    def __init__(
        self,
        llm_client: Any,
        graph_db: Any,
        innovation_scheduler: Any | None = None,
        obsidian_writer: Any | None = None,
        feishu_pusher: Any | None = None,
        schedule_hour: int = 9,
        schedule_minute: int = 0,
        circuit_breaker_threshold: int = 3,
        enabled: bool = True,
        proposal_min_confidence: float = 0.7,
        proposal_max_per_session: int = 10,
        innovation_timeout_minutes: int = 30,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            mind_name="entrepreneur_react",
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
            circuit_breaker_threshold=circuit_breaker_threshold,
            enabled=enabled,
        )
        self.graph_db = graph_db
        self.innovation_scheduler = innovation_scheduler
        self.obsidian_writer = obsidian_writer
        self.feishu_pusher = feishu_pusher
        self.proposal_min_confidence = proposal_min_confidence
        self.proposal_max_per_session = proposal_max_per_session
        self.innovation_timeout_minutes = innovation_timeout_minutes

        # Initialize ReAct mind - talks like Garry
        self.react_mind = GStackReactMind(
            llm_client=llm_client,
            min_confidence=proposal_min_confidence,
        )

    async def _run_session(self) -> dict[str, Any]:
        """Execute ReAct-powered entrepreneur session."""
        logger.info("[Entrepreneur React] Starting ReAct business evaluation")

        # Step 1: Gather knowledge
        knowledge = await self._query_recent_knowledge()
        innovation_proposals = self._get_innovation_proposals()

        logger.info(
            "[Entrepreneur React] Evaluating %d knowledge items, %d innovation proposals",
            len(knowledge), len(innovation_proposals),
        )

        # Step 2: Run ReAct session
        context = {
            "knowledge": knowledge,
            "innovation_proposals": innovation_proposals,
            "session_type": "entrepreneur",
        }

        react_session = await self.react_mind.run_react_session(context)

        # Step 3: Generate proposal
        proposal_data = await self.react_mind.generate_final_proposal(react_session)

        # Step 4: Deliver if confident
        proposals = []
        confidence = proposal_data.get("confidence", 0.0)

        if confidence >= self.proposal_min_confidence:
            proposal = Proposal(
                id=f"biz_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                title=proposal_data.get("title", "Business Evaluation"),
                description=proposal_data.get("one_liner", ""),
                problem_statement=proposal_data.get("problem", ""),
                solution=proposal_data.get("solution", ""),
                target_user=proposal_data.get("target_user", ""),
                confidence=confidence,
                proposal_type=ProposalType.BUSINESS,
                status=ProposalStatus.GENERATED,
                metadata={
                    "verdict": proposal_data.get("verdict", "unknown"),
                    "risks": proposal_data.get("risks", []),
                    "next_steps": proposal_data.get("next_steps", []),
                },
            )
            proposals.append(proposal)
            await self._deliver_proposals(proposals)

        return {
            "proposals_generated": len(proposals),
            "react_steps": react_session.current_step - 1,
            "confidence": confidence,
            "verdict": proposal_data.get("verdict", "unknown"),
        }

    async def _query_recent_knowledge(self) -> list[dict]:
        """Query knowledge from last 24h."""
        try:
            from datetime import timedelta
            since = datetime.now(timezone.utc) - timedelta(hours=24)

            nodes = []
            async with self.graph_db._db.execute(
                "SELECT id, label, source, created_at FROM nodes WHERE type = ? AND created_at > ? ORDER BY created_at DESC",
                ("atomic_note", since.isoformat()),
            ) as cursor:
                async for row in cursor:
                    nodes.append({"id": row[0], "content": row[1], "source": row[2], "created_at": row[3]})
            return nodes[:50]
        except Exception as e:
            logger.exception("[Entrepreneur React] Failed to query knowledge: %s", e)
            return []

    def _get_innovation_proposals(self) -> list[dict]:
        """Get proposals from Innovation Mind."""
        if not self.innovation_scheduler:
            return []
        try:
            proposals = getattr(self.innovation_scheduler, '_current_session_proposals', [])
            return [{"title": p.title, "description": p.description, "confidence": p.confidence} for p in proposals]
        except Exception:
            return []

    async def _deliver_proposals(self, proposals: list[Proposal]) -> None:
        """Deliver proposals."""
        for proposal in proposals:
            if self.obsidian_writer:
                try:
                    await self.obsidian_writer.write_note(
                        title=f"Business: {proposal.title}",
                        markdown=f"# {proposal.title}\n\n{proposal.description}",
                        source_url="aily://entrepreneur",
                    )
                except Exception as e:
                    logger.warning("[Entrepreneur React] Obsidian write failed: %s", e)
