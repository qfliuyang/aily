"""InformationAgent - Stage 2: INFORMATION classification and tagging."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid

from aily.dikiwi.agents.base import DikiwiAgent
from aily.dikiwi.agents.context import AgentContext
from aily.dikiwi.agents.llm_tools import chat_json
from aily.llm.prompt_registry import DikiwiPromptRegistry
from aily.sessions.dikiwi_mind import DataPoint, DikiwiStage, InformationNode, StageResult

logger = logging.getLogger(__name__)


class InformationAgent(DikiwiAgent):
    """Stage 2: Batch classify data points into information nodes."""

    async def execute(self, ctx: AgentContext) -> StageResult:
        start = time.time()

        try:
            # Retrieve prior stage results
            data_result = self._find_stage_result(ctx, DikiwiStage.DATA)
            if not data_result:
                raise RuntimeError("DATA stage result not found in context")

            data_points: list[DataPoint] = data_result.data.get("data_points", [])
            data_note_id: str = data_result.data.get("data_note_id", "")
            data_note_ids: list[str] = data_result.data.get("data_note_ids", [])
            source = ctx.drop.source

            logger.info(
                "[DIKIWI] INFORMATION: %d data points, %d data_note_ids, first=%s",
                len(data_points), len(data_note_ids), data_note_ids[0] if data_note_ids else "(none)"
            )

            classifications = await self._llm_classify_batch(data_points, source, ctx)

            # Build a map from data_point chunk index to the corresponding data note id
            def _dp_to_data_note_id(dp_id: str) -> str:
                """Extract chunk index from dp_id (format: dp_{uuid}_{chunk_index}_{i}) and look up data_note_id."""
                if not data_note_ids:
                    logger.warning("[DIKIWI] data_note_ids is empty, falling back to data_note_id=%s", data_note_id)
                    return data_note_id
                parts = dp_id.split("_")
                if len(parts) >= 3:
                    try:
                        chunk_idx = int(parts[-2])
                        if 0 <= chunk_idx < len(data_note_ids):
                            return data_note_ids[chunk_idx]
                    except ValueError:
                        pass
                logger.warning("[DIKIWI] Could not map dp_id=%s to data_note_id", dp_id)
                return data_note_id

            info_nodes: list[InformationNode] = []
            for dp, cls in zip(data_points, classifications):
                node = InformationNode(
                    id=f"info_{uuid.uuid4().hex[:8]}",
                    data_point_id=dp.id,
                    content=dp.content,
                    concept=dp.concept,
                    tags=cls.get("tags", []),
                    info_type=cls.get("info_type", "fact"),
                    domain=self._clean_domain(cls.get("domain", "general")),
                )
                info_nodes.append(node)

                if ctx.graph_db:
                    await ctx.graph_db.insert_node(
                        node_id=node.id,
                        node_type="information",
                        label=node.content[:200],
                        source=source,
                    )
                    await self._store_node_metadata(node, ctx)

            # Write information notes
            info_note_ids: dict[str, str] = {}
            if ctx.dikiwi_obsidian_writer and info_nodes:
                source_paths = ctx.drop.metadata.get("source_paths", [])
                for node in info_nodes:
                    try:
                        # Link to the specific data chunk this concept was extracted from
                        specific_data_note_id = _dp_to_data_note_id(node.data_point_id)
                        nid = await ctx.dikiwi_obsidian_writer.write_information_note(
                            node, specific_data_note_id, source, source_paths, data_point_id=node.data_point_id
                        )
                        info_note_ids[node.id] = nid
                    except Exception as e:
                        logger.warning("[DIKIWI] Failed to write information note: %s", e)

            # Add to memory
            if ctx.memory and info_nodes:
                ctx.memory.add_assistant(
                    f"STAGE 2 (INFORMATION) Complete: Classified {len(info_nodes)} information nodes. "
                    f"Domains: {', '.join(node.domain for node in info_nodes[:4])}"
                )

            processing_time = (time.time() - start) * 1000

            keywords = list({tag for node in info_nodes for tag in node.tags})

            return StageResult(
                stage=DikiwiStage.INFORMATION,
                success=True,
                items_processed=len(data_points),
                items_output=len(info_nodes),
                processing_time_ms=processing_time,
                data={
                    "information_nodes": info_nodes,
                    "info_note_ids": info_note_ids,
                    "keywords": keywords,
                },
            )

        except Exception as exc:
            return StageResult(
                stage=DikiwiStage.INFORMATION,
                success=False,
                error_message=str(exc),
                processing_time_ms=(time.time() - start) * 1000,
            )

    async def _llm_classify_batch(
        self,
        data_points: list[DataPoint],
        source: str,
        ctx: AgentContext,
    ) -> list[dict]:
        if not data_points:
            return []

        memory_context = DikiwiPromptRegistry.render_memory(ctx.memory, limit=1200)
        messages = DikiwiPromptRegistry.classification_batch(
            data_points=data_points,
            source=source,
            memory_context=memory_context,
        )
        stage_key = f"information:batch:{hashlib.sha1(source.encode('utf-8')).hexdigest()[:8]}"

        fallback = [
            {"tags": [], "info_type": "fact", "domain": "general", "confidence": 0.8}
        ] * len(data_points)

        try:
            result = await chat_json(
                llm_client=ctx.llm_client,
                stage="information",
                stage_key=stage_key,
                messages=messages,
                temperature=0.2,
                budget=ctx.budget,
            )
        except Exception as exc:
            logger.warning("[DIKIWI] Batch classification failed: %s", exc)
            return fallback

        if not isinstance(result, dict):
            return fallback

        raw_list = result.get("classifications", [])
        index_map: dict[int, dict] = {}
        for item in raw_list:
            if isinstance(item, dict):
                idx = item.get("index")
                if isinstance(idx, int):
                    index_map[idx] = item

        return [
            {
                "tags": index_map.get(i, {}).get("tags", [])[:5],
                "info_type": index_map.get(i, {}).get("info_type", "fact"),
                "domain": self._clean_domain(index_map.get(i, {}).get("domain", "general")),
                "confidence": float(index_map.get(i, {}).get("confidence", 0.8)),
            }
            for i in range(len(data_points))
        ]

    async def _store_node_metadata(self, node: InformationNode, ctx: AgentContext) -> None:
        if not ctx.graph_db:
            return
        source_paths = ctx.drop.metadata.get("source_paths", []) if getattr(ctx.drop, "metadata", None) else []
        try:
            await ctx.graph_db.set_node_property(node.id, "data_point_id", node.data_point_id)
            await ctx.graph_db.set_node_property(node.id, "concept", node.concept)
            await ctx.graph_db.set_node_property(node.id, "tags", node.tags)
            await ctx.graph_db.set_node_property(node.id, "info_type", node.info_type)
            await ctx.graph_db.set_node_property(node.id, "domain", node.domain)
            await ctx.graph_db.set_node_property(node.id, "source_paths", source_paths)
            await ctx.graph_db.set_node_property(node.id, "pipeline_id", ctx.pipeline_id)
        except AttributeError:
            # Older tests use AsyncMock GraphDBs without property APIs.
            pass
        for tag in node.tags:
            await ctx.graph_db.insert_node(
                node_id=f"tag_{tag}", node_type="tag", label=tag, source="dikiwi"
            )
            await ctx.graph_db.insert_edge(
                edge_id=f"edge_{uuid.uuid4().hex[:8]}",
                source_node_id=node.id,
                target_node_id=f"tag_{tag}",
                relation_type="has_tag",
                source="dikiwi",
                weight=1.0,
            )
        try:
            raw_log_id = str(source_paths[0]) if source_paths else ctx.pipeline_id
            await ctx.graph_db.insert_occurrence(
                occurrence_id=f"occ_{uuid.uuid4().hex[:8]}",
                node_id=node.id,
                raw_log_id=raw_log_id,
            )
        except AttributeError:
            pass

    @staticmethod
    def _clean_domain(domain: str) -> str:
        return domain.split("|")[0].strip() if "|" in domain else domain.strip()

    def _find_stage_result(self, ctx: AgentContext, stage: DikiwiStage) -> StageResult | None:
        for result in ctx.stage_results:
            if result.stage == stage:
                return result
        return None
