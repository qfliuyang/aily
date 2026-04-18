"""Batch ingest documents through MinerU directly into 00-Chaos and DIKIWI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from aily.chaos.config import ChaosConfig
from aily.chaos.dikiwi_bridge import ChaosDikiwiBridge
from aily.chaos.processors.mineru_processor import MinerUProcessor, _MinerULocalAPIService
from aily.chaos.types import ExtractedContentMultimodal
from aily.config import SETTINGS
from aily.graph.db import GraphDB
from aily.llm.provider_routes import PrimaryLLMRoute
from aily.sessions.dikiwi_mind import DikiwiMind
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter

logger = logging.getLogger(__name__)


@dataclass
class MinerUBatchItemResult:
    """Processing result for one source document."""

    source_path: str
    title: str | None
    status: str
    error: str | None = None
    stage: str | None = None
    zettels_created: int = 0
    insights: int = 0
    transcript_path: str | None = None
    extraction_md_path: str | None = None
    extraction_json_path: str | None = None


@dataclass
class MinerUBatchSummary:
    """Aggregate batch result."""

    total: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[MinerUBatchItemResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "processed": self.processed,
            "failed": self.failed,
            "skipped": self.skipped,
            "results": [item.__dict__ for item in self.results],
        }


class MinerUChaosBatchRunner:
    """Run a whole folder through MinerU and DIKIWI with one shared runtime."""

    def __init__(
        self,
        *,
        source_folder: Path,
        vault_path: Path,
        processed_folder: Path | None = None,
        run_dikiwi: bool = True,
        skip_existing: bool = False,
    ) -> None:
        self.source_folder = source_folder.expanduser().resolve()
        self.vault_path = vault_path.expanduser().resolve()
        self.processed_folder = (
            processed_folder.expanduser().resolve()
            if processed_folder is not None
            else (self.source_folder / ".processed").resolve()
        )
        self.run_dikiwi = run_dikiwi
        self.skip_existing = skip_existing

        self.config = ChaosConfig(
            watch_folder=self.source_folder,
            processed_folder=self.processed_folder,
            failed_folder=self.source_folder / ".failed",
        )
        self.processor = MinerUProcessor(self.config)

        self._graph_db: GraphDB | None = None
        self._bridge: ChaosDikiwiBridge | None = None

    def discover_files(self) -> list[Path]:
        """Discover MinerU-supported documents under the source folder."""
        files: list[Path] = []
        supported = MinerUProcessor.SUPPORTED_SUFFIXES
        skip_dirs = {".processed", ".failed", ".git", "__pycache__", "node_modules", ".venv", "venv"}

        for path in self.source_folder.rglob("*"):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.parts if part != ".processed"):
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.suffix.lower() in supported:
                files.append(path)

        return sorted(files)

    async def initialize(self) -> None:
        """Initialize the shared DIKIWI runtime when needed."""
        if not self.run_dikiwi or self._bridge is not None:
            return

        api_key = (
            os.getenv("KIMI_API_KEY")
            or os.getenv("MOONSHOT_API_KEY")
            or SETTINGS.kimi_api_key
            or SETTINGS.llm_api_key
        )
        if not api_key:
            raise RuntimeError("Set KIMI_API_KEY, MOONSHOT_API_KEY, or LLM_API_KEY before running DIKIWI.")

        llm_client = PrimaryLLMRoute.route_kimi(
            api_key=api_key,
            model=SETTINGS.kimi_model,
            max_concurrency=SETTINGS.llm_max_concurrency,
            min_interval_seconds=SETTINGS.llm_min_interval_seconds,
        )

        self._graph_db = GraphDB(db_path=SETTINGS.graph_db_path)
        await self._graph_db.initialize()

        obsidian_writer = DikiwiObsidianWriter(vault_path=self.vault_path)
        dikiwi_mind = DikiwiMind(
            graph_db=self._graph_db,
            llm_client=llm_client,
            dikiwi_obsidian_writer=obsidian_writer,
        )
        self._bridge = ChaosDikiwiBridge(dikiwi_mind=dikiwi_mind, processed_folder=self.processed_folder)

    async def close(self) -> None:
        """Close the shared runtime cleanly."""
        if self._graph_db is not None:
            await self._graph_db.close()
            self._graph_db = None
        _MinerULocalAPIService.shared().stop_sync()
        self._bridge = None

    async def run(self, files: list[Path] | None = None, limit: int | None = None) -> MinerUBatchSummary:
        """Run the batch over discovered or explicit files."""
        if files is None:
            files = self.discover_files()
        if limit is not None:
            files = files[:limit]

        summary = MinerUBatchSummary(total=len(files))
        await self.initialize()

        for index, path in enumerate(files, start=1):
            logger.info("MinerU batch %s/%s: %s", index, len(files), path.name)
            result = await self.process_file(path)
            summary.results.append(result)
            if result.status == "ok":
                summary.processed += 1
            elif result.status == "skipped":
                summary.skipped += 1
            else:
                summary.failed += 1

        return summary

    async def process_file(self, source_path: Path) -> MinerUBatchItemResult:
        """Parse one file, write 00-Chaos artifacts, then feed DIKIWI."""
        source_path = source_path.resolve()
        base_name = source_path.stem
        transcript_target = self.vault_path / "00-Chaos" / f"{base_name}.md"
        if self.skip_existing and transcript_target.exists():
            return MinerUBatchItemResult(
                source_path=str(source_path),
                title=base_name,
                status="skipped",
                transcript_path=str(transcript_target),
            )

        extracted = await self.processor.process(source_path)
        if extracted is None:
            return MinerUBatchItemResult(
                source_path=str(source_path),
                title=base_name,
                status="failed",
                error="mineru_extraction_failed",
            )

        saved = self._persist_extraction(extracted, source_path)
        batch_result = MinerUBatchItemResult(
            source_path=str(source_path),
            title=extracted.title,
            status="ok",
            transcript_path=str(saved["transcript_path"]),
            extraction_md_path=str(saved["markdown_path"]),
            extraction_json_path=str(saved["json_path"]),
        )

        if self.run_dikiwi and self._bridge is not None:
            pipeline_result = await self._bridge.process_extracted_content(extracted)
            if "error" in pipeline_result:
                batch_result.status = "failed"
                batch_result.error = str(pipeline_result["error"])
            else:
                batch_result.stage = pipeline_result.get("stage")
                batch_result.zettels_created = int(pipeline_result.get("zettels_created", 0))
                batch_result.insights = int(pipeline_result.get("insights", 0))

        return batch_result

    def _persist_extraction(
        self,
        extracted: ExtractedContentMultimodal,
        source_path: Path,
    ) -> dict[str, Path]:
        """Persist processed JSON/markdown and the 00-Chaos transcript."""
        date_folder = datetime.now().strftime("%Y-%m-%d")
        output_dir = self.processed_folder / date_folder
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = chaos_base_name(extracted, source_path)
        json_path = output_dir / f"{base_name}.json"
        markdown_path = output_dir / f"{base_name}.md"
        transcript_path = self._write_chaos_transcript(extracted, source_path)

        json_path.write_text(
            json.dumps(extracted.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(self._render_processed_markdown(extracted, source_path, base_name), encoding="utf-8")

        return {
            "json_path": json_path,
            "markdown_path": markdown_path,
            "transcript_path": transcript_path,
        }

    def _write_chaos_transcript(
        self,
        extracted: ExtractedContentMultimodal,
        source_path: Path,
    ) -> Path:
        """Write a one-to-one transcript note into 00-Chaos."""
        transcript_dir = self.vault_path / "00-Chaos"
        transcript_dir.mkdir(parents=True, exist_ok=True)

        base_name = chaos_base_name(extracted, source_path)
        transcript_path = transcript_dir / f"{base_name}.md"
        counter = 1
        while transcript_path.exists() and not self.skip_existing:
            transcript_path = transcript_dir / f"{base_name}_{counter}.md"
            counter += 1

        lines = [
            f"# {extracted.title or base_name}",
            "",
            f"**Original File:** {source_path.name}",
            "",
            f"**Type:** {extracted.source_type}",
            "",
            f"**Processed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
            extracted.get_full_text(),
        ]
        transcript_path.write_text("\n".join(lines), encoding="utf-8")
        return transcript_path

    def _render_processed_markdown(
        self,
        extracted: ExtractedContentMultimodal,
        source_path: Path,
        base_name: str,
    ) -> str:
        """Render the audit markdown persisted under .processed."""
        return "\n".join(
            [
                f"# {extracted.title or base_name}",
                "",
                f"**Source:** {source_path.name}",
                "",
                f"**Type:** {extracted.source_type}",
                "",
                f"**Tags:** {', '.join(extracted.tags)}",
                "",
                "---",
                "",
                extracted.get_full_text(),
            ]
        )


def chaos_base_name(extracted: ExtractedContentMultimodal, source_path: Path) -> str:
    """Choose a stable filename for persisted Chaos artifacts."""
    base_name = extracted.metadata.get("chaos_base_name")
    if isinstance(base_name, str) and base_name.strip():
        return base_name.strip()
    if extracted.source_type == "mineru_markdown" and source_path.name.lower() == "full.md":
        return source_path.parent.name
    return source_path.stem
