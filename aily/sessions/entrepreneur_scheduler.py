"""Entrepreneur Mind - Agentic GStack evaluation through execution.

Runs daily at 9am.
Acts like Garry Tan - actually pulls up code, runs tests, checks metrics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from aily.sessions.base import BaseMindScheduler
from aily.sessions.models import Proposal, ProposalType, ProposalStatus
from aily.sessions.gstack_agent import GStackAgent

logger = logging.getLogger(__name__)


class EntrepreneurScheduler(BaseMindScheduler):
    """Entrepreneur Mind that actually takes actions - evaluates by doing."""

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
        tool_executor: Any | None = None,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            mind_name="entrepreneur",
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

        # Initialize GStack Agent - actually takes actions
        self.gstack_agent = GStackAgent(
            llm_client=llm_client,
            tool_executor=tool_executor,
            obsidian_writer=obsidian_writer,
        )

    async def _run_session(self) -> dict[str, Any]:
        """Execute GStack agentic evaluation - actually takes actions."""
        logger.info("[Entrepreneur] Starting GStack evaluation with real actions")

        # Step 1: Gather knowledge and innovation proposals
        knowledge = await self._query_recent_knowledge()
        innovation_proposals = self._get_innovation_proposals()

        logger.info(
            "[Entrepreneur] Evaluating %d knowledge items, %d innovation proposals",
            len(knowledge), len(innovation_proposals),
        )

        # Step 2: Run GStack Agent - it actually does things
        # Build hypothesis from knowledge and innovation proposals
        hypothesis = self._build_hypothesis(knowledge, innovation_proposals)

        context = {
            "knowledge": knowledge,
            "innovation_proposals": innovation_proposals,
            "session_type": "entrepreneur",
        }

        session = await self.gstack_agent.evaluate(
            hypothesis=hypothesis["hypothesis"],
            problem=hypothesis["problem"],
            solution=hypothesis["solution"],
            target_user=hypothesis["target_user"],
            context=context,
        )

        # Step 3: Generate proposal from session results
        proposals: list[Proposal] = []
        confidence = session.confidence

        if confidence >= self.proposal_min_confidence:
            proposal = Proposal(
                id=f"biz_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                mind_name="entrepreneur",
                title=hypothesis["title"],
                content=session.hypothesis,
                summary=session.hypothesis[:200],
                confidence=confidence,
                proposal_type=ProposalType.BUSINESS,
                status=ProposalStatus.PENDING,
                priority="high" if confidence >= 0.85 else "medium",
                framework_used="GStack",
                metadata={
                    "problem": session.problem,
                    "solution": session.solution,
                    "target_user": session.target_user,
                    "verdict": session.verdict,
                    "risks": session.blockers,
                    "opportunities": session.opportunities,
                    "actions_taken": len(session.actions),
                    "key_findings": session.key_findings[:10],
                },
            )
            proposals.append(proposal)
            await self._deliver_proposals(proposals)

        # Step 4: Write session report to Obsidian
        if self.obsidian_writer:
            try:
                report = self.gstack_agent.get_session_report(session)
                await self.obsidian_writer.write_note(
                    title=f"GStack Evaluation {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                    markdown=report,
                    source_url="aily://entrepreneur_session",
                )
            except Exception as e:
                logger.warning("[Entrepreneur] Failed to write session report: %s", e)

        return {
            "proposals_generated": len(proposals),
            "actions_taken": len(session.actions),
            "confidence": confidence,
            "verdict": session.verdict,
        }

    def _build_hypothesis(self, knowledge: list[dict], innovation_proposals: list[dict]) -> dict:
        """Build business hypothesis from knowledge and innovation proposals."""
        # If we have innovation proposals, use the best one as foundation
        if innovation_proposals:
            best = max(innovation_proposals, key=lambda x: x.get("confidence", 0))
            return {
                "title": best.get("title", "Business Opportunity"),
                "hypothesis": f"Building {best.get('title', 'this product')} will solve a real problem",
                "problem": best.get("description", "Problem not clearly defined"),
                "solution": best.get("description", "Solution not clearly defined"),
                "target_user": "Users who face this problem",
            }

        # Otherwise synthesize from knowledge
        if knowledge:
            topics = [k.get("content", "") for k in knowledge[:3]]
            combined = " ".join(topics)
            return {
                "title": "Knowledge-Based Opportunity",
                "hypothesis": f"Exploring opportunity related to: {combined[:100]}...",
                "problem": "Problem to be identified through validation",
                "solution": "Solution to be determined based on problem validation",
                "target_user": "Target users to be identified",
            }

        # Fallback
        return {
            "title": "Aily Self-Evaluation",
            "hypothesis": "Aily (AI knowledge management) should expand its business evaluation capabilities",
            "problem": "Current evaluation is conversation-based, not execution-based",
            "solution": "Build GStack agent that actually runs tests, checks code, validates assumptions",
            "target_user": "AI product teams, startup builders",
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
            logger.exception("[Entrepreneur] Failed to query knowledge: %s", e)
            return []

    def _get_innovation_proposals(self) -> list[dict]:
        """Get proposals from Innovation Mind."""
        if not self.innovation_scheduler:
            return []
        try:
            proposals = getattr(self.innovation_scheduler, '_current_session_proposals', [])
            return [
                {
                    "title": p.title,
                    "description": p.summary or p.content,
                    "confidence": p.confidence,
                }
                for p in proposals
            ]
        except Exception:
            return []

    async def _deliver_proposals(self, proposals: list[Proposal]) -> None:
        """Deliver proposals."""
        for proposal in proposals:
            if self.obsidian_writer:
                try:
                    await self.obsidian_writer.write_note(
                        title=f"Business: {proposal.title}",
                        markdown=f"# {proposal.title}\n\n{proposal.content}",
                        source_url="aily://entrepreneur",
                    )
                    proposal.status = ProposalStatus.DELIVERED
                except Exception as e:
                    logger.warning("[Entrepreneur] Obsidian write failed: %s", e)
