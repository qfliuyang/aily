#!/usr/bin/env python3
"""Batch processor for Aily Chaos - Handle large file volumes."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path.home() / ".aily_chaos_batch.log"),
    ],
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.chaos.config import ChaosConfig
from aily.chaos.processor import ChaosProcessor
from aily.chaos.types import ProcessingJob, ProcessingStatus
from aily.config import SETTINGS


@dataclass
class BatchState:
    """Track batch processing state."""

    processed: list[str]
    failed: list[str]
    skipped: list[str]
    start_time: str

    @classmethod
    def load(cls, state_file: Path) -> "BatchState":
        if state_file.exists():
            with open(state_file) as f:
                data = json.load(f)
            return cls(**data)
        return cls(
            processed=[],
            failed=[],
            skipped=[],
            start_time=datetime.now().isoformat(),
        )

    def save(self, state_file: Path):
        with open(state_file, "w") as f:
            json.dump(
                {
                    "processed": self.processed,
                    "failed": self.failed,
                    "skipped": self.skipped,
                    "start_time": self.start_time,
                },
                f,
            )


class BatchProcessor:
    """Process files in batches with rate limiting and resume."""

    def __init__(
        self,
        config: ChaosConfig,
        concurrency: int = 3,
        rate_limit_delay: float = 1.0,
        vault_path: str | None = None,
    ):
        self.config = config
        self.concurrency = concurrency
        self.rate_limit_delay = rate_limit_delay
        self.vault_path = vault_path or SETTINGS.dikiwi_vault_path or SETTINGS.obsidian_vault_path or str(Path.home() / "Documents" / "aily")
        self.state_file = Path.home() / ".aily_chaos_batch_state.json"
        self.state = BatchState.load(self.state_file)
        self.semaphore = asyncio.Semaphore(concurrency)
        self.stats = {"processed": 0, "failed": 0, "skipped": 0, "total": 0}

    def discover_files(self, root: Path) -> list[Path]:
        """Discover processable files."""
        extensions = {".pdf", ".pptx", ".ppt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".md", ".txt"}
        files = []

        for path in root.rglob("*"):
            # Skip hidden files and directories
            if any(part.startswith(".") for part in path.parts):
                continue
            # Skip node_modules
            if "node_modules" in path.parts:
                continue
            # Skip processed folder
            if ".processed" in path.parts or ".failed" in path.parts:
                continue
            # Check extension
            if path.is_file() and path.suffix.lower() in extensions:
                files.append(path)

        return sorted(files)

    async def process_file(self, file_path: Path) -> tuple[str, ProcessingJob | None]:
        """Process a single file with semaphore."""
        async with self.semaphore:
            file_id = str(file_path.relative_to(self.config.watch_folder))

            # Skip if already processed
            if file_id in self.state.processed:
                self.stats["skipped"] += 1
                return "skipped", None

            try:
                processor = ChaosProcessor(self.config, vault_path=self.vault_path)
                job = await processor.process_file(file_path)

                if job.status == ProcessingStatus.COMPLETED:
                    self.state.processed.append(file_id)
                    self.stats["processed"] += 1
                    return "success", job
                else:
                    self.state.failed.append(file_id)
                    self.stats["failed"] += 1
                    return "failed", job

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                self.state.failed.append(file_id)
                self.stats["failed"] += 1
                return "error", None

            finally:
                # Rate limit
                await asyncio.sleep(self.rate_limit_delay)
                # Save state periodically
                if (self.stats["processed"] + self.stats["failed"]) % 10 == 0:
                    self.state.save(self.state_file)

    async def run(self, files: list[Path] | None = None):
        """Run batch processing."""
        if files is None:
            files = self.discover_files(self.config.watch_folder)

        self.stats["total"] = len(files)

        print(f"\n{'='*60}")
        print(f"BATCH CHAOS PROCESSOR")
        print(f"{'='*60}")
        print(f"Files to process: {len(files)}")
        print(f"Already processed: {len(self.state.processed)}")
        print(f"Concurrency: {self.concurrency}")
        print(f"Rate limit: {self.rate_limit_delay}s between files")
        print(f"{'='*60}\n")

        # Create tasks
        tasks = [self.process_file(f) for f in files]

        # Process with progress
        completed = 0
        for coro in asyncio.as_completed(tasks):
            status, job = await coro
            completed += 1

            # Progress bar
            pct = completed / len(files) * 100
            bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
            print(f"\r[{bar}] {pct:.1f}% | ✓{self.stats['processed']} ✗{self.stats['failed']} →{self.stats['skipped']}", end="", flush=True)

        # Final stats
        self.state.save(self.state_file)

        print(f"\n\n{'='*60}")
        print("BATCH COMPLETE")
        print(f"{'='*60}")
        print(f"Processed: {self.stats['processed']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Skipped: {self.stats['skipped']}")
        print(f"Total: {self.stats['total']}")
        print(f"{'='*60}")

        return self.stats


async def main():
    parser = argparse.ArgumentParser(description="Batch process Aily Chaos files")
    parser.add_argument("--folder", "-f", type=str, default="~/aily_chaos")
    parser.add_argument("--concurrency", "-c", type=int, default=3)
    parser.add_argument("--delay", "-d", type=float, default=1.0, help="Seconds between files")
    parser.add_argument("--reset", "-r", action="store_true", help="Reset state and reprocess all")
    parser.add_argument("--dry-run", "-n", action="store_true", help="List files without processing")

    args = parser.parse_args()

    if not (
        os.getenv("KIMI_API_KEY")
        or os.getenv("MOONSHOT_API_KEY")
        or os.getenv("LLM_API_KEY")
    ):
        raise SystemExit("Set KIMI_API_KEY, MOONSHOT_API_KEY, or LLM_API_KEY before running the batch processor.")

    config = ChaosConfig()
    config.watch_folder = Path(args.folder).expanduser()
    config.__post_init__()

    processor = BatchProcessor(config, concurrency=args.concurrency, rate_limit_delay=args.delay)

    # Reset state if requested
    if args.reset and processor.state_file.exists():
        processor.state_file.unlink()
        processor.state = BatchState.load(processor.state_file)
        print("State reset - will process all files")

    # Discover files
    files = processor.discover_files(config.watch_folder)

    if args.dry_run:
        print(f"\nFiles to process ({len(files)} total):")
        for f in files[:20]:
            print(f"  {f.relative_to(config.watch_folder)}")
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more")
        return

    # Run batch
    await processor.run(files)


if __name__ == "__main__":
    asyncio.run(main())
