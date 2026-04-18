#!/usr/bin/env python3
"""Test script for LLM-powered DIKIWI using Kimi API.

This script tests the new DikiwiMind class that replaces all
hardcoded rule-based logic with Kimi LLM-based processing.

Usage:
    python scripts/test_kimi_dikiwi.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.sessions.dikiwi_mind import DikiwiMind, DikiwiStage
from aily.gating.drainage import RainDrop, RainType
from aily.graph.db import GraphDB
from aily.llm.kimi_client import KimiClient

# Create temp directory for test DB
import tempfile
TEST_DB_DIR = Path(tempfile.gettempdir()) / "aily_test"
TEST_DB_DIR.mkdir(exist_ok=True)


def _require_kimi_api_key() -> str:
    api_key = KimiClient.resolve_api_key()
    if not api_key:
        raise RuntimeError("Set KIMI_API_KEY, MOONSHOT_API_KEY, or LLM_API_KEY before running this script.")
    return api_key


# The 10 test messages from docs/URL_TEST_MESSAGES.md
TEST_MESSAGES = [
    "【转向AI芯片架构的路径与优势 - Monica AI Chat】https://monica.im/share/chat?shareId=1jB54WO31xDzAIjL",
    "【模型的8bit和4bit量化原理与影响 - Monica AI Chat】https://monica.im/share/chat?shareId=VSvhr187W10wmQ5m",
    "【EDA软件的MCP蒸馏讨论 - Monica AI Chat】https://monica.im/share/chat?shareId=GGz9X6A7mnNeMqAJ",
    "【什么是MCP及其开发方法 - Monica AI Chat】https://monica.im/share/chat?shareId=9kH3k9l1jAPKh6t2",
    "【破除都灵裹尸布的迷雾 - Monica AI Chat】https://monica.im/share/chat?shareId=s36KOgwdvpjFZaEf",
    "【具有里程碑意义的AI技术 - Monica AI Chat】https://monica.im/share/chat?shareId=emlaeMyPoBUaFFfo",
    "【基于命令行工具转为MCP的可行性与借鉴工作 - Monica AI Chat】https://monica.im/share/chat?shareId=fdxLkrA92foijyIl",
    "【评估NVIDIA生成式AI技术用于EDA领域TCL脚本生成的适用性 - Monica AI Chat】https://monica.im/share/chat?shareId=BsA0KcdiGWQo4l09",
    "【PDK 评价体系与工艺线平衡分析 - Monica AI Chat】https://monica.im/share/chat?shareId=nLsKxwTCySW0p6Z3",
    "【芯片signoff规则制定方法论及学习资料 - Monica AI Chat】https://monica.im/share/chat?shareId=4cxQomLr6VD28Ofx",
]


async def test_kimi_dikiwi():
    """Test LLM-powered DIKIWI with Kimi API."""
    print("=" * 80)
    print("TEST: LLM-Powered DIKIWI with Kimi API")
    print("=" * 80)

    # Initialize components
    # Note: Using a mock GraphDB for testing - replace with real instance
    graph_db = GraphDB(db_path=TEST_DB_DIR / "test.db")
    await graph_db.initialize()

    # Initialize Kimi-powered DIKIWI mind
    kimi_api_key = _require_kimi_api_key()

    print("\nInitializing DikiwiMind with Kimi API...")
    mind = DikiwiMind(
        kimi_api_key=kimi_api_key,
        graph_db=graph_db,
        enabled=True,
        obsidian_writer=None,  # Skip Obsidian for this test
        browser_manager=None,  # Will be needed for URL fetching
        model="kimi-k2.5",
    )
    print("✓ DikiwiMind initialized")

    # Test with first 2 messages (to keep test duration reasonable)
    test_subset = TEST_MESSAGES[:2]

    print(f"\nProcessing {len(test_subset)} messages through DIKIWI pipeline...")
    print("-" * 80)

    results = []
    for i, msg in enumerate(test_subset, 1):
        print(f"\n[{i}/{len(test_subset)}] Processing message:")
        print(f"    {msg[:60]}...")

        # Create RainDrop
        drop = RainDrop(
            rain_type=RainType.CHAT,
            id=f"test_msg_{i}",
            content=msg,
            source="test_kimi_dikiwi",
        )

        try:
            # Process through DIKIWI
            result = await mind.process_input(drop)
            results.append(result)

            # Print results
            print(f"\n    Pipeline ID: {result.pipeline_id}")
            print(f"    Total time: {result.total_time_ms:.0f}ms")
            print(f"    Stages completed: {len(result.stage_results)}")

            for stage_result in result.stage_results:
                status = "✓" if stage_result.success else "✗"
                print(f"      {status} {stage_result.stage.name}: "
                      f"{stage_result.items_output} items "
                      f"({stage_result.processing_time_ms:.0f}ms)")

                if not stage_result.success:
                    print(f"        Error: {stage_result.error_message}")

            # Print extracted data details
            for stage_result in result.stage_results:
                if stage_result.stage == DikiwiStage.DATA and stage_result.success:
                    data_points = stage_result.data.get("data_points", [])
                    print(f"\n    Data Points extracted ({len(data_points)}):")
                    for dp in data_points[:3]:  # Show first 3
                        print(f"      - {dp.content[:80]}...")

                if stage_result.stage == DikiwiStage.INFORMATION and stage_result.success:
                    info_nodes = stage_result.data.get("information_nodes", [])
                    print(f"\n    Information Nodes ({len(info_nodes)}):")
                    for node in info_nodes[:3]:
                        print(f"      - [{node.domain}] {node.content[:60]}...")
                        print(f"        Tags: {', '.join(node.tags[:5])}")

                if stage_result.stage == DikiwiStage.INSIGHT and stage_result.success:
                    insights = stage_result.data.get("insights", [])
                    print(f"\n    Insights detected ({len(insights)}):")
                    for insight in insights[:3]:
                        print(f"      - [{insight.insight_type}] {insight.description[:60]}...")

        except Exception as e:
            print(f"    ✗ FAILED: {type(e).__name__}: {e}")
            results.append(None)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    successful = sum(1 for r in results if r is not None)
    print(f"Messages processed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")

    if successful > 0:
        avg_time = sum(r.total_time_ms for r in results if r is not None) / successful
        print(f"Average processing time: {avg_time:.0f}ms")

    # Print metrics
    metrics = mind.get_metrics()
    print(f"\nMetrics:")
    print(f"  Total inputs: {metrics['total_inputs']}")
    print(f"  Success rate: {metrics['success_rate']:.1%}")
    print(f"  Mode: {metrics['mode']}")

    print("\n" + "=" * 80)
    print("Key Differences from Rule-Based DIKIWI:")
    print("=" * 80)
    print("""
1. DATA Stage:
   Rule-based: Hardcoded 200-char threshold, truncation fallback
   LLM-based: LLM decides what constitutes meaningful data points

2. INFORMATION Stage:
   Rule-based: Keyword fallback when LLM fails
   LLM-based: Pure semantic classification, no keyword heuristics

3. KNOWLEDGE Stage:
   Rule-based: shared_tags heuristic for relation strength
   LLM-based: LLM determines semantic relationships

4. INSIGHT Stage:
   Rule-based: Simple isolated node detection
   LLM-based: LLM pattern analysis, theme detection, contradiction finding

5. WISDOM Stage:
   Rule-based: Template-based synthesis
   LLM-based: LLM principle synthesis with contextual awareness

6. IMPACT Stage:
   Rule-based: Fixed impact types
   LLM-based: LLM-generated actionable proposals with rationale
""")

    return results


async def test_kimi_client_directly():
    """Test Kimi client directly without full DIKIWI pipeline."""
    print("\n" + "=" * 80)
    print("TEST: Kimi Client Direct API Test")
    print("=" * 80)

    kimi_api_key = _require_kimi_api_key()

    print("\nInitializing KimiClient...")
    client = KimiClient(api_key=kimi_api_key, model="kimi-k2.5")
    print("✓ Client initialized")

    # Test simple chat
    print("\nTesting simple chat completion...")
    try:
        response = await client.chat(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"},
            ],
            temperature=0.5,
        )
        print(f"✓ Response: {response}")
    except Exception as e:
        print(f"✗ Failed: {type(e).__name__}: {e}")
        return False

    # Test JSON mode
    print("\nTesting JSON mode...")
    try:
        result = await client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": "You extract information as JSON.",
                },
                {
                    "role": "user",
                    "content": 'Extract: "AI chip design is moving toward specialized architectures"',
                },
            ],
            temperature=0.3,
        )
        print(f"✓ JSON Response: {result}")
    except Exception as e:
        print(f"✗ Failed: {type(e).__name__}: {e}")
        return False

    # Test semantic classification
    print("\nTesting semantic classification...")
    try:
        result = await client.classify_semantic(
            content="Reinforcement learning from human feedback improves model alignment",
            categories=["technology", "business", "science", "philosophy"],
            context="AI research topic",
        )
        print(f"✓ Classification: {result}")
    except Exception as e:
        print(f"✗ Failed: {type(e).__name__}: {e}")
        return False

    print("\n✓ All Kimi client tests passed!")
    return True


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("LLM-POWERED DIKIWI TEST SUITE")
    print("Using Kimi API for pure LLM-based knowledge processing")
    print("=" * 80)

    # First test Kimi client directly
    client_ok = await test_kimi_client_directly()

    if not client_ok:
        print("\n✗ Kimi client test failed - skipping DIKIWI tests")
        return 1

    # Then test full DIKIWI pipeline
    await test_kimi_dikiwi()

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
