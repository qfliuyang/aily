#!/usr/bin/env python3
"""Full E2E test: chaos files → extraction → DIKIWI → Reactor → Residual → Entrepreneur.

Usage:
    python scripts/full_e2e_test.py          # all PDFs
    python scripts/full_e2e_test.py --max 5  # first 5 PDFs

Environment:
    EMPTY_VAULT_BEFORE_TEST=1  # rm -rf the entire vault before running
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from aily.chaos.dikiwi_bridge import ChaosDikiwiBridge
from aily.chaos.processors.pdf import PDFProcessor
from aily.chaos.config import ChaosConfig
from aily.config import SETTINGS
from aily.graph.db import GraphDB
from aily.llm.provider_routes import PrimaryLLMRoute
from aily.sessions.dikiwi_mind import DikiwiMind
from aily.sessions.reactor_scheduler import ReactorScheduler
from aily.sessions.entrepreneur_scheduler import EntrepreneurScheduler
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter

VAULT_PATH = Path(SETTINGS.dikiwi_vault_path).expanduser()
GRAPH_DB_PATH = VAULT_PATH / ".aily" / "graph.db"
CHAOS_FOLDER = Path.home() / "aily_chaos"

TEST_RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = Path(__file__).parent.parent / "logs" / "e2e"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"e2e_run_{TEST_RUN_ID}.log"
REPORT_FILE = LOG_DIR / f"e2e_report_{TEST_RUN_ID}.json"

# Set up file logger
file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
file_handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)
root_logger.setLevel(logging.DEBUG)

# Also tee stdout to log
class TeeStream:
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        file_handler.stream.write(data)
        file_handler.stream.flush()

    def flush(self):
        self.stream.flush()
        file_handler.stream.flush()

sys.stdout = TeeStream(sys.stdout)
sys.stderr = TeeStream(sys.stderr)


def clean_vault() -> dict:
    """Remove ALL markdown notes from the vault and reset graph DB."""
    print(f"[CLEAN] Vault path: {VAULT_PATH}")
    removed_md = 0
    removed_dirs = 0

    if VAULT_PATH.exists():
        for subpath in list(VAULT_PATH.rglob("*")):
            if subpath.is_file() and subpath.suffix == ".md":
                subpath.unlink()
                removed_md += 1
        for subpath in sorted(VAULT_PATH.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if subpath.is_dir() and subpath != VAULT_PATH and not any(subpath.iterdir()):
                subpath.rmdir()
                removed_dirs += 1

    graph_reset = False
    if GRAPH_DB_PATH.exists():
        GRAPH_DB_PATH.unlink()
        graph_reset = True

    print(f"[CLEAN] Removed {removed_md} markdown files, {removed_dirs} dirs. Graph DB reset: {graph_reset}")
    return {"removed_md": removed_md, "removed_dirs": removed_dirs, "graph_reset": graph_reset}


def empty_vault_completely() -> None:
    """rm -rf the entire vault directory when EMPTY_VAULT_BEFORE_TEST is set."""
    if VAULT_PATH.exists():
        shutil.rmtree(VAULT_PATH)
        print(f"[EMPTY] Completely removed vault: {VAULT_PATH}")


def get_vault_status() -> dict:
    """Count files in each vault directory."""
    status = {}
    for subdir in sorted(VAULT_PATH.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            md_count = len(list(subdir.rglob("*.md")))
            status[subdir.name] = md_count
    return status


def get_dir_sizes(dir_name: str) -> list[tuple[str, int]]:
    """Get relative paths and sizes of .md files in a directory."""
    d = VAULT_PATH / dir_name
    if not d.exists():
        return []
    files = sorted(d.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [(str(f.relative_to(VAULT_PATH)), f.stat().st_size) for f in files]


async def run_full_e2e(max_pdfs: int | None = None, no_clean: bool = False) -> dict:
    if os.environ.get("EMPTY_VAULT_BEFORE_TEST") == "1":
        empty_vault_completely()

    if not no_clean:
        clean_vault()
    else:
        print("[SKIP] Vault cleaning disabled (--no-clean)")

    api_key = os.environ.get("ZHIPU_API_KEY", SETTINGS.zhipu_api_key)
    llm_client = PrimaryLLMRoute.route_zhipu(
        api_key=api_key,
        model=SETTINGS.zhipu_model,
        max_concurrency=SETTINGS.llm_max_concurrency,
        min_interval_seconds=SETTINGS.llm_min_interval_seconds,
    )

    graph_db = GraphDB(db_path=GRAPH_DB_PATH)
    await graph_db.initialize()

    obsidian_writer = DikiwiObsidianWriter(vault_path=VAULT_PATH)

    dikiwi_mind = DikiwiMind(
        graph_db=graph_db,
        llm_client=llm_client,
        dikiwi_obsidian_writer=obsidian_writer,
    )

    reactor_scheduler = ReactorScheduler(
        graph_db=graph_db,
        llm_client=llm_client,
        obsidian_writer=obsidian_writer,
    )
    entrepreneur_scheduler = EntrepreneurScheduler(
        graph_db=graph_db,
        llm_client=llm_client,
        obsidian_writer=obsidian_writer,
    )
    dikiwi_mind.reactor_scheduler = reactor_scheduler
    dikiwi_mind.entrepreneur_scheduler = entrepreneur_scheduler

    bridge = ChaosDikiwiBridge(
        dikiwi_mind=dikiwi_mind,
        processed_folder=CHAOS_FOLDER / ".processed",
    )

    pdf_dir = CHAOS_FOLDER / "pdf"
    all_pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not all_pdfs:
        print("No PDFs found")
        return {"error": "no pdfs"}

    # Random selection
    random.shuffle(all_pdfs)
    pdf_files = all_pdfs[:max_pdfs] if max_pdfs else all_pdfs

    print(f"\n=== Aily Full E2E Test ({len(pdf_files)} documents) ===")
    print(f"Vault: {VAULT_PATH}")
    print(f"Log: {LOG_FILE}")
    print(f"Report: {REPORT_FILE}")

    config = ChaosConfig()
    processor = PDFProcessor(config=config)

    doc_results: list[dict] = []
    total_start = time.monotonic()

    for idx, pdf_path in enumerate(pdf_files, 1):
        print(f"\n--- Document {idx}/{len(pdf_files)}: {pdf_path.name} ---")
        doc_start = time.monotonic()

        # Chaos extraction
        extracted = await processor.process(pdf_path)
        if not extracted:
            print("  [SKIP] Extraction failed")
            continue

        transcript_dir = VAULT_PATH / "00-Chaos"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / f"{pdf_path.stem}.md"
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(f"# {extracted.title or pdf_path.stem}\n\n")
            f.write(f"**Original File:** {pdf_path.name}\n\n")
            f.write(f"**Type:** {extracted.source_type}\n\n")
            f.write(f"**Processed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(extracted.get_full_text())
        print(f"  00-Chaos transcript: {transcript_path.stat().st_size} bytes")

        # DIKIWI pipeline
        result = await bridge.process_extracted_content(extracted)
        print(f"  DIKIWI stage: {result.get('stage', 'UNKNOWN')}, zettels: {result.get('zettels_created', 0)}")

        usage_after = llm_client.get_usage_stats()
        doc_results.append({
            "pdf": pdf_path.name,
            "stage": result.get("stage"),
            "zettels": result.get("zettels_created", 0),
            "transcript_bytes": transcript_path.stat().st_size,
            "elapsed": round(time.monotonic() - doc_start, 2),
            "tokens": {
                "prompt": usage_after.get("prompt_tokens", 0),
                "completion": usage_after.get("completion_tokens", 0),
                "total": usage_after.get("total_tokens", 0),
            },
        })

    # Run schedulers once after all docs
    print("\n[Reactor] Running innovation evaluation...")
    reactor_start = time.monotonic()
    try:
        context = await reactor_scheduler._gather_context()
        proposals = await reactor_scheduler.evaluate_context(context)
        print(f"  Reactor proposals: {len(proposals)}")
    except Exception as e:
        print(f"  Reactor failed: {e}")
        proposals = []
    reactor_elapsed = round(time.monotonic() - reactor_start, 2)

    print("\n[Residual] MAC loop should have run via DIKIWI mind...")
    # Residual is already executed inside DikiwiMind MAC loop when reactor_scheduler is wired

    print("\n[Entrepreneur] Running business evaluation...")
    entrepreneur_start = time.monotonic()
    try:
        await entrepreneur_scheduler._run_session_wrapper()
        print("  Entrepreneur complete")
    except Exception as e:
        print(f"  Entrepreneur failed: {e}")
    entrepreneur_elapsed = round(time.monotonic() - entrepreneur_start, 2)

    await graph_db.close()

    # Vault inspection
    print("\n=== Vault Output Summary ===")
    vault_status = get_vault_status()
    for folder, count in sorted(vault_status.items()):
        print(f"  {folder}: {count} files")

    # Inspect key directories
    print("\n=== Sample Files ===")
    for dir_name in ["00-Chaos", "01-Data", "05-Wisdom", "07-Proposal", "08-Entrepreneurship"]:
        files = get_dir_sizes(dir_name)[:3]
        if files:
            print(f"\n  {dir_name}:")
            for rel, size in files:
                print(f"    - {rel} ({size} bytes)")

    total_elapsed = round(time.monotonic() - total_start, 2)
    final_usage = llm_client.get_usage_stats()
    print(f"\n=== E2E Test Complete in {total_elapsed}s ===")
    print(f"Total LLM calls: {final_usage.get('calls', 0)}")
    print(f"Total tokens: {final_usage.get('total_tokens', 0)}")

    result = {
        "test_run_id": TEST_RUN_ID,
        "documents": len(doc_results),
        "results": doc_results,
        "elapsed_seconds": total_elapsed,
        "reactor_elapsed_seconds": reactor_elapsed,
        "entrepreneur_elapsed_seconds": entrepreneur_elapsed,
        "vault_status": vault_status,
        "vault_path": str(VAULT_PATH),
        "log_file": str(LOG_FILE),
        "report_file": str(REPORT_FILE),
        "token_usage": {
            "calls": final_usage.get("calls", 0),
            "prompt_tokens": final_usage.get("prompt_tokens", 0),
            "completion_tokens": final_usage.get("completion_tokens", 0),
            "total_tokens": final_usage.get("total_tokens", 0),
        },
    }

    REPORT_FILE.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"Report written to: {REPORT_FILE}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=20, help="Max PDFs to process")
    parser.add_argument("--no-clean", action="store_true", help="Skip vault cleaning (useful for resuming)")
    args = parser.parse_args()
    result = asyncio.run(run_full_e2e(max_pdfs=args.max, no_clean=args.no_clean))
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
