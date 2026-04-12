"""Innolaval - The Innovation Laval Nozzle.

Wide inputs from multiple innovation methodologies running in parallel,
focused through a synthesis nozzle into high-quality proposals.

Name origin: Innovation + Laval (convergent-divergent nozzle principle)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from aily.sessions.base import BaseMindScheduler
from aily.sessions.models import Proposal

logger = logging.getLogger(__name__)


class InnovationMethod(Enum):
    """Available innovation methodologies."""
    TRIZ = "triz"
    SIT = "sit"
    SIX_HATS = "six_hats"
    BIOMIMICRY = "biomimicry"
    MORPHOLOGICAL = "morphological"
    BLUE_OCEAN = "blue_ocean"
    SCAMPER = "scamper"
    FIRST_PRINCIPLES = "first_principles"


@dataclass
class MethodResult:
    """Result from a single innovation method."""
    method: InnovationMethod
    proposals: list[Proposal]
    confidence: float
    processing_time_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NozzleConfig:
    """Configuration for the innovation nozzle."""
    min_confidence: float = 0.6
    min_novelty_score: float = 0.5
    min_feasibility_score: float = 0.4
    max_proposals_per_session: int = 10
    diversity_threshold: float = 0.7
    enabled_methods: set = field(default_factory=lambda: {
        InnovationMethod.TRIZ,
        InnovationMethod.SIT,
        InnovationMethod.SIX_HATS,
        InnovationMethod.SCAMPER,
        InnovationMethod.BLUE_OCEAN,
        InnovationMethod.FIRST_PRINCIPLES,
    })


class InnolavalScheduler(BaseMindScheduler):
    """Innovation Laval Nozzle - wide inputs, focused output.

    Architecture:
        [Wide Input] -> [Parallel Methods] -> [Synthesis Nozzle] -> [Focused Proposals]

        TRIZ, SIT, Six Hats, Biomimicry, Morphological, Blue Ocean, SCAMPER...
    """

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
        nozzle_config: NozzleConfig | None = None,
    ) -> None:
        super().__init__(
            llm_client=llm_client,
            mind_name="innolaval",
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
            circuit_breaker_threshold=circuit_breaker_threshold,
            enabled=enabled,
        )
        self.graph_db = graph_db
        self.obsidian_writer = obsidian_writer
        self.feishu_pusher = feishu_pusher
        self.nozzle_config = nozzle_config or NozzleConfig()
        self._analyzers: dict[InnovationMethod, Any] = {}
        self._current_session_proposals: list[Proposal] = []

    def _get_analyzer(self, method: InnovationMethod) -> Any:
        """Get or create analyzer for a method."""
        if method in self._analyzers:
            return self._analyzers[method]

        # Lazy import to avoid circular dependencies
        try:
            if method == InnovationMethod.TRIZ:
                from aily.thinking.frameworks.triz import TrizAnalyzer
                analyzer = TrizAnalyzer(self.llm_client)
            elif method == InnovationMethod.SIT:
                from aily.thinking.frameworks.sit import SitAnalyzer
                analyzer = SitAnalyzer(self.llm_client)
            elif method == InnovationMethod.SIX_HATS:
                from aily.thinking.frameworks.six_hats import SixHatsAnalyzer
                analyzer = SixHatsAnalyzer(self.llm_client)
            elif method == InnovationMethod.BIOMIMICRY:
                from aily.thinking.frameworks.biomimicry import BiomimicryAnalyzer
                analyzer = BiomimicryAnalyzer(self.llm_client)
            elif method == InnovationMethod.MORPHOLOGICAL:
                from aily.thinking.frameworks.morphological import MorphologicalAnalyzer
                analyzer = MorphologicalAnalyzer(self.llm_client)
            elif method == InnovationMethod.BLUE_OCEAN:
                from aily.thinking.frameworks.blue_ocean import BlueOceanAnalyzer
                analyzer = BlueOceanAnalyzer(self.llm_client)
            elif method == InnovationMethod.SCAMPER:
                from aily.thinking.frameworks.scamper import ScamperAnalyzer
                analyzer = ScamperAnalyzer(self.llm_client)
            elif method == InnovationMethod.FIRST_PRINCIPLES:
                from aily.thinking.frameworks.first_principles import FirstPrinciplesAnalyzer
                analyzer = FirstPrinciplesAnalyzer(self.llm_client)
            else:
                return None

            self._analyzers[method] = analyzer
            return analyzer

        except Exception as e:
            logger.warning(f"Failed to load analyzer for {method.value}: {e}")
            return None

    async def _run_session(self) -> dict[str, Any]:
        """Execute Innolaval session."""
        session_start = datetime.now(timezone.utc)
        logger.info("Innolaval session starting - wide input phase")

        context = await self._gather_context()
        enabled = self.nozzle_config.enabled_methods

        # Run all methods in parallel
        tasks = []
        for method in enabled:
            task = self._run_method(method, context)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid_results = [
            r for r in results
            if isinstance(r, MethodResult) and r.proposals
        ]

        logger.info(f"Innolaval: {len(valid_results)}/{len(enabled)} methods produced proposals")

        # Synthesis nozzle
        proposals = await self._synthesis_nozzle(valid_results)
        self._current_session_proposals = proposals

        # Output
        await self._output_proposals(proposals, session_start)

        return {
            "methods_run": len(valid_results),
            "proposals_generated": len(proposals),
            "proposals_delivered": len(proposals),
        }

    async def _run_method(self, method: InnovationMethod, context: dict) -> MethodResult | None:
        """Run a single innovation method."""
        start_time = datetime.now(timezone.utc)
        analyzer = self._get_analyzer(method)

        if not analyzer:
            logger.warning(f"No analyzer available for {method.value}")
            return MethodResult(
                method=method,
                proposals=[],
                confidence=0.0,
            )

        try:
            result = await analyzer.analyze(context)
            processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            # Convert to MethodResult format
            return MethodResult(
                method=method,
                proposals=result.proposals,
                confidence=result.confidence,
                processing_time_ms=processing_time,
                metadata=result.metadata,
            )
        except Exception as e:
            logger.error(f"Method {method.value} failed: {e}")
            return MethodResult(
                method=method,
                proposals=[],
                confidence=0.0,
            )

    async def _synthesis_nozzle(self, results: list[MethodResult]) -> list[Proposal]:
        """Filter and synthesize proposals."""
        all_proposals: list[Proposal] = []
        for result in results:
            all_proposals.extend(result.proposals)

        if not all_proposals:
            return []

        # Filter by confidence
        filtered = [
            p for p in all_proposals
            if p.confidence >= self.nozzle_config.min_confidence
        ]

        # Sort by confidence
        filtered.sort(key=lambda x: x.confidence, reverse=True)

        # Limit output
        return filtered[:self.nozzle_config.max_proposals_per_session]

    async def _gather_context(self) -> dict[str, Any]:
        """Gather context from GraphDB for innovation analysis."""
        context = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "focus_areas": ["eda", "ai", "semiconductor", "software"],
            "recent_insights": [],
        }

        # Try to get recent insights from GraphDB
        try:
            if self.graph_db:
                # Get recent nodes as insights
                nodes = await self.graph_db.get_recent_nodes(limit=20)
                context["recent_insights"] = [
                    {"label": n.get("label", ""), "type": n.get("type", "")}
                    for n in nodes
                ]
        except Exception as e:
            logger.debug(f"Could not gather GraphDB context: {e}")

        return context

    async def _output_proposals(self, proposals: list[Proposal], start: datetime) -> None:
        """Output proposals to Obsidian and Feishu."""
        if not proposals:
            logger.info("No proposals generated in this session")
            return

        logger.info(f"Generated {len(proposals)} proposals")

        # Write to Obsidian
        if self.obsidian_writer:
            try:
                date_str = start.strftime("%Y-%m-%d")
                for i, proposal in enumerate(proposals):
                    await self._write_proposal_to_obsidian(proposal, date_str, i)
            except Exception as e:
                logger.warning(f"Failed to write proposals to Obsidian: {e}")

        # Send to Feishu
        if self.feishu_pusher and proposals:
            try:
                top_proposals = proposals[:3]
                message = self._format_proposals_message(top_proposals, start)
                # Feishu pusher implementation here
            except Exception as e:
                logger.warning(f"Failed to send Feishu notification: {e}")

    async def _write_proposal_to_obsidian(self, proposal: Proposal, date_str: str, index: int) -> None:
        """Write a single proposal to Obsidian."""
        await self.obsidian_writer.write_note(
            title=f"Innovation: {proposal.title}",
            markdown=proposal.to_markdown(),
            source_url=f"aily://innolaval/{date_str}/{index}",
        )

    def _format_proposals_message(self, proposals: list[Proposal], start: datetime) -> str:
        """Format proposals for Feishu message."""
        lines = [f"🚀 **Innolaval Innovation Report** ({start.strftime('%Y-%m-%d %H:%M')})", ""]
        for i, p in enumerate(proposals, 1):
            lines.append(f"**{i}. {p.title}** (confidence: {p.confidence:.0%})")
            preview = p.summary or p.content
            lines.append(f"{preview[:200]}...")
            lines.append("")
        return "\n".join(lines)

    def get_current_proposals(self) -> list[Proposal]:
        """Return proposals from the most recent session."""
        return self._current_session_proposals

    def add_method(self, method: InnovationMethod) -> None:
        """Enable a new innovation method."""
        self.nozzle_config.enabled_methods.add(method)
        logger.info(f"Added {method.value} to Innolaval")

    def remove_method(self, method: InnovationMethod) -> None:
        """Disable an innovation method."""
        self.nozzle_config.enabled_methods.discard(method)
        logger.info(f"Removed {method.value} from Innolaval")

    def list_methods(self) -> dict[str, bool]:
        """List all methods and their status."""
        return {
            method.value: method in self.nozzle_config.enabled_methods
            for method in InnovationMethod
        }
