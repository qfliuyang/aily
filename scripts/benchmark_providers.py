#!/usr/bin/env python3
"""Benchmark LLM providers on the same 10 PDFs: Chaos -> Entrepreneur."""

import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.chaos.config import ChaosConfig
from aily.chaos.processors.pdf import PDFProcessor
from aily.config import SETTINGS
from aily.graph.db import GraphDB
from aily.llm.kimi_client import KimiClient
from aily.llm.client import LLMClient
from aily.sessions.dikiwi_mind import DikiwiMind
from aily.sessions.entrepreneur_scheduler import EntrepreneurScheduler
from aily.sessions.reactor_scheduler import ReactorScheduler
from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter

PROVIDERS = {
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": SETTINGS.kimi_model or "kimi-k2.6",
        "thinking": False,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": getattr(SETTINGS, "deepseek_model", "") or "deepseek-v4-pro",
        "thinking": False,
    },
}

def get_api_key(provider: str) -> str:
    if provider == "kimi":
        return SETTINGS.kimi_api_key
    if provider == "deepseek":
        return getattr(SETTINGS, "deepseek_api_key", "")
    raise ValueError(f"Unknown provider: {provider}")


def build_client(provider: str) -> LLMClient:
    cfg = PROVIDERS[provider]
    return LLMClient(
        base_url=cfg["base_url"],
        api_key=get_api_key(provider),
        model=cfg["model"],
        timeout=300.0,
        max_retries=2,
        thinking=cfg["thinking"],
        max_concurrency=1,
        min_interval_seconds=5.0,
    )


async def run_provider(
    provider: str,
    pdf_files: list[Path],
    vault_base: Path,
) -> dict:
    vault_path = vault_base / f"test-vault-{provider}"
    # Clean and create
    for subdir in list(vault_path.glob("*")):
        if subdir.is_dir() and not subdir.name.startswith("."):
            import shutil
            shutil.rmtree(subdir, ignore_errors=True)
    vault_path.mkdir(parents=True, exist_ok=True)

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

    from aily.chaos.dikiwi_bridge import ChaosDikiwiBridge

    processor = PDFProcessor(config=ChaosConfig())
    bridge = ChaosDikiwiBridge(dikiwi_mind=dikiwi_mind)

    doc_results = []
    total_start = time.monotonic()

    for pdf_path in pdf_files:
        doc_start = time.monotonic()
        extracted = await processor.process(pdf_path)
        if not extracted:
            doc_results.append({"pdf": pdf_path.name, "error": "extraction_failed"})
            continue

        transcript_dir = vault_path / "00-Chaos"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        (transcript_dir / f"{pdf_path.stem}.md").write_text(
            f"# {extracted.title or pdf_path.stem}\n\n{extracted.get_full_text()}",
            encoding="utf-8",
        )
        # Copy images
        mineru_out = extracted.metadata.get("mineru_output_dir", "")
        src_images = Path(mineru_out) / "images" if mineru_out else None
        if src_images and src_images.is_dir():
            dest_images = transcript_dir / "images"
            dest_images.mkdir(parents=True, exist_ok=True)
            import shutil
            for img in src_images.iterdir():
                if img.is_file() and not (dest_images / img.name).exists():
                    shutil.copy2(img, dest_images / img.name)

        bridge_result = await bridge.process_extracted_content(extracted)
        doc_results.append({
            "pdf": pdf_path.name,
            "stage": bridge_result.get("stage", "UNKNOWN"),
            "zettels": bridge_result.get("zettels_created", 0),
            "insights": bridge_result.get("insights", 0),
            "elapsed": round(time.monotonic() - doc_start, 2),
        })

    # Reactor
    reactor_elapsed = None
    proposals = []
    if dikiwi_mind.reactor_scheduler:
        reactor_start = time.monotonic()
        context = await dikiwi_mind.reactor_scheduler._gather_context()
        proposals = await dikiwi_mind.reactor_scheduler.evaluate_context(context)
        reactor_elapsed = round(time.monotonic() - reactor_start, 2)

    # Entrepreneur
    entrepreneur_elapsed = None
    if dikiwi_mind.entrepreneur_scheduler:
        entrepreneur_start = time.monotonic()
        await dikiwi_mind.entrepreneur_scheduler._run_session_wrapper()
        entrepreneur_elapsed = round(time.monotonic() - entrepreneur_start, 2)

    total_elapsed = round(time.monotonic() - total_start, 2)

    # Vault stats
    vault_status = {}
    for subdir in sorted(vault_path.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            vault_status[subdir.name] = len(list(subdir.rglob("*.md")))

    usage = llm_client.get_usage_stats()

    await graph_db.close()

    return {
        "provider": provider,
        "model": PROVIDERS[provider]["model"],
        "documents": len(doc_results),
        "results": doc_results,
        "elapsed_seconds": total_elapsed,
        "reactor_elapsed_seconds": reactor_elapsed,
        "reactor_proposals": len(proposals),
        "entrepreneur_elapsed_seconds": entrepreneur_elapsed,
        "vault_status": vault_status,
        "token_usage": usage,
    }


async def main():
    vault_base = Path("/Users/luzi/code/aily")
    pdf_dir = Path.home() / "aily_chaos" / "pdf"
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    random.Random(42).shuffle(pdf_files)
    selected = pdf_files[:10]
    print(f"Selected {len(selected)} PDFs: {[p.stem for p in selected]}")

    providers = ["kimi", "deepseek"]
    import logging
    logging.getLogger("aily.llm.client").setLevel(logging.WARNING)

    all_results = {}
    for provider in providers:
        print(f"\n{'='*60}")
        print(f"Running {provider.upper()} ({PROVIDERS[provider]['model']})...")
        print(f"{'='*60}")
        result = await run_provider(provider, selected, vault_base)
        all_results[provider] = result
        print(f"\n{provider.upper()} done: {result['elapsed_seconds']:.0f}s, "
              f"{result['vault_status']}, {result['token_usage']['calls']} calls")

    # Write report
    report_path = vault_base / "logs" / "benchmark_report.json"
    report_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nReport: {report_path}")

    # Summary table
    print(f"\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}")
    print(f"{'Provider':12s} {'Model':20s} {'Time':>8s} {'Calls':>6s} {'Vault':>30s}")
    for provider, r in all_results.items():
        vault_str = " ".join(f"{k}:{v}" for k, v in sorted(r["vault_status"].items()))
        print(f"{provider:12s} {PROVIDERS[provider]['model']:20s} {r['elapsed_seconds']:>8.0f}s {r['token_usage']['calls']:>6d} {vault_str[:30]}")


if __name__ == "__main__":
    asyncio.run(main())
