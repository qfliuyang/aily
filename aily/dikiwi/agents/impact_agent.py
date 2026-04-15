"""ImpactAgent - Stage 6: IMPACT actionable outcome generation."""

from __future__ import annotations

import hashlib
import logging
import time

from aily.dikiwi.agents.base import DikiwiAgent
from aily.dikiwi.agents.context import AgentContext
from aily.dikiwi.agents.llm_tools import multi_agent_json
from aily.llm.prompt_registry import DikiwiPromptRegistry
from aily.sessions.dikiwi_mind import DikiwiStage, StageResult, ZettelkastenNote

logger = logging.getLogger(__name__)


class ImpactAgent(DikiwiAgent):
    """Stage 6: Generate actionable outcomes from Zettelkasten notes via producer-reviewer."""

    async def execute(self, ctx: AgentContext) -> StageResult:
        start = time.time()

        try:
            wisdom_result = self._find_stage_result(ctx, DikiwiStage.WISDOM)
            insight_result = self._find_stage_result(ctx, DikiwiStage.INSIGHT)
            if not wisdom_result:
                raise RuntimeError("WISDOM stage result not found in context")

            zettels: list[ZettelkastenNote] = wisdom_result.data.get("zettels", [])
            wisdom_note_ids: list[str] = wisdom_result.data.get("wisdom_note_ids", [])
            insights: list = insight_result.data.get("insights", []) if insight_result else []

            impacts: list[dict] = []
            if zettels:
                impacts = await self._llm_generate_impacts(zettels, ctx)

            # Write impact notes
            if ctx.dikiwi_obsidian_writer and impacts:
                source_paths = ctx.drop.metadata.get("source_paths", [])
                for impact_item in impacts:
                    try:
                        await ctx.dikiwi_obsidian_writer.write_impact_note(
                            impact_item, wisdom_note_ids, ctx.drop, source_paths
                        )
                    except Exception as e:
                        logger.warning("[DIKIWI] Failed to write impact note: %s", e)

            processing_time = (time.time() - start) * 1000

            return StageResult(
                stage=DikiwiStage.IMPACT,
                success=True,
                items_processed=len(zettels),
                items_output=len(impacts),
                processing_time_ms=processing_time,
                data={
                    "impacts": impacts,
                    "ready_for_scheduled_minds": len(impacts) > 0,
                },
            )

        except Exception as exc:
            return StageResult(
                stage=DikiwiStage.IMPACT,
                success=False,
                error_message=str(exc),
                processing_time_ms=(time.time() - start) * 1000,
            )

    async def _llm_generate_impacts(
        self,
        zettels: list[ZettelkastenNote],
        ctx: AgentContext,
    ) -> list[dict]:
        zettels_desc = "\n".join(
            f"- {z.title[:100]}"
            for z in zettels[:3]
        )
        memory_context = DikiwiPromptRegistry.render_memory(ctx.memory, limit=1200)
        messages = DikiwiPromptRegistry.impact(
            zettels_desc=zettels_desc,
            memory_context=memory_context,
        )
        stage_key = f"impact:{hashlib.sha1(zettels_desc.encode('utf-8')).hexdigest()[:8]}"

        try:
            result = await multi_agent_json(
                llm_client=ctx.llm_client,
                stage="impact",
                stage_key=stage_key,
                producer_messages=messages,
                reviewer_messages_factory=lambda draft_json: DikiwiPromptRegistry.review(
                    stage="IMPACT",
                    reviewer_role="Action Editor",
                    objective="Review the proposed impacts and keep only actions that faithfully follow from the extracted knowledge.",
                    output_contract=DikiwiPromptRegistry.IMPACT_CONTRACT,
                    draft_json=draft_json,
                    memory_context=memory_context,
                    review_focus=(
                        "Remove generic actions that are not grounded in the notes.",
                        "Prefer concrete next steps that compound the knowledge system.",
                    ),
                    context_sections=(
                        ("Zettelkasten Principles", zettels_desc or "No zettels available."),
                    ),
                ),
                temperature=0.5,
                budget=ctx.budget,
            )

            if not isinstance(result, dict):
                return []

            impacts = result.get("impacts", [])
            return [
                {
                    "type": imp.get("type", "action"),
                    "description": imp.get("description", ""),
                    "priority": imp.get("priority", "medium"),
                    "rationale": imp.get("rationale", ""),
                    "effort_estimate": imp.get("effort_estimate", "medium"),
                }
                for imp in impacts
                if isinstance(imp, dict)
            ]
        except Exception as exc:
            logger.debug("[DIKIWI] Impact generation failed: %s", exc)
            return []

    def _find_stage_result(self, ctx: AgentContext, stage: DikiwiStage) -> StageResult | None:
        for result in ctx.stage_results:
            if result.stage == stage:
                return result
        return None
