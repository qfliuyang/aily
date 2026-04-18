#!/usr/bin/env python3
"""Simple standalone script to run Chaos-to-DIKIWI bridge."""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _split_content_into_jobs(content):
    """Expand one extracted content item into multiple DIKIWI jobs when appropriate."""
    from aily.chaos.config import ChaosConfig
    from aily.chaos.processors.document import TextProcessor

    if content.source_type != "url_markdown":
        return [content]
    processor = TextProcessor(ChaosConfig())
    return processor.split_url_import_items(content)


async def process_single_file(json_file: Path, vault_path: Path) -> dict:
    """Process a single JSON file through DIKIWI."""
    from aily.chaos.types import ExtractedContentMultimodal
    from aily.config import SETTINGS
    from aily.graph.db import GraphDB
    from aily.llm.provider_routes import PrimaryLLMRoute
    from aily.sessions.dikiwi_mind import DikiwiMind
    from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter

    # Load JSON
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Create content
    content = ExtractedContentMultimodal(
        text=data.get("text", ""),
        title=data.get("title"),
        source_type=data.get("source_type", "unknown"),
        source_path=Path(data["source_path"]) if data.get("source_path") else None,
        metadata=data.get("metadata", {}),
        tags=data.get("tags", []),
        processing_timestamp=datetime.fromisoformat(data["processing_timestamp"])
        if data.get("processing_timestamp")
        else datetime.now(),
        processing_method=data.get("processing_method", "unknown"),
    )

    # Split multi-URL imports into individual jobs
    jobs = _split_content_into_jobs(content)
    logger.info(
        "Processing %s through DIKIWI as %d job(s)",
        json_file.name,
        len(jobs),
    )

    # Setup LLM
    api_key = os.environ.get("KIMI_API_KEY") or os.environ.get("MOONSHOT_API_KEY") or SETTINGS.kimi_api_key or SETTINGS.llm_api_key
    llm_client = PrimaryLLMRoute.route_kimi(
        api_key=api_key,
        model=SETTINGS.kimi_model,
    )

    # Setup GraphDB (use temp to avoid lock issues)
    graph_db = GraphDB(db_path=vault_path / ".aily" / f"chaos_bridge_{datetime.now():%Y%m%d}.db")
    await graph_db.initialize()

    try:
        # Setup Obsidian writer
        obsidian_writer = DikiwiObsidianWriter(vault_path=vault_path)

        # Setup browser manager for JS-rendered pages (Monica, etc.)
        from aily.browser.manager import BrowserUseManager
        browser_manager = BrowserUseManager()
        await browser_manager.start()

        # Setup DIKIWI mind
        dikiwi_mind = DikiwiMind(
            graph_db=graph_db,
            llm_client=llm_client,
            dikiwi_obsidian_writer=obsidian_writer,
            browser_manager=browser_manager,
        )

        total_zettels = 0
        total_insights = 0
        max_stage = None

        for job in jobs:
            logger.info(f"Processing job: {job.title or 'Untitled'}")

            # Create RainDrop
            content_text = job.text or ""
            if job.title:
                content_text = f"# {job.title}\n\n{content_text}"
            if job.transcript:
                content_text += f"\n\n## Transcript\n\n{job.transcript}"

            from aily.gating.drainage import RainDrop, RainType, StreamType

            drop = RainDrop(
                id="",
                rain_type=RainType.DOCUMENT,
                content=content_text,
                source="chaos_processor",
                source_id=str(job.source_path) if job.source_path else "unknown",
                stream_type=StreamType.EXTRACT_ANALYZE,
                metadata={
                    **job.metadata,
                    "title": job.title,
                    "tags": job.tags,
                },
            )

            # Process
            result = await dikiwi_mind.process_input(drop)

            final_stage = result.final_stage_reached
            zettels = sum(len(sr.data.get("zettels", [])) for sr in result.stage_results if sr.success)
            insights = sum(len(sr.data.get("insights", [])) for sr in result.stage_results if sr.success)

            logger.info(
                "Done: %s -> Stage %s, %d zettels, %d insights",
                job.title or "Untitled",
                final_stage.name if final_stage else "NONE",
                zettels,
                insights,
            )

            total_zettels += zettels
            total_insights += insights
            if max_stage is None and final_stage is not None:
                max_stage = final_stage

        return {
            "file": json_file.name,
            "stage": max_stage.name if max_stage else None,
            "zettels": total_zettels,
            "insights": total_insights,
            "jobs": len(jobs),
        }

    finally:
        try:
            if 'browser_manager' in locals():
                await browser_manager.stop()
        except Exception:
            pass
        await graph_db.close()


async def main():
    from aily.config import SETTINGS

    vault_path = Path(SETTINGS.obsidian_vault_path).expanduser() if SETTINGS.obsidian_vault_path else Path(SETTINGS.dikiwi_vault_path).expanduser()
    processed_folder = Path.home() / "aily_chaos/.processed"
    date_folder = "2026-04-13"
    max_items = 1

    source_dir = processed_folder / date_folder
    if not source_dir.exists():
        logger.error(f"Source directory not found: {source_dir}")
        return

    json_files = list(source_dir.glob("*.json"))
    if max_items:
        json_files = json_files[:max_items]

    logger.info(f"Processing {len(json_files)} files...")

    results = []
    for json_file in json_files:
        try:
            result = await process_single_file(json_file, vault_path)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed {json_file.name}: {e}")
            results.append({"file": json_file.name, "error": str(e)})

    # Summary
    print(f"\n{'='*50}")
    print("Chaos → Zettelkasten Complete")
    print(f"{'='*50}")
    print(f"Total files: {len(results)}")
    total_zettels = sum(r.get("zettels", 0) for r in results)
    total_jobs = sum(r.get("jobs", 1) for r in results)
    print(f"Total jobs: {total_jobs}")
    print(f"Zettels Created: {total_zettels}")


if __name__ == "__main__":
    asyncio.run(main())
