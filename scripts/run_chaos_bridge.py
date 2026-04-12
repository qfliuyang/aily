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


async def process_single_file(json_file: Path, vault_path: Path) -> dict:
    """Process a single JSON file through DIKIWI."""
    from aily.chaos.types import ExtractedContentMultimodal
    from aily.gating.drainage import RainDrop, RainType, StreamType
    from aily.graph.db import GraphDB
    from aily.config import SETTINGS
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

    logger.info(f"Processing: {content.title or 'Untitled'}")

    # Create RainDrop
    content_text = content.text or ""
    if content.title:
        content_text = f"# {content.title}\n\n{content_text}"
    if content.transcript:
        content_text += f"\n\n## Transcript\n\n{content.transcript}"

    drop = RainDrop(
        id="",
        rain_type=RainType.DOCUMENT,
        content=content_text,
        source="chaos_processor",
        source_id=str(content.source_path) if content.source_path else "unknown",
        stream_type=StreamType.EXTRACT_ANALYZE,
        metadata={
            **content.metadata,
            "title": content.title,
            "tags": content.tags,
        },
    )

    # Setup LLM
    api_key = os.environ.get("ZHIPU_API_KEY", SETTINGS.zhipu_api_key)
    llm_client = PrimaryLLMRoute.route_zhipu(
        api_key=api_key,
        model=SETTINGS.zhipu_model,
    )

    # Setup GraphDB (use temp to avoid lock issues)
    graph_db = GraphDB(db_path=vault_path / ".aily" / f"chaos_bridge_{datetime.now():%Y%m%d}.db")
    await graph_db.initialize()

    try:
        # Setup Obsidian writer
        obsidian_writer = DikiwiObsidianWriter(vault_path=vault_path)

        # Setup DIKIWI mind
        dikiwi_mind = DikiwiMind(
            graph_db=graph_db,
            llm_client=llm_client,
            dikiwi_obsidian_writer=obsidian_writer,
        )

        # Process
        result = await dikiwi_mind.process_input(drop)

        final_stage = result.final_stage_reached
        zettels = sum(len(sr.data.get("zettels", [])) for sr in result.stage_results if sr.success)
        insights = sum(len(sr.data.get("insights", [])) for sr in result.stage_results if sr.success)

        logger.info(f"Done: {content.title} -> Stage {final_stage.name if final_stage else 'NONE'}, {zettels} zettels, {insights} insights")

        return {
            "file": json_file.name,
            "stage": final_stage.name if final_stage else None,
            "zettels": zettels,
            "insights": insights,
        }

    finally:
        await graph_db.close()


async def main():
    from aily.config import SETTINGS

    vault_path = Path(SETTINGS.obsidian_vault_path).expanduser() if SETTINGS.obsidian_vault_path else (Path.home() / "Documents/Obsidian Vault")
    processed_folder = Path.home() / "aily_chaos/.processed"
    date_folder = "2026-04-12"
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
    print(f"Total: {len(results)}")
    total_zettels = sum(r.get("zettels", 0) for r in results)
    print(f"Zettels Created: {total_zettels}")


if __name__ == "__main__":
    asyncio.run(main())
