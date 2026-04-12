#!/usr/bin/env python3
"""Aily Chaos CLI - Process files from aily_chaos folder."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.chaos.config import ChaosConfig
from aily.chaos.processor import ChaosProcessor


def setup_api_key():
    """Setup API key from environment or argument."""
    api_key = os.getenv("ZHIPU_API_KEY") or os.getenv("BIGMODEL_API_KEY")
    if not api_key:
        logger.error("No API key found. Set ZHIPU_API_KEY environment variable.")
        sys.exit(1)
    return api_key


async def process_single(file_path: Path, config: ChaosConfig):
    """Process a single file."""
    processor = ChaosProcessor(config)

    print(f"\n{'='*60}")
    print(f"Processing: {file_path.name}")
    print(f"{'='*60}")

    job = await processor.process_file(file_path)

    if job.status.name == "COMPLETED" and job.extracted:
        print(f"\n✓ Title: {job.extracted.title}")
        print(f"✓ Type: {job.extracted.source_type}")
        print(f"✓ Tags: {job.extracted.tags[:15]}")
        print(f"\nText preview:\n{job.extracted.text[:500]}...")

        # Show output location
        date_folder = job.completed_at.strftime("%Y-%m-%d") if job.completed_at else "unknown"
        output_dir = config.processed_folder / date_folder
        print(f"\n📁 Output saved to: {output_dir}")
    else:
        print(f"\n✗ Failed: {job.error_message}")

    return job


async def watch_mode(config: ChaosConfig):
    """Run in watch mode."""
    processor = ChaosProcessor(config)

    def on_complete(job):
        status = "✓" if job.status.name == "COMPLETED" else "✗"
        print(f"{status} {job.file_path.name}: {len(job.extracted.tags) if job.extracted else 0} tags")

    processor.on_job_completed(on_complete)

    print(f"\n{'='*60}")
    print(f"Aily Chaos Watch Mode")
    print(f"Watching: {config.watch_folder}")
    print(f"Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    await processor.start()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        await processor.stop()


async def list_files(config: ChaosConfig):
    """List files in chaos folder."""
    folder = config.watch_folder

    if not folder.exists():
        print(f"Folder doesn't exist: {folder}")
        return

    files = [f for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")]

    print(f"\nFiles in {folder}:")
    print(f"{'='*60}")

    for f in sorted(files):
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"  {f.name:<50} {size_mb:>8.1f} MB")

    print(f"{'='*60}")
    print(f"Total: {len(files)} files")


async def main():
    """Main CLI."""
    parser = argparse.ArgumentParser(description="Aily Chaos - Multimodal Content Processor")
    parser.add_argument("--folder", "-f", type=str, help="Chaos folder path (default: ~/aily_chaos)")
    parser.add_argument("--api-key", "-k", type=str, help="BigModel API key")

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Process command
    process_parser = subparsers.add_parser("process", help="Process a file")
    process_parser.add_argument("file", type=str, help="File to process")

    # Watch command
    subparsers.add_parser("watch", help="Watch folder for new files")

    # List command
    subparsers.add_parser("list", help="List files in chaos folder")

    args = parser.parse_args()

    # Setup API key
    if args.api_key:
        os.environ["ZHIPU_API_KEY"] = args.api_key
    setup_api_key()

    # Setup config
    config = ChaosConfig()
    if args.folder:
        config.watch_folder = Path(args.folder)
        config.__post_init__()

    # Run command
    if args.command == "process":
        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = config.watch_folder / file_path
        await process_single(file_path, config)

    elif args.command == "watch":
        await watch_mode(config)

    elif args.command == "list":
        await list_files(config)

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
