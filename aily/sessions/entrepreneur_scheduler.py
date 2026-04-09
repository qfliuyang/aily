"""Entrepreneur Mind - Daily GStack-based business evaluation.

Runs daily at 9am (after Innovation Mind completes) to:
1. Query last 24h of knowledge from DIKIWI pipeline
2. Query Innovation Mind proposals from current session
3. Analyze using GStack framework (PMF, shipping velocity, growth loops)
4. Generate business proposals (max 10 per session)
5. Deliver high-confidence proposals (>=0.7) to Feishu and Obsidian

Depends on: Innovation Mind session completion (with 30 min timeout)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from aily.sessions.base import BaseMindScheduler
from aily.sessions.models import Proposal, ProposalType, ProposalStatus

if TYPE_CHECKING:
    from aily.graph.db import GraphDB
    from aily.llm.client import LLMClient
    from aily.thinking.frameworks.gstack import GStackAnalyzer
    from aily.writer.obsidian import ObsidianWriter
    from aily.push.feishu import FeishuPusher
    from aily.sessions.innovation_scheduler import InnovationScheduler

logger = logging.getLogger(__name__)


class EntrepreneurScheduler(BaseMindScheduler):
    """Scheduled Entrepreneur Mind for daily GStack business evaluation.

    Generates business proposals by applying GStack methodology
    (YC/Garry Tan startup thinking) to recent knowledge and
    Innovation Mind outputs. Evaluates PMF, shipping discipline,
    and growth loops.

    Has a dependency on Innovation Mind - waits for it to complete
    before running (with timeout fallback).
    """

    def __init__(
        self,
        llm_client: LLMClient,
        graph_db: GraphDB,
        innovation_scheduler: InnovationScheduler | None = None,
        obsidian_writer: ObsidianWriter | None = None,
        feishu_pusher: FeishuPusher | None = None,
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

        # Initialize GStack analyzer
        from aily.thinking.frameworks.gstack import GStackAnalyzer
        self.gstack_analyzer = GStackAnalyzer(llm_client)

    async def _run_session(self) -> dict[str, Any]:
        """Execute daily entrepreneur session.

        Returns:
            Dict with proposals_generated, proposals_delivered, metadata
        """
        logger.info("[Entrepreneur] Starting daily entrepreneur session")

        # Step 1: Wait for Innovation Mind (with timeout)
        innovation_ready = await self._wait_for_innovation()
        if not innovation_ready:
            logger.warning("[Entrepreneur] Innovation Mind not ready, proceeding with knowledge only")

        # Step 2: Query recent knowledge (last 24h)
        knowledge = await self._query_recent_knowledge()
        logger.info("[Entrepreneur] Analyzing %d knowledge items", len(knowledge))

        # Step 3: Get Innovation proposals if available
        innovation_proposals = []
        if self.innovation_scheduler and self.innovation_scheduler.is_session_complete():
            innovation_proposals = self.innovation_scheduler.get_current_proposals()
            logger.info("[Entrepreneur] Including %d Innovation proposals", len(innovation_proposals))

        # Step 4: Analyze using GStack
        gstack_results = await self._analyze_with_gstack(knowledge, innovation_proposals)

        # Step 5: Generate business proposals
        proposals = await self._generate_proposals(gstack_results, knowledge, innovation_proposals)

        # Step 6: Filter by confidence threshold
        qualified_proposals = [
            p for p in proposals
            if p.confidence >= self.proposal_min_confidence
        ]

        # Step 7: Limit max proposals
        if len(qualified_proposals) > self.proposal_max_per_session:
            qualified_proposals.sort(key=lambda x: x.confidence, reverse=True)
            qualified_proposals = qualified_proposals[:self.proposal_max_per_session]

        # Step 8: Deliver proposals
        delivered_count = await self._deliver_proposals(qualified_proposals)

        logger.info(
            "[Entrepreneur] Session complete: %d proposals generated, %d delivered",
            len(proposals),
            delivered_count,
        )

        return {
            "proposals_generated": len(proposals),
            "proposals_delivered": delivered_count,
            "metadata": {
                "knowledge_items": len(knowledge),
                "innovation_proposals": len(innovation_proposals),
                "pmf_score": gstack_results.get("pmf_score", 0),
                "confidence_avg": sum(p.confidence for p in proposals) / max(len(proposals), 1),
            },
        }

    async def _wait_for_innovation(self) -> bool:
        """Wait for Innovation Mind to complete (with timeout).

        Returns:
            True if Innovation completed, False if timeout.
        """
        if not self.innovation_scheduler:
            return False

        # Check if already complete
        if self.innovation_scheduler.is_session_complete():
            return True

        # Wait with timeout
        logger.info("[Entrepreneur] Waiting for Innovation Mind...")
        start_time = datetime.now(timezone.utc)
        timeout = timedelta(minutes=self.innovation_timeout_minutes)

        while datetime.now(timezone.utc) - start_time < timeout:
            if self.innovation_scheduler.is_session_complete():
                logger.info("[Entrepreneur] Innovation Mind completed")
                return True
            await asyncio.sleep(5)  # Check every 5 seconds

        logger.warning("[Entrepreneur] Timeout waiting for Innovation Mind")
        return False

    async def _query_recent_knowledge(self) -> list[dict[str, Any]]:
        """Query knowledge from last 24 hours."""
        since = datetime.now(timezone.utc) - timedelta(hours=24)

        query = """
            SELECT id, type, label, source, created_at
            FROM nodes
            WHERE type = 'atomic_note'
            AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT 100
        """

        try:
            rows = await self.graph_db.execute_query(query, (since.isoformat(),))
            return [
                {
                    "id": row["id"],
                    "type": row["type"],
                    "label": row["label"],
                    "source": row["source"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        except Exception as exc:
            logger.error("[Entrepreneur] Failed to query knowledge: %s", exc)
            return []

    async def _analyze_with_gstack(
        self,
        knowledge: list[dict],
        innovation_proposals: list[Proposal],
    ) -> dict[str, Any]:
        """Analyze knowledge and proposals using GStack framework."""
        # Combine knowledge and Innovation proposals
        knowledge_text = "\n\n".join(
            f"[{i+1}] {item['label']}"
            for i, item in enumerate(knowledge[:15])
        )

        innovation_text = "\n\n".join(
            f"[Innovation {i+1}] {p.title}: {p.summary}"
            for i, p in enumerate(innovation_proposals[:5])
        )

        combined_content = f"""## Recent Knowledge (24h)

{knowledge_text}

## Innovation Proposals

{innovation_text if innovation_text else "No Innovation proposals available"}
"""

        from aily.thinking.models import KnowledgePayload

        payload = KnowledgePayload(
            content=combined_content,
            source_title="DIKIWI + Innovation Aggregate (24h)",
            metadata={
                "knowledge_count": len(knowledge),
                "innovation_count": len(innovation_proposals),
                "mind": "entrepreneur",
            },
        )

        try:
            result = await self.gstack_analyzer.analyze(payload)

            return {
                "insights": result.insights,
                "pmf_score": result.raw_analysis.get("pmf_analysis", {}).get("pmf_score", 50),
                "shipping_velocity": result.raw_analysis.get("shipping_assessment", {}).get("velocity_score", "medium"),
                "growth_loops": result.raw_analysis.get("growth_loops", []),
                "confidence": result.confidence,
                "priority": result.priority.value if hasattr(result.priority, 'value') else str(result.priority),
            }

        except Exception as exc:
            logger.error("[Entrepreneur] GStack analysis failed: %s", exc)
            return {
                "insights": [],
                "pmf_score": 50,
                "shipping_velocity": "medium",
                "growth_loops": [],
                "confidence": 0.5,
                "error": str(exc),
            }

    async def _generate_proposals(
        self,
        gstack_results: dict[str, Any],
        knowledge: list[dict],
        innovation_proposals: list[Proposal],
    ) -> list[Proposal]:
        """Generate business proposals from GStack analysis."""
        proposals = []
        source_ids = [k["id"] for k in knowledge[:5]]

        # Proposal from PMF analysis
        pmf_score = gstack_results.get("pmf_score", 50)
        if pmf_score < 60:
            proposals.append(Proposal(
                mind_name="entrepreneur",
                proposal_type=ProposalType.BUSINESS,
                title="PMF Alert: Signals suggest weak product-market fit",
                content=self._format_pmf_proposal(gstack_results, weak=True),
                summary=f"PMF score {pmf_score}/100 - consider pivot or deep user research",
                confidence=0.8 if pmf_score < 40 else 0.6,
                priority="high" if pmf_score < 40 else "medium",
                framework_used="GStack",
                source_knowledge_ids=source_ids,
            ))
        elif pmf_score > 80:
            proposals.append(Proposal(
                mind_name="entrepreneur",
                proposal_type=ProposalType.BUSINESS,
                title="PMF Strong: Double down on what's working",
                content=self._format_pmf_proposal(gstack_results, weak=False),
                summary=f"PMF score {pmf_score}/100 - time to scale",
                confidence=min(pmf_score / 100.0, 0.95),
                priority="high",
                framework_used="GStack",
                source_knowledge_ids=source_ids,
            ))

        # Proposals from growth loops
        for loop in gstack_results.get("growth_loops", [])[:3]:
            proposals.append(Proposal(
                mind_name="entrepreneur",
                proposal_type=ProposalType.BUSINESS,
                title=f"Growth Loop: {loop.get('loop_type', 'Unknown').title()}",
                content=self._format_growth_loop_proposal(loop),
                summary=loop.get("description", "Growth opportunity identified")[:150],
                confidence=self._map_strength_to_confidence(loop.get("strength", "medium")),
                priority="high" if loop.get("strength") == "strong" else "medium",
                framework_used="GStack",
                source_knowledge_ids=source_ids,
            ))

        # Proposals from general insights
        for insight in gstack_results.get("insights", [])[:3]:
            proposals.append(Proposal(
                mind_name="entrepreneur",
                proposal_type=ProposalType.BUSINESS,
                title=f"Business Insight: {insight[:50]}..." if len(insight) > 50 else f"Business Insight: {insight}",
                content=insight,
                summary=insight[:150],
                confidence=gstack_results.get("confidence", 0.5),
                priority=gstack_results.get("priority", "medium"),
                framework_used="GStack",
                source_knowledge_ids=source_ids,
            ))

        return proposals

    async def _deliver_proposals(self, proposals: list[Proposal]) -> int:
        """Deliver proposals to Feishu and Obsidian."""
        if not proposals:
            return 0

        delivered = 0

        # Deliver to Obsidian
        if self.obsidian_writer:
            for proposal in proposals:
                try:
                    note_path = await self.obsidian_writer.write_note(
                        title=f"Business: {proposal.title[:80]}",
                        markdown=proposal.to_markdown(),
                        source_url=f"aily://business/{proposal.id}",
                    )
                    proposal.obsidian_note_path = note_path
                    proposal.status = ProposalStatus.DELIVERED
                    delivered += 1
                    logger.debug("[Entrepreneur] Proposal written to Obsidian: %s", note_path)
                except Exception as exc:
                    logger.error("[Entrepreneur] Failed to write to Obsidian: %s", exc)

        # Deliver summary to Feishu
        if self.feishu_pusher and proposals:
            try:
                summary = self._format_feishu_summary(proposals)
                from aily.config import SETTINGS
                open_id = SETTINGS.aily_digest_feishu_open_id
                if open_id:
                    await self.feishu_pusher.send_message(open_id, summary)
                    logger.info("[Entrepreneur] Summary sent to Feishu")
            except Exception as exc:
                logger.error("[Entrepreneur] Failed to send Feishu summary: %s", exc)

        return delivered

    def _format_pmf_proposal(self, gstack_results: dict, weak: bool) -> str:
        """Format PMF analysis as proposal."""
        pmf_data = gstack_results.get("pmf_analysis", {})

        if weak:
            return f"""## Product-Market Fit Analysis

**PMF Score:** {gstack_results.get('pmf_score', 50)}/100

**Warning Signals:**
{chr(10).join(f"- {signal}" for signal in pmf_data.get('contradicting_signals', ['Insufficient user engagement'])[:5])}

**Recommendations:**

1. **Talk to users immediately** - Schedule 5 customer interviews this week
2. **Identify the drop-off point** - Where are users leaving? Why?
3. **Consider pivot options** - What adjacent problems can you solve?
4. **Measure leading indicators** - Focus on retention, not just acquisition

**The hard truth:** Without PMF, nothing else matters. All optimization is premature.
"""
        else:
            return f"""## Product-Market Fit Analysis

**PMF Score:** {gstack_results.get('pmf_score', 50)}/100

**Positive Signals:**
{chr(10).join(f"- {signal}" for signal in pmf_data.get('supporting_signals', ['Strong user engagement'])[:5])}

**Recommendations:**

1. **Double down on what's working** - Scale your best channels
2. **Hire for growth** - Add team members who can accelerate
3. **Watch for competitors** - PMF attracts competition; stay ahead
4. **Maintain velocity** - Don't let process slow down shipping

**The opportunity:** You have something people want. Now execute relentlessly.
"""

    def _format_growth_loop_proposal(self, loop: dict) -> str:
        """Format growth loop as proposal."""
        return f"""## Growth Loop Opportunity

**Type:** {loop.get('loop_type', 'Unknown').title()}

**Strength:** {loop.get('strength', 'medium').title()}

**Description:**
{loop.get('description', 'No description')}

**Activation Points:**
{chr(10).join(f"- {point}" for point in loop.get('activation_points', ['Optimize onboarding flow'])[:5])}

**Action Items:**

1. Map the complete user journey through this loop
2. Identify the biggest drop-off point
3. Run experiments to improve conversion at that step
4. Measure impact on overall growth rate
5. Document learnings and iterate

**Success metric:** Loop velocity (users completing full cycle per week)
"""

    def _format_feishu_summary(self, proposals: list[Proposal]) -> str:
        """Format proposals for Feishu notification."""
        lines = [
            "💼 **Entrepreneur Mind - Daily Proposals**",
            f"Generated {len(proposals)} business proposals:",
            "",
        ]

        for i, proposal in enumerate(proposals[:5], 1):
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                proposal.priority, "⚪"
            )
            lines.append(f"{emoji} **{i}.** {proposal.title}")
            lines.append(f"   {proposal.summary[:100]}...")
            lines.append(f"   _Confidence: {proposal.confidence:.0%}_")
            lines.append("")

        if len(proposals) > 5:
            lines.append(f"... and {len(proposals) - 5} more proposals in Obsidian")

        lines.append("")
        lines.append("📁 Full details in Obsidian: Aily/Proposals/Business/")

        return "\n".join(lines)

    def _map_strength_to_confidence(self, strength: str) -> float:
        """Map growth loop strength to confidence."""
        mapping = {
            "strong": 0.85,
            "medium": 0.65,
            "weak": 0.45,
            "potential": 0.55,
        }
        return mapping.get(strength.lower(), 0.5)
