"""DIKIWI Mind - Continuous knowledge processing pipeline.

Implements the DIKIWI (Data-Information-Knowledge-Insight-Wisdom-Impact) pipeline:
- Data: Raw input (every input)
- Information: Structured content
- Knowledge: Atomic ideas (stored in GraphDB)
- Insight: Pattern recognition
- Wisdom: Synthesis
- Impact: Actionable proposals

The DIKIWI Mind runs continuously, processing every input through all stages.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aily.graph.db import GraphDB
    from aily.llm.client import LLMClient
    from aily.processing.atomicizer import AtomicNoteGenerator
    from aily.gating.drainage import DrainageSystem, RainDrop

logger = logging.getLogger(__name__)


class DikiwiStage(Enum):
    """Stages of the DIKIWI pipeline."""

    DATA = auto()  # Raw input
    INFORMATION = auto()  # Structured content
    KNOWLEDGE = auto()  # Atomic ideas
    INSIGHT = auto()  # Pattern recognition
    WISDOM = auto()  # Synthesis
    IMPACT = auto()  # Actionable proposals


@dataclass
class StageResult:
    """Result of processing a single DIKIWI stage."""

    stage: DikiwiStage
    success: bool
    items_processed: int = 0
    items_output: int = 0
    processing_time_ms: float = 0.0
    error_message: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class DikiwiResult:
    """Complete result of DIKIWI pipeline processing."""

    input_id: str
    pipeline_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    stage_results: list[StageResult] = field(default_factory=list)

    @property
    def total_time_ms(self) -> float:
        """Calculate total pipeline time."""
        if not self.completed_at:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds() * 1000

    @property
    def final_stage_reached(self) -> DikiwiStage | None:
        """Get the final stage that was successfully reached."""
        for stage in reversed(DikiwiStage):
            for result in self.stage_results:
                if result.stage == stage and result.success:
                    return stage
        return None


class DikiwiMind:
    """Continuous DIKIWI pipeline for knowledge processing.

    Every input flows through all DIKIWI stages:
    1. Data: Capture raw input (RainDrop)
    2. Information: Extract/structure content
    3. Knowledge: Atomize into discrete ideas
    4. Insight: Detect patterns, find connections
    5. Wisdom: Synthesize across sources
    6. Impact: Generate actionable proposals (feeds Innovation/Entrepreneur)

    The DIKIWI Mind is the foundation of the Three-Mind System. It runs
    continuously and feeds the scheduled Innovation and Entrepreneur minds.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        graph_db: GraphDB,
        atomicizer: AtomicNoteGenerator | None = None,
        enabled: bool = True,
        obsidian_writer: Any | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.graph_db = graph_db
        self.atomicizer = atomicizer
        self.enabled = enabled
        self.obsidian_writer = obsidian_writer

        # Cache for duplicate detection
        self._content_cache: dict[str, tuple[float, str]] = {}  # hash -> (timestamp, result_id)
        self._cache_ttl_seconds = 3600  # 1 hour

        # Metrics
        self._total_inputs = 0
        self._successful_pipelines = 0
        self._failed_pipelines = 0

    async def process_input(
        self,
        drop: RainDrop,
        skip_cache: bool = False,
    ) -> DikiwiResult:
        """Process a single input through the full DIKIWI pipeline.

        Args:
            drop: The RainDrop (input) to process
            skip_cache: If True, bypass cache lookup

        Returns:
            DikiwiResult with complete pipeline results
        """
        if not self.enabled:
            logger.debug("[DIKIWI] Mind disabled, skipping input %s", drop.id[:12])
            return DikiwiResult(
                input_id=drop.id,
                stage_results=[StageResult(
                    stage=DikiwiStage.DATA,
                    success=False,
                    error_message="DIKIWI Mind disabled",
                )],
            )

        self._total_inputs += 1
        start_time = time.time()
        pipeline_id = f"dikiwi_{drop.id[:12]}_{int(start_time)}"

        logger.info("[DIKIWI] Starting pipeline %s for drop %s", pipeline_id, drop.id[:12])

        result = DikiwiResult(
            input_id=drop.id,
            pipeline_id=pipeline_id,
        )

        try:
            # Stage 1: DATA -> Capture
            stage1 = await self._stage_data(drop)
            result.stage_results.append(stage1)
            if not stage1.success:
                raise RuntimeError(f"Stage DATA failed: {stage1.error_message}")

            # Stage 2: INFORMATION -> Structure
            stage2 = await self._stage_information(drop, stage1.data)
            result.stage_results.append(stage2)
            if not stage2.success:
                raise RuntimeError(f"Stage INFORMATION failed: {stage2.error_message}")

            # Stage 3: KNOWLEDGE -> Atomize
            stage3 = await self._stage_knowledge(drop, stage2.data)
            result.stage_results.append(stage3)
            if not stage3.success:
                raise RuntimeError(f"Stage KNOWLEDGE failed: {stage3.error_message}")

            # Stage 4: INSIGHT -> Pattern detection
            stage4 = await self._stage_insight(drop, stage3.data)
            result.stage_results.append(stage4)

            # Stage 5: WISDOM -> Synthesis
            stage5 = await self._stage_wisdom(drop, stage4.data)
            result.stage_results.append(stage5)

            # Stage 6: IMPACT -> Proposals (async, feeds other minds)
            stage6 = await self._stage_impact(drop, stage5.data)
            result.stage_results.append(stage6)

            result.completed_at = datetime.now(timezone.utc)
            self._successful_pipelines += 1

            logger.info(
                "[DIKIWI] Pipeline %s completed in %.2fms, reached %s",
                pipeline_id,
                result.total_time_ms,
                result.final_stage_reached.name if result.final_stage_reached else "none",
            )

        except Exception as exc:
            result.completed_at = datetime.now(timezone.utc)
            self._failed_pipelines += 1
            logger.exception("[DIKIWI] Pipeline %s failed: %s", pipeline_id, exc)

        return result

    async def _stage_data(self, drop: RainDrop) -> StageResult:
        """Stage 1: DATA - Capture raw input."""
        start = time.time()

        try:
            # Store raw input in GraphDB
            node_id = f"raw_{drop.id}"
            await self.graph_db.insert_node(
                node_id=node_id,
                node_type="dikiwi_data",
                label=f"Data: {drop.content[:100]}",
                source=drop.source,
            )

            processing_time = (time.time() - start) * 1000

            return StageResult(
                stage=DikiwiStage.DATA,
                success=True,
                items_processed=1,
                items_output=1,
                processing_time_ms=processing_time,
                data={"node_id": node_id, "drop_id": drop.id},
            )

        except Exception as exc:
            return StageResult(
                stage=DikiwiStage.DATA,
                success=False,
                error_message=str(exc),
                processing_time_ms=(time.time() - start) * 1000,
            )

    async def _stage_information(self, drop: RainDrop, prev_data: dict) -> StageResult:
        """Stage 2: INFORMATION - Structure content."""
        start = time.time()

        try:
            # Extract structured information from content
            # For URLs: already parsed; for text: extract entities
            structured = {
                "content": drop.content,
                "source": drop.source,
                "creator": drop.creator_id,
                "timestamp": drop.created_at.isoformat() if hasattr(drop.created_at, 'isoformat') else str(drop.created_at),
                "keywords": self._extract_keywords(drop.content),
            }

            processing_time = (time.time() - start) * 1000

            return StageResult(
                stage=DikiwiStage.INFORMATION,
                success=True,
                items_processed=1,
                items_output=1,
                processing_time_ms=processing_time,
                data=structured,
            )

        except Exception as exc:
            return StageResult(
                stage=DikiwiStage.INFORMATION,
                success=False,
                error_message=str(exc),
                processing_time_ms=(time.time() - start) * 1000,
            )

    async def _stage_knowledge(self, drop: RainDrop, prev_data: dict) -> StageResult:
        """Stage 3: KNOWLEDGE - Atomize into discrete ideas."""
        start = time.time()

        try:
            if not self.atomicizer:
                # No atomicizer, treat as single knowledge unit
                return StageResult(
                    stage=DikiwiStage.KNOWLEDGE,
                    success=True,
                    items_processed=1,
                    items_output=1,
                    processing_time_ms=(time.time() - start) * 1000,
                    data={"atomic_notes": [prev_data["content"]], "count": 1},
                )

            # Use atomicizer to break content into atomic notes
            from aily.processing.atomicizer import AtomicNote

            notes = await self.atomicizer.atomize(
                content=prev_data["content"],
                source_url=prev_data.get("source", ""),
                raw_log_id=drop.id,
            )

            note_contents = [note.content for note in notes]

            # Write atomic notes to Obsidian if writer is available
            obsidian_paths = []
            if self.obsidian_writer:
                for note in notes:
                    try:
                        # Create markdown content for the atomic note
                        markdown = f"# Atomic Note\n\n{note.content}\n\n---\n**Source**: {note.source_url}\n**Created**: {note.created_at.isoformat()}\n**Tags**: {', '.join(note.tags)}\n"
                        path = await self.obsidian_writer.write_note(
                            title=f"Atomic: {note.content[:50]}",
                            markdown=markdown,
                            source_url=note.source_url,
                        )
                        obsidian_paths.append(path)
                        logger.debug("[DIKIWI] Wrote atomic note to Obsidian: %s", path)
                    except Exception as e:
                        logger.warning("[DIKIWI] Failed to write atomic note to Obsidian: %s", e)

            processing_time = (time.time() - start) * 1000

            return StageResult(
                stage=DikiwiStage.KNOWLEDGE,
                success=True,
                items_processed=1,
                items_output=len(notes),
                processing_time_ms=processing_time,
                data={"atomic_notes": note_contents, "count": len(notes), "obsidian_paths": obsidian_paths},
            )

        except Exception as exc:
            return StageResult(
                stage=DikiwiStage.KNOWLEDGE,
                success=False,
                error_message=str(exc),
                processing_time_ms=(time.time() - start) * 1000,
            )

    async def _stage_insight(self, drop: RainDrop, prev_data: dict) -> StageResult:
        """Stage 4: INSIGHT - Detect patterns and connections."""
        start = time.time()

        try:
            # Query GraphDB for similar knowledge
            notes = prev_data.get("atomic_notes", [])
            connections = []

            for note in notes[:3]:  # Limit to first 3 notes for performance
                # Simple keyword-based similarity
                keywords = self._extract_keywords(note)
                if keywords:
                    # Query for nodes with similar keywords
                    similar = await self.graph_db.get_nodes_by_type("atomic_note")
                    for node in similar[:5]:  # Top 5 similar
                        if any(kw in node.get("label", "").lower() for kw in keywords[:3]):
                            connections.append({
                                "node_id": node.get("id"),
                                "label": node.get("label", "")[:100],
                            })

            processing_time = (time.time() - start) * 1000

            return StageResult(
                stage=DikiwiStage.INSIGHT,
                success=True,
                items_processed=len(notes),
                items_output=len(connections),
                processing_time_ms=processing_time,
                data={"connections": connections, "patterns_detected": len(connections) > 0},
            )

        except Exception as exc:
            return StageResult(
                stage=DikiwiStage.INSIGHT,
                success=False,
                error_message=str(exc),
                processing_time_ms=(time.time() - start) * 1000,
            )

    async def _stage_wisdom(self, drop: RainDrop, prev_data: dict) -> StageResult:
        """Stage 5: WISDOM - Synthesize across sources."""
        start = time.time()

        try:
            # Simple synthesis: combine connections into themes
            connections = prev_data.get("connections", [])
            themes = []

            if connections:
                # Group by common concepts (simplified)
                themes.append({
                    "theme": "Knowledge Network",
                    "connections_count": len(connections),
                    "description": f"Input connects to {len(connections)} existing knowledge nodes",
                })

            processing_time = (time.time() - start) * 1000

            return StageResult(
                stage=DikiwiStage.WISDOM,
                success=True,
                items_processed=len(connections),
                items_output=len(themes),
                processing_time_ms=processing_time,
                data={"themes": themes, "synthesized": len(themes) > 0},
            )

        except Exception as exc:
            return StageResult(
                stage=DikiwiStage.WISDOM,
                success=False,
                error_message=str(exc),
                processing_time_ms=(time.time() - start) * 1000,
            )

    async def _stage_impact(self, drop: RainDrop, prev_data: dict) -> StageResult:
        """Stage 6: IMPACT - Generate actionable proposals."""
        start = time.time()

        try:
            # This stage feeds the Innovation/Entrepreneur minds
            # For now, mark potential impact areas
            themes = prev_data.get("themes", [])

            impact_areas = []
            if themes:
                impact_areas.append({
                    "area": "knowledge_graph",
                    "potential": "medium",
                    "description": "New connections added to knowledge graph",
                })

            processing_time = (time.time() - start) * 1000

            return StageResult(
                stage=DikiwiStage.IMPACT,
                success=True,
                items_processed=len(themes),
                items_output=len(impact_areas),
                processing_time_ms=processing_time,
                data={
                    "impact_areas": impact_areas,
                    "ready_for_scheduled_minds": len(themes) > 0,
                },
            )

        except Exception as exc:
            return StageResult(
                stage=DikiwiStage.IMPACT,
                success=False,
                error_message=str(exc),
                processing_time_ms=(time.time() - start) * 1000,
            )

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from content (simple implementation)."""
        # Simple keyword extraction: words > 5 chars, lowercase
        words = content.lower().split()
        keywords = [
            w.strip(".,!?;:()[]{}") for w in words
            if len(w) > 5 and w.isalnum()
        ]
        # Remove duplicates and limit
        return list(dict.fromkeys(keywords))[:10]

    def _compute_content_hash(self, content: str) -> str:
        """Compute hash for duplicate detection."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_metrics(self) -> dict[str, Any]:
        """Get processing metrics."""
        return {
            "total_inputs": self._total_inputs,
            "successful_pipelines": self._successful_pipelines,
            "failed_pipelines": self._failed_pipelines,
            "success_rate": (
                self._successful_pipelines / max(self._total_inputs, 1)
            ),
            "enabled": self.enabled,
        }

    async def get_recent_knowledge(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get knowledge from last N hours (for Innovation/Entrepreneur minds)."""
        since = datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=hours)

        query = """
            SELECT id, type, label, source, created_at
            FROM nodes
            WHERE type = 'atomic_note'
            AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT ?
        """

        try:
            rows = await self.graph_db.execute_query(query, (since.isoformat(), limit))
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
            logger.error("[DIKIWI] Failed to query recent knowledge: %s", exc)
            return []
