#!/usr/bin/env python3
"""Unified ad hoc test runner for Aily."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_framework import (
    DEFAULT_LOG_DIR,
    DEFAULT_VAULT_PATH,
    scenario_army,
    scenario_chaos_e2e,
    scenario_dikiwi_smoke,
    scenario_full_pipeline,
    scenario_legacy_atomicizer,
    scenario_processors,
    scenario_url_audit,
)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified scenario runner for Aily manual/integration test scripts.",
    )
    subparsers = parser.add_subparsers(dest="scenario", required=True)

    subparsers.add_parser("processors", help="Run lightweight Chaos processor smoke tests")

    smoke = subparsers.add_parser("dikiwi-smoke", help="Run direct Kimi checks and a small DIKIWI pipeline smoke test")
    smoke.add_argument("--limit", type=int, default=2, help="Number of test messages to run")
    smoke.add_argument("--url", type=str, help="Single URL/message override")

    chaos = subparsers.add_parser("chaos-e2e", help="Extract PDF/images and optionally push through DIKIWI")
    chaos.add_argument("--pdf", action="store_true", help="PDF only")
    chaos.add_argument("--images", action="store_true", help="Images only")
    chaos.add_argument("--dry-run", action="store_true", help="Extraction only, skip DIKIWI")
    chaos.add_argument("--n-images", type=int, default=3, help="Number of images to bundle")
    chaos.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH, help="Vault path")

    url_audit = subparsers.add_parser("url-audit", help="Audit Monica share-link routing and extraction")
    url_audit.add_argument("--limit", type=int, default=10, help="Number of test messages to inspect")
    url_audit.add_argument("--save-dir", type=Path, default=Path.cwd(), help="Directory for extracted markdown outputs")

    full = subparsers.add_parser("full-pipeline", help="Run Chaos -> DIKIWI -> Reactor -> Entrepreneur on PDFs")
    full.add_argument("--max", type=int, default=20, help="Maximum PDFs to process")
    full.add_argument("--no-clean", action="store_true", help="Skip vault cleanup")
    full.add_argument("--log-llm", action="store_true", help="Record all LLM calls to a jsonl trace")
    full.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH, help="Vault path")
    full.add_argument("--report-dir", type=Path, default=DEFAULT_LOG_DIR / "e2e", help="Directory for reports/logs")
    full.add_argument("--seed", type=int, default=260502, help="Seed for deterministic PDF pressure-test selection")
    full.add_argument("--phase-timeout", type=float, default=600.0, help="Timeout in seconds for each full-pipeline phase")
    full.add_argument("--force-business", action="store_true", help="Run Reactor/Entrepreneur even if no Impact outputs exist")

    legacy = subparsers.add_parser("legacy-atomicizer", help="Run the old Kimi->atomicizer MVP path in one scenario")
    legacy.add_argument("--url", required=True, help="Kimi share URL")
    legacy.add_argument("--open-id", default="", help="Optional Feishu open_id")
    legacy.add_argument("--clean-content", action="store_true", help="Apply aggressive Kimi UI cleanup before atomization")

    subparsers.add_parser("army", help="Run the ARMY OF TOP MINDS scenario")

    args = parser.parse_args()

    if args.scenario == "processors":
        result = await scenario_processors()
    elif args.scenario == "dikiwi-smoke":
        result = await scenario_dikiwi_smoke(limit=args.limit, url=args.url)
    elif args.scenario == "chaos-e2e":
        run_pdf = args.pdf or (not args.images)
        run_images = args.images or (not args.pdf)
        result = await scenario_chaos_e2e(
            run_pdf=run_pdf,
            run_images=run_images,
            dry_run=args.dry_run,
            n_images=args.n_images,
            vault_path=args.vault,
        )
    elif args.scenario == "url-audit":
        result = await scenario_url_audit(limit=args.limit, save_dir=args.save_dir)
    elif args.scenario == "full-pipeline":
        result = await scenario_full_pipeline(
            max_pdfs=args.max,
            no_clean=args.no_clean,
            log_llm=args.log_llm,
            vault_path=args.vault,
            report_dir=args.report_dir,
            source_seed=args.seed,
            phase_timeout_seconds=args.phase_timeout,
            force_business=args.force_business,
        )
    elif args.scenario == "legacy-atomicizer":
        result = await scenario_legacy_atomicizer(
            url=args.url,
            open_id=args.open_id,
            clean_content=args.clean_content,
        )
    elif args.scenario == "army":
        result = await scenario_army()
    else:
        parser.error(f"Unknown scenario: {args.scenario}")
        return 2

    rendered_result = json.dumps(result, indent=2, default=str, ensure_ascii=False)
    if isinstance(result, dict) and result.get("evidence_dir"):
        evidence_dir = Path(str(result["evidence_dir"]))
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "stdout.log").write_text(rendered_result + "\n", encoding="utf-8")
    print(rendered_result)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
