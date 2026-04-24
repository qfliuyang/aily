#!/usr/bin/env python3
"""Fresh test run: clean vault, process chaos files, record LLM calls."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Monkey-patch LLMClient BEFORE anything else imports it
from aily.llm.client import LLMClient

LLM_LOG_PATH = Path("/Users/luzi/code/aily/logs/llm_calls.jsonl")
LLM_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_original_chat_once = LLMClient._chat_once

async def _patched_chat_once(self, messages, temperature, response_format):
    call_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": self.model,
        "temperature": temperature,
        "response_format": response_format is not None,
        "messages": messages,
    }
    try:
        result = await _original_chat_once(self, messages, temperature, response_format)
        call_record["response"] = result
        call_record["success"] = True
    except Exception as exc:
        call_record["error"] = str(exc)
        call_record["success"] = False
        raise
    finally:
        with open(LLM_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(call_record, ensure_ascii=False) + "\n")
    return result

LLMClient._chat_once = _patched_chat_once
print(f"[SETUP] LLM calls will be logged to {LLM_LOG_PATH}")

# Now import the rest
from aily.chaos.dikiwi_bridge import ChaosDikiwiBridge
from aily.config import SETTINGS
from aily.graph.db import GraphDB
from aily.llm.provider_routes import PrimaryLLMRoute
from aily.sessions.dikiwi_mind import DikiwiMind
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter

VAULT_PATH = Path(SETTINGS.obsidian_vault_path).expanduser()
CHAOS_FOLDER = Path.home() / "aily_chaos"
QUEUE_DB_PATH = CHAOS_FOLDER / ".aily_chaos.db"
GRAPH_DB_PATH = VAULT_PATH / ".aily" / "graph.db"


def clean_vault() -> dict:
    """Remove generated notes and reset graph DB."""
    print(f"[CLEAN] Vault path: {VAULT_PATH}")

    removed_md = 0
    removed_dirs = 0

    # Directories that contain generated DIKIWI content
    generated_dirs = [
        VAULT_PATH / "00-Chaos",
        VAULT_PATH / "01-Data",
        VAULT_PATH / "02-Information",
        VAULT_PATH / "03-Knowledge",
        VAULT_PATH / "04-Insight",
        VAULT_PATH / "05-Wisdom",
        VAULT_PATH / "06-Impact",
        VAULT_PATH / "07-Proposal",
        VAULT_PATH / "08-Entrepreneurship",
        VAULT_PATH / "10-Knowledge",
        VAULT_PATH / "20-Innovation",
        VAULT_PATH / "30-Business",
    ]

    for directory in generated_dirs:
        if directory.exists():
            # Remove all .md files recursively, then remove empty dirs
            for subpath in directory.rglob("*"):
                if subpath.is_file() and subpath.suffix == ".md":
                    subpath.unlink()
                    removed_md += 1
            # Remove empty subdirectories
            for subpath in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                if subpath.is_dir() and not any(subpath.iterdir()):
                    subpath.rmdir()
                    removed_dirs += 1

    # Reset graph DB
    graph_reset = False
    if GRAPH_DB_PATH.exists():
        GRAPH_DB_PATH.unlink()
        graph_reset = True

    print(f"[CLEAN] Removed {removed_md} markdown files, {removed_dirs} dirs. Graph DB reset: {graph_reset}")
    return {"removed_md": removed_md, "removed_dirs": removed_dirs, "graph_reset": graph_reset}


def reset_chaos_queue() -> None:
    """Delete chaos queue DB so daemon rescans everything."""
    if QUEUE_DB_PATH.exists():
        QUEUE_DB_PATH.unlink()
        print(f"[CLEAN] Reset chaos queue DB")


def get_vault_status() -> dict:
    """Count files in each vault directory."""
    status = {}
    for subdir in sorted(VAULT_PATH.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            md_count = len(list(subdir.rglob("*.md")))
            status[subdir.name] = md_count
    return status


async def run_test(max_items: int = 5) -> dict:
    clean_vault()
    reset_chaos_queue()

    # Setup DIKIWI mind
    llm_resolver = PrimaryLLMRoute.build_settings_resolver(SETTINGS)
    llm_client = llm_resolver("dikiwi")

    graph_db = GraphDB(db_path=GRAPH_DB_PATH)
    await graph_db.initialize()

    obsidian_writer = DikiwiObsidianWriter(vault_path=VAULT_PATH)

    dikiwi_mind = DikiwiMind(
        graph_db=graph_db,
        llm_client=llm_client,
        llm_client_resolver=llm_resolver,
        dikiwi_obsidian_writer=obsidian_writer,
    )

    bridge = ChaosDikiwiBridge(
        dikiwi_mind=dikiwi_mind,
        processed_folder=CHAOS_FOLDER / ".processed",
    )

    # Process batch from today's processed folder or raw files
    # The bridge process_batch looks in .processed/YYYY-MM-DD
    # Let's also try processing raw files by using the daemon run_once logic
    from scripts.run_chaos_daemon import ChaosDaemon

    daemon = ChaosDaemon()
    daemon._bridge = bridge
    daemon._graph_db = graph_db

    print(f"[RUN] Starting chaos scan and DIKIWI processing (max ~{max_items} items)...")
    start_time = time.monotonic()

    # Scan existing files into queue
    scanned = daemon.scan_existing()
    print(f"[RUN] Scanned {scanned} files into queue")

    processed = 0
    failed = 0
    total_zettels = 0

    for i in range(max_items):
        file_record = daemon.queue.claim_next()
        if not file_record:
            print("[RUN] No more files in queue")
            break

        try:
            records = await daemon._expand_image_session([file_record])
            content_items = []
            for record in records:
                extracted = await daemon._extract_content(record)
                if extracted:
                    jobs = daemon._split_content_into_jobs(extracted)
                    content_items.extend(jobs)

            for item in content_items:
                result = await bridge.process_extracted_content(item)
                if "error" in result:
                    raise RuntimeError(result["error"])
                processed += 1
                total_zettels += int(result.get("zettels_created", 0))
                print(
                    f"  -> {item.title or file_record.filename}: "
                    f"stage={result.get('stage', 'UNKNOWN')}, zettels={result.get('zettels_created', 0)}"
                )

            for record in records:
                daemon.queue.mark_completed(
                    record.id,
                    output_path=str(CHAOS_FOLDER / ".processed"),
                    vault_path=str(VAULT_PATH / "3-Resources" / "Zettelkasten"),
                )
        except Exception as e:
            print(f"  -> FAILED {file_record.filename}: {e}")
            failed += 1

    elapsed = time.monotonic() - start_time

    await graph_db.close()

    vault_status = get_vault_status()
    llm_call_count = 0
    if LLM_LOG_PATH.exists():
        with open(LLM_LOG_PATH, "r", encoding="utf-8") as f:
            llm_call_count = sum(1 for _ in f)

    report = {
        "scanned": scanned,
        "processed": processed,
        "failed": failed,
        "total_zettels": total_zettels,
        "elapsed_seconds": round(elapsed, 2),
        "llm_calls": llm_call_count,
        "vault_status": vault_status,
    }

    print(f"\n[RESULTS] {json.dumps(report, indent=2)}")
    return report


if __name__ == "__main__":
    result = asyncio.run(run_test(max_items=5))
