"""DataAgent - Stage 1: DATA extraction and markdownization."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from typing import TYPE_CHECKING

from aily.dikiwi.agents.base import DikiwiAgent
from aily.dikiwi.agents.context import AgentContext
from aily.dikiwi.agents.llm_tools import chat_json
from aily.llm.prompt_registry import DikiwiPromptRegistry
from aily.sessions.dikiwi_mind import DikiwiStage, StageResult

if TYPE_CHECKING:
    from aily.sessions.dikiwi_mind import DataPoint

logger = logging.getLogger(__name__)


class DataAgent(DikiwiAgent):
    """Stage 1: Extract concept-level data points from raw content."""

    _LONG_DOC_THRESHOLD = 5000
    _CHUNK_SIZE = 4000
    _MAX_CHUNKS = 8

    async def execute(self, ctx: AgentContext) -> StageResult:
        start = time.time()

        try:
            drop = await self._markdownize_drop(ctx)
            content = drop.content

            # Content quality gate: skip LLM extraction on obviously thin content
            quality_check = self._assess_content_quality(content)
            if quality_check["is_too_thin"]:
                logger.warning(
                    "[DIKIWI] Content quality too low for %s: %s",
                    drop.source,
                    quality_check["reason"],
                )
                processing_time = (time.time() - start) * 1000
                return StageResult(
                    stage=DikiwiStage.DATA,
                    success=True,
                    items_processed=1,
                    items_output=0,
                    processing_time_ms=processing_time,
                    data={
                        "data_points": [],
                        "doc_title": "",
                        "doc_summary": "",
                        "data_note_id": "",
                        "quality_assessment": "low",
                        "quality_reason": quality_check["reason"],
                    },
                )

            # Add input to memory
            if ctx.memory:
                ctx.memory.add_user(f"Input to process:\n{content[:3000]}")

            all_data_points: list[DataPoint] = []
            doc_title = ""
            doc_summary = ""

            if len(content) > self._LONG_DOC_THRESHOLD:
                chunks = self._chunk_content(content, self._CHUNK_SIZE)
                logger.info(
                    "[DIKIWI] Long doc (%d chars) split into %d chunks",
                    len(content),
                    min(len(chunks), self._MAX_CHUNKS),
                )
                existing_concepts: list[str] = []
                for i, chunk in enumerate(chunks[: self._MAX_CHUNKS]):
                    dps, meta = await self._llm_extract_chunk(
                        chunk, drop.source, ctx, chunk_index=i, existing_concepts=existing_concepts
                    )
                    all_data_points.extend(dps)
                    existing_concepts.extend(dp.concept for dp in dps if dp.concept)
                    if i == 0:
                        doc_title = meta.get("title", "")
                        doc_summary = meta.get("summary", "")
            else:
                dps, meta = await self._llm_extract_chunk(
                    content, drop.source, ctx, chunk_index=0
                )
                all_data_points.extend(dps)
                doc_title = meta.get("title", "")
                doc_summary = meta.get("summary", "")

            # Let quality gates filter ideas naturally; do not artificially cap volume
            data_points = all_data_points
            if not data_points:
                data_points = await self._llm_fallback_extraction(content, drop.source, ctx)

            processing_time = (time.time() - start) * 1000

            if ctx.memory:
                ctx.memory.add_assistant(
                    f"STAGE 1 (DATA) Complete: Extracted {len(data_points)} concepts. "
                    f"Examples: {', '.join(dp.concept or dp.content[:50] for dp in data_points[:3])}..."
                )

            # Build raw content chunks for 01-Data (unclassified datapoints)
            raw_chunks = self._chunk_content(content, chunk_size=800)

            # Write raw unclassified chunks to 01-Data
            data_note_paths: list[str] = []
            if ctx.dikiwi_obsidian_writer:
                try:
                    paths = await ctx.dikiwi_obsidian_writer.write_raw_data_chunks(
                        message_id=ctx.pipeline_id,
                        chunks=raw_chunks,
                        source=drop.source,
                    )
                    data_note_paths = [str(p) for p in paths]
                except Exception as e:
                    logger.warning("[DIKIWI] Failed to write raw data chunks: %s", e)

            return StageResult(
                stage=DikiwiStage.DATA,
                success=True,
                items_processed=1,
                items_output=len(data_points),
                processing_time_ms=processing_time,
                data={
                    "data_points": data_points,
                    "doc_title": doc_title,
                    "doc_summary": doc_summary,
                    "data_note_paths": data_note_paths,
                },
            )

        except Exception as exc:
            return StageResult(
                stage=DikiwiStage.DATA,
                success=False,
                error_message=str(exc),
                processing_time_ms=(time.time() - start) * 1000,
            )

    async def _markdownize_drop(self, ctx: AgentContext):
        from dataclasses import replace, is_dataclass
        import re

        drop = ctx.drop
        metadata = getattr(drop, "metadata", {})
        if (
            metadata.get("source_type") == "url_markdown"
            or metadata.get("processing_method") == "browser_url_markdown_fetch"
        ):
            logger.info("[DIKIWI] Skipping markdownize for pre-fetched URL markdown")
            return drop

        content = drop.content
        # Extract URLs from markdown links/images first
        md_urls = re.findall(r"!\[.*?\]\((https?://[^\)]+)\)", content)
        md_urls += re.findall(r"\[.*?\]\((https?://[^\)]+)\)", content)
        # Extract bare URLs, stopping at common markdown delimiters
        bare_urls = re.findall(r"https?://[^\s\)\]\>\"']+", content)
        urls = []
        for url in md_urls + bare_urls:
            # Final cleanup: strip trailing punctuation
            url = url.rstrip(").,;:!?*\"']")
            if url and url not in urls:
                urls.append(url)
        if not urls:
            return drop

        logger.info("[DIKIWI] Markdownizing %d URLs", len(urls))
        markdown_parts = []
        for url in urls:
            try:
                md_content = await ctx.markdownizer.process_url(url)
                if md_content.markdown:
                    markdown_parts.append(f"## Content from {url}\n\n{md_content.markdown}")
                else:
                    markdown_parts.append(f"## {url}\n\n[Could not extract content]")
            except Exception as e:
                logger.warning("[DIKIWI] Failed to markdownize %s: %s", url, e)
                markdown_parts.append(f"## {url}\n\n[Error: {e}]")

        text_without_urls = re.sub(r"https?://\S+", "", content).strip()
        combined = []
        if text_without_urls:
            # Only include original text if it's meaningful (not a landing-page wrapper)
            quality = self._assess_content_quality(text_without_urls)
            if not quality["is_too_thin"]:
                combined.append(f"## User Message\n\n{text_without_urls}")
            else:
                logger.info("[DIKIWI] Omitting thin original text: %s", quality["reason"])
        combined.extend(markdown_parts)
        markdownized_content = "\n\n---\n\n".join(combined)
        if is_dataclass(drop):
            return replace(drop, content=markdownized_content)
        drop.content = markdownized_content
        return drop

    @staticmethod
    def _assess_content_quality(content: str) -> dict[str, str | bool]:
        """Fast heuristic to detect landing-page or wrapper content with no substance."""
        import re

        text = re.sub(r"https?://\S+", "", content)
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"[#*_`>\-|]+", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) < 200:
            return {"is_too_thin": True, "reason": f"Text too short ({len(text)} chars) after stripping markup"}

        # Generic landing-page markers that indicate no real content was fetched
        generic_markers = [
            "monica - your gpt ai assistant chrome extension",
            "monicamarch",
            "download#",
            "continue in chat",
            "sharecontinue in chat",
            "checking your browser",
            "just a moment",
            "access denied",
        ]
        lower = text.lower()
        marker_hits = sum(1 for m in generic_markers if m in lower)
        if marker_hits >= 2:
            return {"is_too_thin": True, "reason": f"Detected {marker_hits} generic landing-page markers"}

        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        meaningful = [p for p in paragraphs if len(p) > 60 and not p.startswith("!") and not p.startswith("[")]
        if len(meaningful) < 2:
            return {"is_too_thin": True, "reason": f"Only {len(meaningful)} meaningful paragraphs found"}

        avg_para_len = sum(len(p) for p in meaningful) / max(len(meaningful), 1)
        if avg_para_len < 80:
            return {"is_too_thin": True, "reason": f"Average paragraph length too short ({avg_para_len:.0f} chars)"}

        return {"is_too_thin": False, "reason": "ok"}

    @staticmethod
    def _chunk_content(content: str, chunk_size: int = 4000) -> list[str]:
        if len(content) <= chunk_size:
            return [content]
        paragraphs = content.split("\n\n")
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for para in paragraphs:
            para_len = len(para) + 2
            if current_len + para_len > chunk_size and current:
                chunks.append("\n\n".join(current))
                overlap_target = chunk_size // 10
                overlap: list[str] = []
                overlap_len = 0
                for p in reversed(current):
                    if overlap_len + len(p) > overlap_target:
                        break
                    overlap.insert(0, p)
                    overlap_len += len(p) + 2
                current = overlap
                current_len = overlap_len
            current.append(para)
            current_len += para_len
        if current:
            chunks.append("\n\n".join(current))
        return chunks

    async def _llm_extract_chunk(
        self,
        content: str,
        source: str,
        ctx: AgentContext,
        chunk_index: int = 0,
        existing_concepts: list[str] | None = None,
    ):
        from aily.sessions.dikiwi_mind import DataPoint

        memory_context = (
            DikiwiPromptRegistry.render_memory(ctx.memory, limit=1200)
            if ctx.memory
            else ""
        )
        messages = DikiwiPromptRegistry.data_extraction(
            source=source,
            content=content,
            memory_context=memory_context,
            existing_concepts=existing_concepts or [],
        )
        stage_key = f"data:chunk{chunk_index}:{hashlib.sha1(content[:200].encode()).hexdigest()[:8]}"

        try:
            result = await chat_json(
                llm_client=ctx.llm_client,
                stage="data",
                stage_key=stage_key,
                messages=messages,
                temperature=0.2,
                budget=ctx.budget,
            )
        except Exception as exc:
            logger.warning("[DIKIWI] Chunk %d extraction failed: %s", chunk_index, exc)
            return [], {}

        if not isinstance(result, dict):
            return [], {}

        meta = {
            "title": str(result.get("title", "")),
            "summary": str(result.get("summary", "")),
        }
        data_points: list[DataPoint] = []
        for i, pd in enumerate(result.get("data_points", [])):
            if not isinstance(pd, dict) or not pd.get("content"):
                continue
            data_points.append(
                DataPoint(
                    id=f"dp_{uuid.uuid4().hex[:8]}_{chunk_index}_{i}",
                    content=pd["content"].strip(),
                    context=pd.get("context", ""),
                    source=source,
                    confidence=float(pd.get("confidence", 0.8)),
                    concept=str(pd.get("concept", "")),
                )
            )
        return data_points, meta

    async def _llm_fallback_extraction(self, content: str, source: str, ctx: AgentContext):
        from aily.sessions.dikiwi_mind import DataPoint

        messages = DikiwiPromptRegistry.fallback_extraction(
            source=source,
            content_preview=f"{content[:2000]}...",
        )
        try:
            result = await chat_json(
                llm_client=ctx.llm_client,
                stage="data_fallback",
                stage_key=f"data_fallback:{hashlib.sha1(source.encode('utf-8')).hexdigest()[:8]}",
                messages=messages,
                temperature=0.3,
                budget=ctx.budget,
            )
            if isinstance(result, dict):
                summary = result.get("summary") or result.get("key_takeaway", "")
                if summary:
                    return [
                        DataPoint(
                            id=f"dp_{uuid.uuid4().hex[:8]}",
                            content=summary,
                            source=source,
                            confidence=result.get("confidence", 0.5),
                        )
                    ]
        except Exception:
            pass
        return [
            DataPoint(
                id=f"dp_{uuid.uuid4().hex[:8]}",
                content=f"[Content from {source} - extraction failed, manual review needed]",
                source=source,
                confidence=0.0,
            )
        ]
