#!/usr/bin/env python3
"""Test Zettelkasten generation with a single URL using Kimi."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.config import SETTINGS
from aily.sessions.dikiwi_mind import DikiwiMind
from aily.gating.drainage import RainDrop, RainType
from aily.graph.db import GraphDB
from aily.llm.llm_router import LLMRouter

# Test with just 1 URL
TEST_URL = "https://monica.im/share/chat?shareId=1jB54WO31xDzAIjL"

async def test():
    """Run single message test with Kimi."""
    print("=" * 60)
    print("Single Message Zettelkasten Test (Kimi)")
    print("=" * 60)

    # Initialize components
    db_path = Path("/tmp/test_dikiwi.db")
    graph_db = GraphDB(db_path=db_path)
    await graph_db.initialize()

    kimi_api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("LLM_API_KEY")
    if not kimi_api_key:
        raise RuntimeError("Set KIMI_API_KEY, MOONSHOT_API_KEY, or LLM_API_KEY before running this script.")

    print("\nUsing Kimi Open Platform...\n")

    llm_client = LLMRouter.standard_kimi(
        api_key=kimi_api_key,
        model="kimi-k2.5",
    )

    print("Provider: Kimi Open Platform")
    print(f"Model: {llm_client.model}")
    print(f"Base URL: {llm_client.base_url}\n")

    # Create DikiwiMind with Obsidian writer
    from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter

    obsidian_writer = DikiwiObsidianWriter(
        vault_path=SETTINGS.dikiwi_vault_path,
        folder_prefix="DIKIWI",
        zettelkasten_only=True,  # Only write Zettelkasten notes
    )

    mind = DikiwiMind(
        graph_db=graph_db,
        llm_client=llm_client,
        dikiwi_obsidian_writer=obsidian_writer,
    )

    # Create test drop
    drop = RainDrop(
        id="test_single",
        content=f"【Test Message - Monica AI Chat】{TEST_URL}",
        source="test",
        rain_type=RainType.URL,
    )

    print(f"Processing: {TEST_URL}")
    print("This may take 1-2 minutes...\n")

    try:
        result = await mind.process_input(drop)

        print("\n" + "=" * 60)
        print("RESULT")
        print("=" * 60)
        print(f"Pipeline ID: {result.pipeline_id}")
        print(f"Total time: {result.total_time_ms/1000:.1f}s")
        print(f"Final stage: {result.final_stage_reached}")

        for stage_result in result.stage_results:
            print(f"\n{stage_result.stage.name}:")
            print(f"  Success: {stage_result.success}")
            print(f"  Input: {stage_result.items_processed}")
            print(f"  Output: {stage_result.items_output}")
            if stage_result.stage.name == "WISDOM" and stage_result.success:
                zettels = stage_result.data.get("zettels", [])
                print(f"  Zettels created: {len(zettels)}")
                for z in zettels:
                    word_count = len(z.content.split())
                    print(f"    - {z.title[:50]}... ({word_count} words)")

        # Check vault for new files
        import subprocess
        result_cmd = subprocess.run(
            ["find", f"{SETTINGS.dikiwi_vault_path}/3-Resources/Zettelkasten", "-name", "*.md", "-mmin", "-5"],
            capture_output=True,
            text=True
        )
        new_files = result_cmd.stdout.strip().split("\n") if result_cmd.stdout.strip() else []
        new_files = [f for f in new_files if f]

        print("\n" + "=" * 60)
        print("VAULT STATUS (files modified in last 5 minutes)")
        print("=" * 60)
        print(f"New Zettelkasten files: {len(new_files)}")
        for f in new_files[:5]:
            print(f"  - {Path(f).name}")
            # Show word count
            content = Path(f).read_text()
            word_count = len(content.split())
            print(f"    ({word_count} words)")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
