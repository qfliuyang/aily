"""Entrepreneur Mind - Agentic GStack evaluation through execution.

Runs daily at 9am.
Acts like Garry Tan - actually pulls up code, runs tests, checks metrics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from aily.sessions.base import BaseMindScheduler
from aily.sessions.models import Proposal, ProposalType, ProposalStatus, ProposalStage
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
            graph_db=graph_db,
        )

    async def _run_session(self) -> dict[str, Any]:
        """Execute GStack agentic evaluation - actually takes actions."""
        logger.info("[Entrepreneur] Starting GStack evaluation with real actions")

        # Step 1: Gather pending business proposals from Residual/Reactor
        pending_proposals = await self._query_pending_business_proposals()
        innovation_proposals = self._get_innovation_proposals()

        logger.info(
            "[Entrepreneur] Evaluating %d pending business proposals",
            len(pending_proposals),
        )

        approved_proposals: list[Proposal] = []
        total_actions = 0

        # Step 2: Evaluate each pending proposal with GStack
        for proposal_node in pending_proposals[: self.proposal_max_per_session]:
            hypothesis = self._build_hypothesis_from_node(proposal_node)
            context = {
                "knowledge": [],
                "innovation_proposals": innovation_proposals,
                "session_type": "entrepreneur",
                "proposal_node_id": proposal_node["id"],
            }

            session = await self.gstack_agent.evaluate(
                hypothesis=hypothesis["hypothesis"],
                problem=hypothesis["problem"],
                solution=hypothesis["solution"],
                target_user=hypothesis["target_user"],
                context=context,
            )
            total_actions += len(session.actions)

            # Step 3: Process verdict and update GraphDB
            entrepreneur_proposal = await self._process_gstack_verdict(
                proposal_node, session
            )
            if entrepreneur_proposal:
                approved_proposals.append(entrepreneur_proposal)

        if approved_proposals:
            await self._deliver_proposals(approved_proposals)

        # Step 4: Write session summary report to Obsidian
        if self.obsidian_writer:
            try:
                summary_lines = [
                    f"# Entrepreneur Session {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                    "",
                    f"Evaluated: {len(pending_proposals)} proposals",
                    f"Approved: {len(approved_proposals)} proposals",
                    "",
                    "## Approved",
                ]
                for p in approved_proposals:
                    summary_lines.append(f"- **{p.title}** (confidence: {p.confidence:.0%})")
                summary_lines.append("")
                summary_lines.append("## Rejected")
                for node in pending_proposals:
                    props = node.get("properties", {})
                    if props.get("status") in ("rejected_business", "rejected_innovation"):
                        summary_lines.append(f"- {node['label'][:80]}... — {props.get('rejection_reason', '')}")

                await self.obsidian_writer.write_note(
                    title=f"Entrepreneur Session {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                    markdown="\n".join(summary_lines),
                    source_url="aily://entrepreneur_session",
                )
            except Exception as e:
                logger.warning("[Entrepreneur] Failed to write session report: %s", e)

        return {
            "proposals_generated": len(approved_proposals),
            "actions_taken": total_actions,
            "evaluated": len(pending_proposals),
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
                "SELECT id, label, source, created_at FROM nodes WHERE type IN (?, ?) AND created_at > ? ORDER BY created_at DESC",
                ("atomic_note", "residual_proposal", since.isoformat()),
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

    async def _query_pending_business_proposals(self) -> list[dict]:
        """Query Residual proposals waiting for business evaluation."""
        if not self.graph_db:
            return []
        try:
            nodes = await self.graph_db.get_nodes_by_property(
                "residual_proposal", "status", "pending_business"
            )
            return nodes
        except Exception as e:
            logger.exception("[Entrepreneur] Failed to query pending business proposals: %s", e)
            return []

    def _build_hypothesis_from_node(self, node: dict) -> dict:
        """Build a GStack hypothesis from a Residual proposal node."""
        label = node.get("label", "")
        title = label.split(":")[0] if ":" in label else label
        description = label[len(title) + 1 :].strip() if ":" in label else label
        return {
            "title": title or "Business Opportunity",
            "hypothesis": f"Building {title} will solve a real problem",
            "problem": description or "Problem not clearly defined",
            "solution": description or "Solution not clearly defined",
            "target_user": "Users who face this problem",
        }

    async def _process_gstack_verdict(
        self, proposal_node: dict, session: "GStackSession"
    ) -> Proposal | None:
        """Update proposal status based on GStack verdict and return Proposal if approved."""
        if not self.graph_db:
            return None

        node_id = proposal_node["id"]
        verdict = session.verdict
        confidence = session.confidence
        props = proposal_node.get("properties", {})

        if verdict == "build_it" and confidence >= self.proposal_min_confidence:
            await self.graph_db.set_node_property(node_id, "status", "incubating")
            await self.graph_db.set_node_property(node_id, "business_score", confidence)
            await self._create_incubation_task(proposal_node, session)
            return Proposal(
                id=f"biz_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{node_id[-4:]}",
                mind_name="entrepreneur",
                title=self._build_hypothesis_from_node(proposal_node)["title"],
                content=session.hypothesis,
                summary=session.hypothesis[:200],
                confidence=confidence,
                proposal_type=ProposalType.BUSINESS,
                status=ProposalStatus.PENDING,
                priority="high" if confidence >= 0.85 else "medium",
                business_score=confidence,
                stage=ProposalStage.INCUBATING,
                source_knowledge_ids=[node_id],
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

        if verdict == "kill_it":
            reason = session.blockers[-1] if session.blockers else "killed_by_gstack"
            await self.graph_db.set_node_property(node_id, "status", "rejected_business")
            await self.graph_db.set_node_property(node_id, "rejection_reason", reason)
            await self.graph_db.set_node_property(node_id, "business_score", confidence)
            await self._write_rejection_feedback(proposal_node, reason)
            return None

        # needs_more_validation or pivot
        attempts = int(props.get("validation_attempts", 0)) + 1
        if attempts >= 2:
            reason = "max_validation_attempts_reached"
            await self.graph_db.set_node_property(node_id, "status", "rejected_business")
            await self.graph_db.set_node_property(node_id, "rejection_reason", reason)
            await self.graph_db.set_node_property(node_id, "business_score", confidence)
            await self._write_rejection_feedback(proposal_node, reason)
        else:
            await self.graph_db.set_node_property(node_id, "validation_attempts", attempts)
            await self.graph_db.set_node_property(node_id, "business_score", confidence)

        return None

    async def _write_rejection_feedback(self, proposal_node: dict, reason: str) -> None:
        """Append rejection reason to the Residual Feedback Index for future learning."""
        if not self.graph_db:
            return
        try:
            label = proposal_node.get("label", "")[:120]
            await self.graph_db.add_residual_feedback(label, reason)
            logger.info("[Entrepreneur] Wrote rejection feedback for %s", proposal_node.get("id"))
        except Exception as e:
            logger.warning("[Entrepreneur] Failed to write rejection feedback: %s", e)

    async def _create_incubation_task(self, proposal_node: dict, session: "GStackSession") -> None:
        """Create an incubation task note for approved proposals."""
        if not self.obsidian_writer:
            return
        try:
            title = self._build_hypothesis_from_node(proposal_node)["title"]
            lines = [
                f"# Incubation Task: {title}",
                "",
                f"**Verdict:** {session.verdict}",
                f"**Confidence:** {session.confidence:.0%}",
                "",
                "## Next Steps",
            ]
            for finding in session.key_findings[:5]:
                lines.append(f"- [ ] {finding}")
            lines.append("")
            lines.append("## Blockers to Resolve")
            for blocker in session.blockers:
                lines.append(f"- [ ] {blocker}")

            await self.obsidian_writer.write_note(
                title=f"Incubation: {title}",
                markdown="\n".join(lines),
                source_url="aily://entrepreneur_incubation",
            )
        except Exception as e:
            logger.warning("[Entrepreneur] Failed to create incubation task: %s", e)
