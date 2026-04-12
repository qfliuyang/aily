#!/usr/bin/env python3
"""End-to-end test: chaos file → extraction → DIKIWI → Zettelkasten.

Usage:
    python scripts/test_chaos_e2e.py          # runs default: 1 PDF + 3 images
    python scripts/test_chaos_e2e.py --pdf     # PDF only
    python scripts/test_chaos_e2e.py --images  # images only
    python scripts/test_chaos_e2e.py --dry-run # extraction only, no DIKIWI
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("chaos_e2e")
logging.getLogger("aily").setLevel(logging.INFO)

CHAOS_FOLDER = Path.home() / "aily_chaos"


def _banner(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def _section(title: str) -> None:
    print(f"\n  ── {title}")


async def _extract_pdf(pdf_path: Path) -> object | None:
    """Extract content from a PDF using the ChaosProcessor pipeline."""
    from aily.chaos.config import ChaosConfig
    from aily.chaos.processors.pdf import PDFProcessor

    config = ChaosConfig()
    processor = PDFProcessor(config, llm_client=None)

    print(f"  Extracting PDF: {pdf_path.name} ({pdf_path.stat().st_size // 1024}KB)...")
    result = await processor.process(pdf_path)
    return result


async def _extract_images(image_paths: list[Path]) -> list[object]:
    """Extract content from a list of images, then merge into one session."""
    from aily.chaos.config import ChaosConfig
    from aily.chaos.processors.image import ImageProcessor
    from aily.chaos.types import ExtractedContentMultimodal

    config = ChaosConfig()
    processor = ImageProcessor(config, llm_client=None)

    results = []
    for p in image_paths:
        print(f"  Extracting image: {p.name}...")
        r = await processor.process(p)
        if r:
            results.append(r)

    if not results:
        return []

    # Merge into one session note (same as daemon behaviour for burst images)
    merged_text = "\n\n".join(r.text for r in results if r.text)
    merged = ExtractedContentMultimodal(
        text=merged_text,
        title=f"Image Session ({len(results)} photos)",
        source_type="image_session",
        source_path=image_paths[0],
        processing_method="glm-4v",
        metadata={"image_count": len(results), "paths": [str(p) for p in image_paths]},
        tags=[],
    )
    return [merged]


async def _run_dikiwi(content: object, vault_path: Path) -> dict:
    """Run one content item through DIKIWI mind, return stats + zettels."""
    from aily.config import SETTINGS
    from aily.graph.db import GraphDB
    from aily.llm.provider_routes import PrimaryLLMRoute
    from aily.sessions.dikiwi_mind import DikiwiMind
    from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter
    from aily.chaos.dikiwi_bridge import ChaosDikiwiBridge

    api_key = os.environ.get("ZHIPU_API_KEY") or SETTINGS.zhipu_api_key
    llm_client = PrimaryLLMRoute.route_zhipu(
        api_key=api_key,
        model=SETTINGS.zhipu_model,
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

    bridge = ChaosDikiwiBridge(dikiwi_mind=dikiwi_mind)

    try:
        result = await bridge.process_extracted_content(content)
    finally:
        await graph_db.close()

    return result


def _print_extraction(label: str, content: object) -> None:
    """Pretty-print extraction results."""
    _section(f"Extraction — {label}")
    if content is None:
        print("    [FAILED: no content extracted]")
        return
    text = getattr(content, "text", "") or ""
    title = getattr(content, "title", "(no title)")
    method = getattr(content, "processing_method", "?")
    tags = getattr(content, "tags", [])

    print(f"    title:  {title}")
    print(f"    method: {method}")
    print(f"    chars:  {len(text)}")
    print(f"    tags:   {tags[:8]}")
    print()
    # Show first ~500 chars
    preview = text[:500].strip()
    for line in textwrap.wrap(preview, width=70, initial_indent="    ", subsequent_indent="    "):
        print(line)
    if len(text) > 500:
        print(f"    ... [{len(text) - 500} more chars]")


def _print_dikiwi_result(result: dict, vault_path: Path) -> None:
    """Print DIKIWI pipeline result and any generated Zettelkasten notes."""
    _section("DIKIWI Result")
    if "error" in result:
        print(f"    [ERROR]: {result['error']}")
        return

    print(f"    stage reached: {result.get('stage', '?')}")
    print(f"    zettels:       {result.get('zettels_created', 0)}")
    print(f"    insights:      {result.get('insights', 0)}")
    print(f"    pipeline_id:   {result.get('pipeline_id', '?')}")

    # Find generated notes in vault
    zettel_dir = vault_path / "DIKIWI"
    if zettel_dir.exists():
        all_notes = sorted(zettel_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        recent = [n for n in all_notes[:5]]  # 5 most recently written
        if recent:
            _section("Most Recent Zettelkasten Notes Written")
            for note in recent:
                rel = note.relative_to(vault_path)
                print(f"\n    📄 {rel}")
                body = note.read_text(encoding="utf-8", errors="replace")
                # Show first 400 chars of each note
                preview = body[:400].strip()
                for line in preview.splitlines():
                    print(f"       {line}")
                if len(body) > 400:
                    print(f"       ... [{len(body) - 400} more chars]")
    else:
        print("\n    (vault DIKIWI folder not found — notes may be elsewhere)")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Chaos end-to-end test")
    parser.add_argument("--pdf", action="store_true", help="Test PDF only")
    parser.add_argument("--images", action="store_true", help="Test images only")
    parser.add_argument("--dry-run", action="store_true", help="Extraction only, skip DIKIWI")
    parser.add_argument("--n-images", type=int, default=3, help="Number of images to bundle")
    args = parser.parse_args()

    run_pdf = args.pdf or (not args.images)
    run_images = args.images or (not args.pdf)

    from aily.config import SETTINGS
    vault_path = Path(SETTINGS.obsidian_vault_path).expanduser() if SETTINGS.obsidian_vault_path else (Path.home() / "Documents/Obsidian Vault")

    _banner("Aily Chaos → Zettelkasten — End-to-End Test")
    print(f"  chaos folder: {CHAOS_FOLDER}")
    print(f"  vault path:   {vault_path}")
    print(f"  dry_run:      {args.dry_run}")

    items: list[tuple[str, object]] = []

    # ── PDF ──────────────────────────────────────────────────────────────────
    if run_pdf:
        pdfs = sorted((CHAOS_FOLDER / "pdf").glob("*.pdf"))
        if not pdfs:
            print("\n  [skip] No PDFs found in ~/aily_chaos/pdf/")
        else:
            pdf = pdfs[0]  # pick first
            content = await _extract_pdf(pdf)
            _print_extraction(pdf.name, content)
            if content:
                items.append((pdf.name, content))

    # ── Images ───────────────────────────────────────────────────────────────
    if run_images:
        imgs = sorted((CHAOS_FOLDER / "image").glob("*.jpg"))[:args.n_images]
        if not imgs:
            print("\n  [skip] No JPGs found in ~/aily_chaos/image/")
        else:
            contents = await _extract_images(imgs)
            for c in contents:
                _print_extraction(c.title, c)
                items.append((c.title, c))

    if not items:
        print("\n  Nothing to process — check ~/aily_chaos/ contents.")
        return

    if args.dry_run:
        _banner("Dry-run complete — skipped DIKIWI stage")
        return

    # ── DIKIWI pipeline ───────────────────────────────────────────────────────
    _banner("Running DIKIWI Pipeline")
    for label, content in items:
        _section(f"Processing: {label}")
        result = await _run_dikiwi(content, vault_path)
        _print_dikiwi_result(result, vault_path)

    _banner("Done")


if __name__ == "__main__":
    asyncio.run(main())
