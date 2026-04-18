#!/usr/bin/env python3
"""Fresh test run with actual PDF content: clean vault, process PDFs, record LLM calls."""

from __future__ import annotations

import asyncio
import json
import os
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

# Clear previous log
if LLM_LOG_PATH.exists():
    LLM_LOG_PATH.unlink()

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
from aily.chaos.processors.pdf import PDFProcessor
from aily.chaos.config import ChaosConfig
from aily.config import SETTINGS
from aily.graph.db import GraphDB
from aily.llm.provider_routes import PrimaryLLMRoute
from aily.sessions.dikiwi_mind import DikiwiMind
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter

VAULT_PATH = Path(SETTINGS.obsidian_vault_path).expanduser()
GRAPH_DB_PATH = VAULT_PATH / ".aily" / "graph.db"


def clean_vault() -> dict:
    """Remove generated notes and reset graph DB."""
    print(f"[CLEAN] Vault path: {VAULT_PATH}")

    removed_md = 0
    removed_dirs = 0

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
            for subpath in list(directory.rglob("*")):
                if subpath.is_file() and subpath.suffix == ".md":
                    subpath.unlink()
                    removed_md += 1
            for subpath in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                if subpath.is_dir() and not any(subpath.iterdir()):
                    subpath.rmdir()
                    removed_dirs += 1

    graph_reset = False
    if GRAPH_DB_PATH.exists():
        GRAPH_DB_PATH.unlink()
        graph_reset = True

    print(f"[CLEAN] Removed {removed_md} markdown files, {removed_dirs} dirs. Graph DB reset: {graph_reset}")
    return {"removed_md": removed_md, "removed_dirs": removed_dirs, "graph_reset": graph_reset}


def get_vault_status() -> dict:
    """Count files in each vault directory."""
    status = {}
    for subdir in sorted(VAULT_PATH.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            md_count = len(list(subdir.rglob("*.md")))
            status[subdir.name] = md_count
    return status


async def process_pdf(pdf_path: Path, bridge: ChaosDikiwiBridge) -> dict:
    """Process a single PDF through DIKIWI."""
    print(f"[PDF] Processing {pdf_path.name} ...")
    config = ChaosConfig()
    processor = PDFProcessor(config=config)
    extracted = await processor.process(pdf_path)

    if not extracted:
        return {"error": "PDF extraction failed"}

    result = await bridge.process_extracted_content(extracted)
    return result


async def run_test() -> dict:
    clean_vault()

    api_key = os.environ.get("KIMI_API_KEY") or os.environ.get("MOONSHOT_API_KEY") or SETTINGS.kimi_api_key or SETTINGS.llm_api_key
    llm_client = PrimaryLLMRoute.route_kimi(
        api_key=api_key,
        model=SETTINGS.kimi_model,
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

    bridge = ChaosDikiwiBridge(
        dikiwi_mind=dikiwi_mind,
        processed_folder=Path.home() / "aily_chaos" / ".processed",
    )

    pdf_dir = Path.home() / "aily_chaos" / "pdf"
    pdf_files = sorted(pdf_dir.glob("*.pdf"), key=lambda p: p.stat().st_size)[:2]

    print(f"[RUN] Processing {len(pdf_files)} smallest PDFs...")
    start_time = time.monotonic()

    processed = 0
    failed = 0
    total_zettels = 0

    for pdf_path in pdf_files:
        try:
            result = await process_pdf(pdf_path, bridge)
            if "error" in result:
                print(f"  -> FAILED {pdf_path.name}: {result['error']}")
                failed += 1
                continue
            processed += 1
            total_zettels += int(result.get("zettels_created", 0))
            print(
                f"  -> {pdf_path.name}: stage={result.get('stage', 'UNKNOWN')}, zettels={result.get('zettels_created', 0)}"
            )
        except Exception as e:
            print(f"  -> FAILED {pdf_path.name}: {e}")
            failed += 1

    elapsed = time.monotonic() - start_time
    await graph_db.close()

    vault_status = get_vault_status()
    llm_call_count = 0
    if LLM_LOG_PATH.exists():
        with open(LLM_LOG_PATH, "r", encoding="utf-8") as f:
            llm_call_count = sum(1 for _ in f)

    report = {
        "pdfs_attempted": len(pdf_files),
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
    result = asyncio.run(run_test())
