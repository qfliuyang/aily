"""Innovation Mind - Daily TRIZ-based insight generation.

Runs daily at 8am to:
1. Query last 24h of knowledge from DIKIWI pipeline
2. Analyze using TRIZ framework (contradictions, principles, evolution)
3. Generate innovation proposals (max 10 per session)
4. Deliver high-confidence proposals (>=0.7) to Feishu and Obsidian
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from aily.sessions.base import BaseMindScheduler
from aily.sessions.models import Proposal, ProposalType, ProposalStatus

if TYPE_CHECKING:
    from aily.graph.db import GraphDB
    from aily.llm.client import LLMClient
    from aily.thinking.frameworks.triz import TrizAnalyzer
    from aily.writer.obsidian import ObsidianWriter
    from aily.push.feishu import FeishuPusher

logger = logging.getLogger(__name__)


class InnovationScheduler(BaseMindScheduler):
    """Scheduled Innovation Mind for daily TRIZ analysis.

    Generates innovation proposals by applying TRIZ methodology
    (Theory of Inventive Problem Solving) to recent knowledge.
    Identifies contradictions, recommends principles, and suggests
    evolutionary improvements.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        graph_db: GraphDB,
        obsidian_writer: ObsidianWriter | None = None,
        feishu_pusher: FeishuPusher | None = None,
        schedule_hour: int = 8,
        schedule_minute: int = 0,
        circuit_breaker_threshold: int = 3,
        enabled: bool = True,
        proposal_min_confidence: float = 0.7,
        proposal_max_per_session: int = 10,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            mind_name="innovation",
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

        # Initialize TRIZ analyzer
        from aily.thinking.frameworks.triz import TrizAnalyzer
        self.triz_analyzer = TrizAnalyzer(llm_client)

        # Session tracking for Entrepreneur dependency
        self._last_session_completed: datetime | None = None
        self._current_session_proposals: list[Proposal] = []

    async def _run_session(self) -> dict[str, Any]:
        """Execute daily innovation session.

        Returns:
            Dict with proposals_generated, proposals_delivered, metadata
        """
        logger.info("[Innovation] Starting daily innovation session")

        # Step 1: Query recent knowledge (last 24h)
        knowledge = await self._query_recent_knowledge()
        if not knowledge:
            logger.info("[Innovation] No recent knowledge found, skipping session")
            return {
                "proposals_generated": 0,
                "proposals_delivered": 0,
                "metadata": {"reason": "no_knowledge"},
            }

        logger.info("[Innovation] Analyzing %d knowledge items", len(knowledge))

        # Step 2: Analyze using TRIZ
        triz_results = await self._analyze_with_triz(knowledge)

        # Step 3: Generate proposals from TRIZ insights
        proposals = await self._generate_proposals(triz_results, knowledge)

        # Step 4: Filter by confidence threshold
        qualified_proposals = [
            p for p in proposals
            if p.confidence >= self.proposal_min_confidence
        ]

        # Step 5: Limit max proposals
        if len(qualified_proposals) > self.proposal_max_per_session:
            # Sort by confidence and take top N
            qualified_proposals.sort(key=lambda x: x.confidence, reverse=True)
            qualified_proposals = qualified_proposals[:self.proposal_max_per_session]

        # Step 6: Deliver proposals
        delivered_count = await self._deliver_proposals(qualified_proposals)

        # Track for Entrepreneur dependency
        self._last_session_completed = datetime.now(timezone.utc)
        self._current_session_proposals = qualified_proposals

        logger.info(
            "[Innovation] Session complete: %d proposals generated, %d delivered",
            len(proposals),
            delivered_count,
        )

        return {
            "proposals_generated": len(proposals),
            "proposals_delivered": delivered_count,
            "metadata": {
                "knowledge_items": len(knowledge),
                "triz_insights": len(triz_results.get("insights", [])),
                "confidence_avg": sum(p.confidence for p in proposals) / max(len(proposals), 1),
            },
        }

    async def _query_recent_knowledge(self) -> list[dict[str, Any]]:
        """Query knowledge from last 24 hours."""
        from datetime import timedelta

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
            logger.error("[Innovation] Failed to query knowledge: %s", exc)
            return []

    async def _analyze_with_triz(self, knowledge: list[dict]) -> dict[str, Any]:
        """Analyze knowledge using TRIZ framework."""
        # Combine knowledge into analysis payload
        combined_content = "\n\n".join(
            f"[{i+1}] {item['label']}"
            for i, item in enumerate(knowledge[:20])  # Limit to 20 items
        )

        from aily.thinking.models import KnowledgePayload

        payload = KnowledgePayload(
            content=combined_content,
            source_title="DIKIWI Knowledge Aggregate (24h)",
            metadata={
                "knowledge_count": len(knowledge),
                "mind": "innovation",
            },
        )

        try:
            result = await self.triz_analyzer.analyze(payload)

            return {
                "insights": result.insights,
                "contradictions": result.raw_analysis.get("contradictions", []),
                "principles": result.raw_analysis.get("principle_recommendations", []),
                "confidence": result.confidence,
                "priority": result.priority.value if hasattr(result.priority, 'value') else str(result.priority),
            }

        except Exception as exc:
            logger.error("[Innovation] TRIZ analysis failed: %s", exc)
            return {
                "insights": [],
                "contradictions": [],
                "principles": [],
                "confidence": 0.0,
                "error": str(exc),
            }

    async def _generate_proposals(
        self,
        triz_results: dict[str, Any],
        knowledge: list[dict],
    ) -> list[Proposal]:
        """Generate proposals from TRIZ analysis results."""
        proposals = []

        # Generate proposals from contradictions
        for contradiction in triz_results.get("contradictions", [])[:3]:
            proposal = Proposal(
                mind_name="innovation",
                proposal_type=ProposalType.INNOVATION,
                title=f"Contradiction: {contradiction.get('description', 'Unknown')[:50]}",
                content=self._format_contradiction_proposal(contradiction),
                summary=f"TRIZ contradiction identified: {contradiction.get('contradiction_type', 'technical')}",
                confidence=contradiction.get('severity_score', 0.5) / 100.0,  # Normalize to 0-1
                priority=self._map_priority(contradiction.get('severity', 'medium')),
                framework_used="TRIZ",
                source_knowledge_ids=[k["id"] for k in knowledge[:5]],
            )
            proposals.append(proposal)

        # Generate proposals from principles
        for principle in triz_results.get("principles", [])[:3]:
            proposal = Proposal(
                mind_name="innovation",
                proposal_type=ProposalType.INNOVATION,
                title=f"Principle #{principle.get('principle_number', '?')}: {principle.get('principle_name', 'Unknown')}",
                content=self._format_principle_proposal(principle),
                summary=f"Apply TRIZ principle: {principle.get('application', '')[:100]}",
                confidence=principle.get('confidence', 0.5),
                priority="medium",
                framework_used="TRIZ",
                source_knowledge_ids=[k["id"] for k in knowledge[:5]],
            )
            proposals.append(proposal)

        # Generate proposal from general insights
        for insight in triz_results.get("insights", [])[:4]:
            proposal = Proposal(
                mind_name="innovation",
                proposal_type=ProposalType.INNOVATION,
                title=f"Insight: {insight[:60]}..." if len(insight) > 60 else f"Insight: {insight}",
                content=insight,
                summary=insight[:150],
                confidence=triz_results.get("confidence", 0.5),
                priority=triz_results.get("priority", "medium"),
                framework_used="TRIZ",
                source_knowledge_ids=[k["id"] for k in knowledge[:5]],
            )
            proposals.append(proposal)

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
                        title=f"Innovation: {proposal.title[:80]}",
                        markdown=proposal.to_markdown(),
                        source_url=f"aily://innovation/{proposal.id}",
                    )
                    proposal.obsidian_note_path = note_path
                    proposal.status = ProposalStatus.DELIVERED
                    delivered += 1
                    logger.debug("[Innovation] Proposal written to Obsidian: %s", note_path)
                except Exception as exc:
                    logger.error("[Innovation] Failed to write to Obsidian: %s", exc)

        # Deliver summary to Feishu
        if self.feishu_pusher and proposals:
            try:
                summary = self._format_feishu_summary(proposals)
                # Get open_id from settings
                from aily.config import SETTINGS
                open_id = SETTINGS.aily_digest_feishu_open_id
                if open_id:
                    await self.feishu_pusher.send_message(open_id, summary)
                    logger.info("[Innovation] Summary sent to Feishu")
            except Exception as exc:
                logger.error("[Innovation] Failed to send Feishu summary: %s", exc)

        return delivered

    def _format_contradiction_proposal(self, contradiction: dict) -> str:
        """Format a contradiction as a proposal."""
        return f"""## TRIZ Contradiction Analysis

**Type:** {contradiction.get('contradiction_type', 'Unknown')}

**Description:**
{contradiction.get('description', 'No description')}

**Severity:** {contradiction.get('severity', 'medium')}

**Recommended Resolution:**
{contradiction.get('resolution_approach', 'Analyze using TRIZ separation principles')}

## Action Items

1. Identify the conflicting parameters in your specific context
2. Apply appropriate TRIZ separation principles (space, time, condition, system levels)
3. Generate solution concepts that resolve the contradiction
4. Evaluate solutions against ideal final result criteria
"""

    def _format_principle_proposal(self, principle: dict) -> str:
        """Format a principle recommendation as a proposal."""
        return f"""## TRIZ Principle Application

**Principle #{principle.get('principle_number', '?')}:** {principle.get('principle_name', 'Unknown')}

**Application:**
{principle.get('application', 'No application guidance')}

**Expected Outcome:**
{principle.get('expected_outcome', 'Resolution of identified contradiction')}

## Implementation Steps

1. Study the principle and its classic examples
2. Map the principle to your specific problem context
3. Brainstorm 3-5 specific implementations
4. Select the most promising for prototyping
"""

    def _format_feishu_summary(self, proposals: list[Proposal]) -> str:
        """Format proposals for Feishu notification."""
        lines = [
            "🧠 **Innovation Mind - Daily Proposals**",
            f"Generated {len(proposals)} proposals from last 24h knowledge:",
            "",
        ]

        for i, proposal in enumerate(proposals[:5], 1):  # Top 5
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
        lines.append("📁 Full details in Obsidian: Aily/Proposals/Innovation/")

        return "\n".join(lines)

    def _map_priority(self, priority: str) -> str:
        """Map TRIZ priority to proposal priority."""
        mapping = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
        }
        return mapping.get(priority.lower(), "medium")

    def get_current_proposals(self) -> list[Proposal]:
        """Get proposals from current session (for Entrepreneur dependency)."""
        return self._current_session_proposals

    def is_session_complete(self) -> bool:
        """Check if today's session has completed (for Entrepreneur dependency)."""
        if not self._last_session_completed:
            return False
        # Check if completed today
        today = datetime.now(timezone.utc).date()
        return self._last_session_completed.date() == today
