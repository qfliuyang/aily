"""WisdomAgent - Stage 5: WISDOM synthesis into Zettelkasten notes."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid

from aily.dikiwi.agents.base import DikiwiAgent
from aily.dikiwi.agents.context import AgentContext
from aily.dikiwi.agents.llm_tools import multi_agent_json
from aily.llm.prompt_registry import DikiwiPromptRegistry
from aily.sessions.dikiwi_mind import DikiwiStage, InformationNode, Insight, StageResult, ZettelkastenNote

logger = logging.getLogger(__name__)


class WisdomAgent(DikiwiAgent):
    """Stage 5: Synthesize insights into Zettelkasten permanent notes via producer-reviewer."""

    async def execute(self, ctx: AgentContext) -> StageResult:
        start = time.time()

        try:
            insight_result = self._find_stage_result(ctx, DikiwiStage.INSIGHT)
            info_result = self._find_stage_result(ctx, DikiwiStage.INFORMATION)
            knowledge_result = self._find_stage_result(ctx, DikiwiStage.KNOWLEDGE)
            if not insight_result or not info_result:
                raise RuntimeError("Prior stage results not found in context")

            insights: list[Insight] = insight_result.data.get("insights", [])
            insight_note_ids: list[str] = insight_result.data.get("insight_note_ids", [])
            info_nodes: list[InformationNode] = []
            if knowledge_result:
                info_nodes = knowledge_result.data.get("network_nodes", [])
            if not info_nodes:
                info_nodes = info_result.data.get("information_nodes", [])

            zettels: list[ZettelkastenNote] = []
            if info_nodes:
                zettels = await self._llm_synthesize_wisdom(insights, info_nodes, ctx)

            # Build title -> dikiwi_id map so Related links resolve exactly
            title_map: dict[str, str] = {}
            for z in zettels:
                zid = f"wisdom_{z.id}"
                title_map[z.title.lower()] = zid
                # Also index by slugified title for robust matching
                slug = "".join(c for c in z.title.lower() if c.isalnum())
                title_map[slug] = zid

            # Pre-register all zettel titles so cross-links use full filenames
            if ctx.dikiwi_obsidian_writer and zettels:
                for z in zettels:
                    ctx.dikiwi_obsidian_writer.register_note_title(
                        f"wisdom_{z.id}", z.title
                    )

            # Write wisdom notes
            wisdom_note_ids: list[str] = []
            if ctx.dikiwi_obsidian_writer and zettels:
                source_paths = ctx.drop.metadata.get("source_paths", [])
                for zettel in zettels:
                    try:
                        wid = await ctx.dikiwi_obsidian_writer.write_wisdom_note(
                            zettel, insight_note_ids, ctx.drop, source_paths, link_map=title_map
                        )
                        wisdom_note_ids.append(wid)
                        logger.info(
                            "[DIKIWI] Wrote wisdom note: %s (%d words)",
                            zettel.title[:40],
                            len(zettel.content.split()),
                        )
                    except Exception as e:
                        logger.warning("[DIKIWI] Failed to write wisdom note: %s", e)

            if ctx.memory and zettels:
                ctx.memory.add_assistant(
                    f"STAGE 5 (WISDOM) Complete: Authored {len(zettels)} permanent notes. "
                    f"Titles: {', '.join(z.title[:80] for z in zettels[:3])}"
                )

            processing_time = (time.time() - start) * 1000

            return StageResult(
                stage=DikiwiStage.WISDOM,
                success=True,
                items_processed=len(insights),
                items_output=len(zettels),
                processing_time_ms=processing_time,
                data={
                    "zettels": zettels,
                    "wisdom_note_ids": wisdom_note_ids,
                },
            )

        except Exception as exc:
            return StageResult(
                stage=DikiwiStage.WISDOM,
                success=False,
                error_message=str(exc),
                processing_time_ms=(time.time() - start) * 1000,
            )

    async def _llm_synthesize_wisdom(
        self,
        insights: list[Insight],
        info_nodes: list[InformationNode],
        ctx: AgentContext,
    ) -> list[ZettelkastenNote]:
        insights_desc = "\n".join(
            f"- [{i.insight_type}] {i.description[:200]}"
            for i in insights[:10]
        )
        info_samples = "\n".join(
            f"- [{n.domain}] {n.content[:220]}"
            for n in info_nodes[:20]
        )

        memory_context = DikiwiPromptRegistry.render_memory(ctx.memory, limit=1500)
        messages = DikiwiPromptRegistry.wisdom(
            insights_desc=insights_desc,
            info_samples=info_samples,
            memory_context=memory_context,
        )
        stage_key = f"wisdom:{hashlib.sha1((insights_desc + info_samples).encode('utf-8')).hexdigest()[:8]}"

        try:
            result = await multi_agent_json(
                llm_client=ctx.llm_client,
                stage="wisdom",
                stage_key=stage_key,
                producer_messages=messages,
                reviewer_messages_factory=lambda draft_json: DikiwiPromptRegistry.review(
                    stage="WISDOM",
                    reviewer_role="Slip-Box Editor",
                    objective="Review the draft permanent notes and return a cleaner set of atomic, source-grounded zettels for long-term use.",
                    output_contract=DikiwiPromptRegistry.WISDOM_CONTRACT,
                    draft_json=draft_json,
                    memory_context=memory_context,
                    review_focus=(
                        "Reject summary-shaped notes and preserve distinct durable ideas instead.",
                        "Split mechanisms, workflows, constraints, tradeoffs, and examples into separate notes when the source supports them.",
                        "Keep titles readable, human, and conceptually precise.",
                    ),
                    context_sections=(
                        ("Insights", insights_desc or "No insights available."),
                        ("Knowledge Base", info_samples or "No information samples available."),
                    ),
                ),
                temperature=0.5,
                budget=ctx.budget,
            )

            if not isinstance(result, dict):
                return []

            zettels_data = result.get("zettels", [])
            return [
                ZettelkastenNote(
                    id=f"z{uuid.uuid4().hex[:6]}",
                    title=z.get("title", "Untitled"),
                    content=z.get("content", ""),
                    tags=z.get("tags", []),
                    links_to=z.get("links_to", []),
                    confidence=z.get("confidence", 0.5),
                )
                for z in zettels_data
                if isinstance(z, dict) and z.get("title") and len(z.get("content", "")) > 100
            ]
        except Exception as exc:
            logger.debug("[DIKIWI] Wisdom synthesis failed: %s", exc)
            return []

    def _find_stage_result(self, ctx: AgentContext, stage: DikiwiStage) -> StageResult | None:
        for result in ctx.stage_results:
            if result.stage == stage:
                return result
        return None
