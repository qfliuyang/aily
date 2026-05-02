#!/usr/bin/env python3
"""Run DIKIWI + Reactor + Entrepreneur against a pre-populated 00-Chaos vault.

Usage:
  python scripts/benchmark_run.py <provider> <vault_path>
  python scripts/benchmark_run.py kimi /Users/luzi/code/aily/test-vault-kimi
  python scripts/benchmark_run.py deepseek /Users/luzi/code/aily/test-vault-deepseek
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.config import SETTINGS
from aily.gating.drainage import RainDrop, RainType, StreamType
from aily.graph.db import GraphDB
from aily.llm.client import LLMClient
from aily.sessions.dikiwi_mind import DikiwiMind
from aily.sessions.entrepreneur_scheduler import EntrepreneurScheduler
from aily.sessions.reactor_scheduler import ReactorScheduler
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark")

PROVIDERS = {
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": SETTINGS.kimi_model or "kimi-k2.6",
        "api_key": SETTINGS.kimi_api_key,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": getattr(SETTINGS, "deepseek_model", "") or "deepseek-v4-pro",
        "api_key": getattr(SETTINGS, "deepseek_api_key", ""),
    },
}


def build_client(provider: str) -> LLMClient:
    cfg = PROVIDERS[provider]
    return LLMClient(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        timeout=300.0,
        max_retries=2,
        thinking=False,
        max_concurrency=1,
        min_interval_seconds=1.0,  # faster pacing for benchmark
    )


async def main():
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <kimi|deepseek> <vault_path>")
        sys.exit(1)

    provider = sys.argv[1]
    vault_path = Path(sys.argv[2])

    if provider not in PROVIDERS:
        print(f"Unknown provider: {provider}")
        sys.exit(1)

    print(f"Provider: {provider} ({PROVIDERS[provider]['model']})")
    print(f"Vault: {vault_path}")

    chaos_dir = vault_path / "00-Chaos"
    if not chaos_dir.exists():
        print(f"ERROR: 00-Chaos not found at {chaos_dir}")
        sys.exit(1)

    md_files = sorted(chaos_dir.glob("*.md"))
    pdf_files = [f for f in md_files if f.name != "00 Zettelkasten Index.md"]
    print(f"Documents to process: {len(pdf_files)}")

    # Init GraphDB
    graph_db = GraphDB(db_path=vault_path / ".aily" / "graph.db")
    await graph_db.initialize()

    llm_client = build_client(provider)
    obsidian_writer = DikiwiObsidianWriter(vault_path=vault_path)

    dikiwi_mind = DikiwiMind(
        graph_db=graph_db,
        llm_client=llm_client,
        dikiwi_obsidian_writer=obsidian_writer,
    )
    dikiwi_mind.reactor_scheduler = ReactorScheduler(
        graph_db=graph_db,
        llm_client=llm_client,
        obsidian_writer=obsidian_writer,
    )
    dikiwi_mind.entrepreneur_scheduler = EntrepreneurScheduler(
        graph_db=graph_db,
        llm_client=llm_client,
        obsidian_writer=obsidian_writer,
    )

    total_start = time.monotonic()
    doc_results = []

    for md_file in pdf_files:
        doc_start = time.monotonic()
        content = md_file.read_text(encoding="utf-8")

        drop = RainDrop(
            id="",
            rain_type=RainType.DOCUMENT,
            content=content,
            source="chaos_processor",
            source_id=md_file.stem,
            stream_type=StreamType.EXTRACT_ANALYZE,
            metadata={"source_paths": [str(md_file)]},
        )

        result = await dikiwi_mind.process_input(drop)
        final_stage = result.final_stage_reached.name if result.final_stage_reached else "UNKNOWN"
        zettels_count = 0
        for sr in result.stage_results:
            if sr.success:
                z = sr.data.get("zettels", [])
                zettels_count += len(z) if isinstance(z, list) else (z if isinstance(z, int) else 0)
        insights = 0
        for sr in result.stage_results:
            if sr.success:
                ins = sr.data.get("insights", [])
                insights += len(ins) if isinstance(ins, list) else (ins if isinstance(ins, int) else 0)

        doc_results.append({
            "pdf": md_file.stem,
            "stage": final_stage,
            "zettels": zettels_count,
            "insights": insights,
            "elapsed": round(time.monotonic() - doc_start, 2),
        })

        vault_status = {}
        for subdir in sorted(vault_path.iterdir()):
            if subdir.is_dir() and not subdir.name.startswith("."):
                vault_status[subdir.name] = len(list(subdir.rglob("*.md")))

        print(f"[{provider}] {md_file.stem[:40]:40s} → {final_stage:10s} | vault: {vault_status}")

    # Reactor
    reactor_proposals = []
    reactor_elapsed = None
    if dikiwi_mind.reactor_scheduler:
        reactor_start = time.monotonic()
        try:
            context = await dikiwi_mind.reactor_scheduler._gather_context()
            reactor_proposals = await dikiwi_mind.reactor_scheduler.evaluate_context(context)
        except Exception as e:
            logger.error(f"Reactor failed: {e}")
        reactor_elapsed = round(time.monotonic() - reactor_start, 2)
        print(f"[{provider}] Reactor: {len(reactor_proposals)} proposals in {reactor_elapsed}s")

    # Entrepreneur
    entrepreneur_elapsed = None
    if dikiwi_mind.entrepreneur_scheduler:
        entrepreneur_start = time.monotonic()
        try:
            await dikiwi_mind.entrepreneur_scheduler._run_session_wrapper()
        except Exception as e:
            logger.error(f"Entrepreneur failed: {e}")
        entrepreneur_elapsed = round(time.monotonic() - entrepreneur_start, 2)
        print(f"[{provider}] Entrepreneur: {entrepreneur_elapsed}s")

    total_elapsed = round(time.monotonic() - total_start, 2)

    # Final vault stats
    vault_status = {}
    for subdir in sorted(vault_path.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            vault_status[subdir.name] = len(list(subdir.rglob("*.md")))

    usage = llm_client.get_usage_stats()

    result = {
        "provider": provider,
        "model": PROVIDERS[provider]["model"],
        "documents": len(pdf_files),
        "results": doc_results,
        "elapsed_seconds": total_elapsed,
        "reactor_elapsed_seconds": reactor_elapsed,
        "reactor_proposals": len(reactor_proposals),
        "entrepreneur_elapsed_seconds": entrepreneur_elapsed,
        "vault_status": vault_status,
        "token_usage": usage,
    }

    report_path = vault_path / "benchmark_report.json"
    report_path.write_text(json.dumps(result, indent=2, default=str))

    print(f"\n[{'='*50}]")
    print(f"[{provider.upper()}] COMPLETE: {total_elapsed:.0f}s, {usage['calls']} calls, {usage['total_tokens']} tokens")
    print(f"[{provider.upper()}] Vault: {vault_status}")
    print(f"[{provider.upper()}] Report: {report_path}")
    print(f"[{'='*50}]")

    await graph_db.close()


if __name__ == "__main__":
    asyncio.run(main())
