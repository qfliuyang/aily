#!/usr/bin/env python3
"""Batch-ingest a folder through MinerU directly into 00-Chaos and DIKIWI."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.chaos.mineru_batch import MinerUChaosBatchRunner
from aily.config import SETTINGS


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run a folder through MinerU -> 00-Chaos -> DIKIWI")
    parser.add_argument("--folder", "-f", type=Path, default=Path.home() / "aily_chaos")
    parser.add_argument(
        "--vault",
        "-v",
        type=Path,
        default=Path(SETTINGS.dikiwi_vault_path or SETTINGS.obsidian_vault_path or "~/Documents/aily").expanduser(),
    )
    parser.add_argument("--processed-folder", type=Path, default=None)
    parser.add_argument("--limit", "-n", type=int, default=None)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--no-dikiwi", action="store_true", help="Only write 00-Chaos and .processed artifacts")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary-file", type=Path, default=None)
    args = parser.parse_args()

    runner = MinerUChaosBatchRunner(
        source_folder=args.folder,
        vault_path=args.vault,
        processed_folder=args.processed_folder,
        run_dikiwi=not args.no_dikiwi,
        skip_existing=args.skip_existing,
    )

    files = runner.discover_files()
    if args.limit is not None:
        files = files[: args.limit]

    if args.dry_run:
        print(json.dumps({"count": len(files), "files": [str(path) for path in files]}, ensure_ascii=False, indent=2))
        return

    try:
        summary = await runner.run(files=files)
    finally:
        await runner.close()

    payload = summary.to_dict()
    if args.summary_file is not None:
        args.summary_file.parent.mkdir(parents=True, exist_ok=True)
        args.summary_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
