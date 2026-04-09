"""Innovation Mind - ReAct-powered TRIZ innovation.

Runs daily at 8am using ReAct pattern:
- Thought: "What contradictions exist in recent knowledge?"
- Action: Search knowledge, analyze with TRIZ
- Observation: "Found contradiction X"
- Repeat until inventive solution emerges
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from aily.sessions.base import BaseMindScheduler
from aily.sessions.models import Proposal, ProposalType, ProposalStatus
from aily.sessions.triz_react_mind import TrizReactMind

logger = logging.getLogger(__name__)


class InnovationReactScheduler(BaseMindScheduler):
    """Innovation Mind with ReAct reasoning - actually thinks through TRIZ."""

    def __init__(
        self,
        llm_client: Any,
        graph_db: Any,
        obsidian_writer: Any | None = None,
        feishu_pusher: Any | None = None,
        schedule_hour: int = 8,
        schedule_minute: int = 0,
        circuit_breaker_threshold: int = 3,
        enabled: bool = True,
        proposal_min_confidence: float = 0.7,
        proposal_max_per_session: int = 10,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            mind_name="innovation_react",
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
            circuit_breaker_threshold=circuit_breaker_threshold,
            enabled=enabled,
        )
        self.graph_db = graph_db
        self.obsidian_writer = obsidian_writer
        self.feishu_pusher = feishu_pusher
        self.proposal_min_confidence = proposal_min_confidence
        self.proposal_max_per_session = proposal_max_per_session

        # Initialize ReAct mind
        self.react_mind = TrizReactMind(
            llm_client=llm_client,
            min_confidence=proposal_min_confidence,
        )

        self._current_session_proposals: list[Proposal] = []

    async def _run_session(self) -> dict[str, Any]:
        """Execute ReAct-powered innovation session."""
        logger.info("[Innovation React] Starting ReAct innovation session")

        # Step 1: Gather knowledge
        knowledge = await self._query_recent_knowledge()
        if not knowledge:
            logger.info("[Innovation React] No knowledge to analyze")
            return {"proposals_generated": 0, "reason": "no_knowledge"}

        logger.info("[Innovation React] Running ReAct on %d knowledge items", len(knowledge))

        # Step 2: Run ReAct session
        context = {
            "knowledge": knowledge,
            "session_type": "innovation",
            "start_time": datetime.now(timezone.utc).isoformat(),
        }

        react_session = await self.react_mind.run_react_session(context)

        logger.info(
            "[Innovation React] ReAct complete: %d thoughts, %d actions",
            len(react_session.thoughts),
            len(react_session.actions),
        )

        # Step 3: Generate final proposal from ReAct reasoning
        proposal_data = await self.react_mind.generate_final_proposal(react_session)

        # Step 4: Create proposal if confident enough
        proposals = []
        confidence = proposal_data.get("confidence", 0.0)

        if confidence >= self.proposal_min_confidence:
            proposal = Proposal(
                id=f"innov_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                title=proposal_data.get("title", "Innovation Proposal"),
                description=proposal_data.get("inventive_solution", ""),
                problem_statement=proposal_data.get("problem_statement", ""),
                solution=proposal_data.get("how_it_works", ""),
                confidence=confidence,
                proposal_type=ProposalType.INNOVATION,
                status=ProposalStatus.GENERATED,
                triz_principles=proposal_data.get("triz_principles_applied", []),
                contradiction=proposal_data.get("contradiction", {}),
                novelty_score=proposal_data.get("novelty_score", 0.0),
                metadata={
                    "react_transcript": react_session.to_dict(),
                    "implementation_complexity": proposal_data.get("implementation_complexity", "medium"),
                },
            )
            proposals.append(proposal)
            self._current_session_proposals = proposals

            # Deliver
            await self._deliver_proposals(proposals)

        # Step 5: Write ReAct transcript to Obsidian
        if self.obsidian_writer:
            try:
                transcript = self.react_mind.get_session_transcript(react_session)
                await self.obsidian_writer.write_note(
                    title=f"ReAct TRIZ Session {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                    markdown=transcript,
                    source_url="aily://innovation_session",
                )
            except Exception as e:
                logger.warning("[Innovation React] Failed to write transcript: %s", e)

        return {
            "proposals_generated": len(proposals),
            "proposals_delivered": len(proposals) if proposals else 0,
            "react_steps": react_session.current_step - 1,
            "confidence": confidence,
            "metadata": {
                "transcript_summary": react_session.to_dict(),
            },
        }

    async def _query_recent_knowledge(self) -> list[dict]:
        """Query knowledge from last 24h."""
        try:
            # Query atomic notes from GraphDB
            from datetime import timedelta
            since = datetime.now(timezone.utc) - timedelta(hours=24)

            nodes = []
            async with self.graph_db._db.execute(
                "SELECT id, label, source, created_at FROM nodes WHERE type = ? AND created_at > ? ORDER BY created_at DESC",
                ("atomic_note", since.isoformat()),
            ) as cursor:
                async for row in cursor:
                    nodes.append({
                        "id": row[0],
                        "content": row[1],
                        "source": row[2],
                        "created_at": row[3],
                    })

            return nodes[:50]  # Limit to recent 50

        except Exception as e:
            logger.exception("[Innovation React] Failed to query knowledge: %s", e)
            return []

    async def _deliver_proposals(self, proposals: list[Proposal]) -> None:
        """Deliver proposals to Feishu and Obsidian."""
        for proposal in proposals:
            # Write to Obsidian
            if self.obsidian_writer:
                try:
                    markdown = self._format_proposal_markdown(proposal)
                    await self.obsidian_writer.write_note(
                        title=f"Innovation: {proposal.title}",
                        markdown=markdown,
                        source_url="aily://innovation",
                    )
                except Exception as e:
                    logger.warning("[Innovation React] Obsidian write failed: %s", e)

            # Send to Feishu
            if self.feishu_pusher:
                try:
                    message = self._format_proposal_message(proposal)
                    # Send to configured open_id if available
                    # await self.feishu_pusher.send_message(open_id, message)
                except Exception as e:
                    logger.warning("[Innovation React] Feishu push failed: %s", e)

    def _format_proposal_markdown(self, proposal: Proposal) -> str:
        """Format proposal as markdown."""
        lines = [
            f"# {proposal.title}",
            "",
            f"**Confidence:** {proposal.confidence:.0%}",
            f"**Novelty:** {proposal.novelty_score:.0%}" if proposal.novelty_score else "",
            "",
            "## Problem",
            proposal.problem_statement or "N/A",
            "",
            "## Contradiction",
            f"- Improving: {proposal.contradiction.get('improving', 'N/A')}" if proposal.contradiction else "",
            f"- Worsening: {proposal.contradiction.get('worsening', 'N/A')}" if proposal.contradiction else "",
            "",
            "## Inventive Solution",
            proposal.description,
            "",
            "## How It Works",
            proposal.solution or "N/A",
            "",
            "## TRIZ Principles Applied",
        ]

        for p in proposal.triz_principles or []:
            lines.append(f"- Principle {p}")

        lines.extend([
            "",
            "## ReAct Transcript",
            "See linked session transcript for full reasoning.",
        ])

        return "\n".join(lines)

    def _format_proposal_message(self, proposal: Proposal) -> str:
        """Format proposal for Feishu."""
        return f"""💡 **Innovation Proposal: {proposal.title}**

**Confidence:** {proposal.confidence:.0%}
**Novelty:** {proposal.novelty_score:.0%}

**Problem:**
{proposal.problem_statement[:200] if proposal.problem_statement else "N/A"}...

**Solution:**
{proposal.description[:300]}...

See Obsidian for full ReAct reasoning transcript.
"""
