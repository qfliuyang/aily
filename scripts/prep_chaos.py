#!/usr/bin/env python3
"""Pre-extract 10 PDFs to a shared 00-Chaos, then clone to all provider vaults."""

import asyncio
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.chaos.config import ChaosConfig
from aily.chaos.processors.pdf import PDFProcessor


async def main():
    vaults = []
    for p in ["kimi", "zhipu", "deepseek"]:
        v = Path(f"/Users/luzi/code/aily/test-vault-{p}")
        for d in ["00-Chaos", "01-Data", "02-Information", "03-Knowledge",
                   "04-Insight", "05-Wisdom", "06-Impact",
                   "07-Proposal", "08-Entrepreneurship", "99-MOC"]:
            (v / d).mkdir(parents=True, exist_ok=True)
        vaults.append(v)

    pdf_dir = Path.home() / "aily_chaos" / "pdf"
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    random.Random(42).shuffle(pdfs)
    selected = pdfs[:10]
    print(f"Selected: {[p.stem for p in selected]}")

    processor = PDFProcessor(config=ChaosConfig())

    extracted = []
    for i, pdf in enumerate(selected):
        print(f"[{i+1}/10] Extracting: {pdf.name}")
        result = await processor.process(pdf)
        if result:
            extracted.append((pdf, result))
            print(f"  → {len(result.get_full_text())} chars")
        else:
            print(f"  → FAILED")

    # Copy to all 3 vaults
    for vault in vaults:
        chaos_dir = vault / "00-Chaos"
        img_dir = chaos_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        for pdf, ext in extracted:
            md_path = chaos_dir / f"{pdf.stem}.md"
            md_path.write_text(
                f"# {ext.title or pdf.stem}\n\n{ext.get_full_text()}",
                encoding="utf-8",
            )

            # Copy images
            mineru_out = ext.metadata.get("mineru_output_dir", "")
            src_images = Path(mineru_out) / "images" if mineru_out else None
            if src_images and src_images.is_dir():
                for img in src_images.iterdir():
                    if img.is_file() and not (img_dir / img.name).exists():
                        shutil.copy2(img, img_dir / img.name)

        count = len(list(chaos_dir.glob("*.md")))
        imgs = len(list(img_dir.iterdir())) if img_dir.exists() else 0
        print(f"{vault.name}: {count} markdown files, {imgs} images")

    # Save PDF list for reference
    (Path("/Users/luzi/code/aily/test-vault-kimi") / "selected_pdfs.json").write_text(
        __import__("json").dumps({"pdfs": [str(p) for p in selected], "names": [p.stem for p in selected]}), indent=2
    )

    print("\nReady. Run 3 benchmarks in parallel:")
    for p in ["kimi", "zhipu", "deepseek"]:
        print(f"  python scripts/benchmark_run.py {p} test-vault-{p}")

asyncio.run(main())
