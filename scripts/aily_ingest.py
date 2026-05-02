#!/usr/bin/env python3
"""Daily incremental ingestion — watch for new files and process via DIKIWI.

Usage:
  # One-shot: process all markdown files in a Chaos folder
  python scripts/aily_ingest.py --chaos-dir ~/aily_chaos/new

  # Watch mode: continuously monitor for new files
  python scripts/aily_ingest.py --watch --chaos-dir ~/aily_chaos/new

  # Force full pipeline (bypass graph threshold)
  python scripts/aily_ingest.py --force --chaos-dir ~/aily_chaos/new

  # Specify vault path
  python scripts/aily_ingest.py --vault /path/to/vault --chaos-dir ~/aily_chaos/new
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.config import SETTINGS
from aily.graph.db import GraphDB
from aily.llm.provider_routes import PrimaryLLMRoute
from aily.sessions.dikiwi_mind import DikiwiMind
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aily_ingest")


async def ingest_once(
    dikiwi_mind: DikiwiMind,
    chaos_dir: Path,
    processed_dir: Path | None = None,
    *,
    force: bool = False,
) -> dict:
    """Process all markdown files in chaos_dir through incremental DIKIWI."""
    if not chaos_dir.exists():
        return {"error": f"Chaos directory not found: {chaos_dir}"}

    md_files = sorted(chaos_dir.glob("*.md"))
    if not md_files:
        logger.info("No markdown files found in %s", chaos_dir)
        return {"processed": 0, "reason": "no_files"}

    logger.info("Starting incremental ingest of %d files (force=%s)", len(md_files), force)
    t0 = time.monotonic()
    result = await dikiwi_mind.process_input_incremental(md_files, force=force)
    elapsed = time.monotonic() - t0

    if processed_dir and result.new_info_nodes > 0:
        processed_dir.mkdir(parents=True, exist_ok=True)
        for f in md_files:
            dest = processed_dir / f.name
            if not dest.exists():
                f.rename(dest)

    summary = {
        "new_files": result.new_files,
        "new_info_nodes": result.new_info_nodes,
        "affected_subgraphs": result.affected_subgraphs,
        "stale": {"insights": result.stale_insights, "wisdom": result.stale_wisdom, "impacts": result.stale_impacts},
        "regenerated": {"insights": result.regenerated_insights, "wisdom": result.regenerated_wisdom, "impacts": result.regenerated_impacts},
        "skipped": {"insights": result.skipped_insights, "wisdom": result.skipped_wisdom, "impacts": result.skipped_impacts},
        "elapsed_seconds": round(elapsed, 2),
    }

    logger.info("Ingest complete: %d new info nodes, %d affected subgraphs, %.0fs",
                result.new_info_nodes, result.affected_subgraphs, elapsed)
    return summary


async def watch_loop(
    dikiwi_mind: DikiwiMind,
    chaos_dir: Path,
    poll_seconds: int = 30,
    processed_dir: Path | None = None,
) -> None:
    """Continuously watch chaos_dir for new markdown files."""
    logger.info("Watching %s every %ds for new files...", chaos_dir, poll_seconds)
    seen: set[str] = set()

    while True:
        try:
            md_files = sorted(chaos_dir.glob("*.md"))
            new_files = [f for f in md_files if f.name not in seen]

            if new_files:
                logger.info("Found %d new file(s), processing...", len(new_files))
                result = await ingest_once(dikiwi_mind, chaos_dir, processed_dir)
                logger.info("Result: %s", json.dumps(result, default=str))
                for f in new_files:
                    seen.add(f.name)

            await asyncio.sleep(poll_seconds)

        except KeyboardInterrupt:
            logger.info("Watch stopped by user")
            break
        except Exception as exc:
            logger.exception("Watch loop error: %s", exc)
            await asyncio.sleep(poll_seconds)


async def main():
    parser = argparse.ArgumentParser(description="Aily daily incremental ingestion")
    parser.add_argument("--chaos-dir", type=Path, required=True, help="Directory with markdown files to process")
    parser.add_argument("--vault", type=Path, help="Obsidian vault path")
    parser.add_argument("--watch", action="store_true", help="Watch mode: poll for new files")
    parser.add_argument("--poll", type=int, default=30, help="Poll interval in seconds (watch mode)")
    parser.add_argument("--force", action="store_true", help="Bypass graph threshold — always run full pipeline")
    parser.add_argument("--processed-dir", type=Path, help="Move processed files here after ingestion")
    args = parser.parse_args()

    vault_path = args.vault or Path(SETTINGS.dikiwi_vault_path or SETTINGS.obsidian_vault_path).expanduser()

    # Ensure API key
    os.environ.setdefault("KIMI_API_KEY", SETTINGS.kimi_api_key or SETTINGS.llm_api_key or "")

    llm_client = PrimaryLLMRoute.route_kimi(
        api_key=os.environ["KIMI_API_KEY"],
        model=SETTINGS.kimi_model,
        max_concurrency=SETTINGS.llm_max_concurrency,
        min_interval_seconds=SETTINGS.llm_min_interval_seconds,
    )

    graph_db = GraphDB(db_path=vault_path / ".aily" / "graph.db")
    await graph_db.initialize()

    obsidian_writer = DikiwiObsidianWriter(vault_path=vault_path)

    dikiwi_mind = DikiwiMind(
        graph_db=graph_db,
        llm_client=llm_client,
        dikiwi_obsidian_writer=obsidian_writer,
    )

    try:
        if args.watch:
            await watch_loop(dikiwi_mind, args.chaos_dir, args.poll, args.processed_dir)
        else:
            result = await ingest_once(dikiwi_mind, args.chaos_dir, args.processed_dir, force=args.force)
            print(json.dumps(result, indent=2, default=str))
    finally:
        await graph_db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
