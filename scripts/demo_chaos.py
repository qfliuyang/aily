#!/usr/bin/env python3
"""Demo script for Aily Chaos - Process a file from aily_chaos folder."""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.chaos.config import ChaosConfig
from aily.chaos.processors.pdf import PDFProcessor
from aily.chaos.processors.image import ImageProcessor
from aily.chaos.tagger.engine import IntelligentTagger


async def process_pdf():
    """Process the Fabless PDF."""
    pdf_path = Path.home() / "aily_chaos" / "Fabless 2019 Version PDF.pdf"

    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return

    print(f"Processing: {pdf_path.name}")
    print(f"Size: {pdf_path.stat().st_size / 1024 / 1024:.1f} MB")
    print("-" * 50)

    config = ChaosConfig()
    processor = PDFProcessor(config.pdf, llm_client=None)

    result = await processor.process(pdf_path)

    if result:
        print(f"\n✓ Title: {result.title}")
        print(f"✓ Type: {result.source_type}")
        print(f"✓ Method: {result.processing_method}")
        print(f"✓ Metadata: {result.metadata}")
        print(f"✓ Visual elements: {len(result.visual_elements)}")

        # Show text preview
        text_preview = result.text[:1000] + "..." if len(result.text) > 1000 else result.text
        print(f"\n--- Text Preview ---\n{text_preview}\n---")

        # Tag the content
        print("\nGenerating tags...")
        tagger = IntelligentTagger(config)
        tags = await tagger.tag(result)
        print(f"✓ Tags: {tags[:10]}")  # Show first 10

        return result
    else:
        print("✗ Processing failed")
        return None


async def main():
    """Run demo."""
    import os

    if not (
        os.getenv("KIMI_API_KEY")
        or os.getenv("MOONSHOT_API_KEY")
        or os.getenv("LLM_API_KEY")
    ):
        raise SystemExit("Set KIMI_API_KEY, MOONSHOT_API_KEY, or LLM_API_KEY before running the demo.")

    print("=" * 60)
    print("Aily Chaos Demo - PDF Processing")
    print("=" * 60)

    result = await process_pdf()

    print("\n" + "=" * 60)
    if result:
        print("Demo complete! Content extracted successfully.")
    else:
        print("Demo failed - check errors above.")


if __name__ == "__main__":
    asyncio.run(main())
