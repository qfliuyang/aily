#!/usr/bin/env python3
"""Test script for the ARMY OF TOP MINDS thinking system."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.thinking.models import KnowledgePayload
from aily.thinking.orchestrator import ThinkingOrchestrator
from aily.llm.client import LLMClient
from aily.config import SETTINGS


async def main():
    """Run ARMY analysis on sample content."""
    
    # Sample content about a startup
    content = """
    CogniChip is a startup using AI to revolutionize chip design. 
    Founded by Faraj Aalaei, the company has raised $93M from NVIDIA and Intel.
    Their ACI platform reduces chip design costs by 75% and time by 50%.
    The team includes experts from Amazon, Google, Apple, and Synopsys.
    They plan to tape out their first AI-designed chip by end of 2026.
    The technology embeds physical constraints into AI models.
    Their vision is to democratize chip design.
    """
    
    payload = KnowledgePayload(
        content=content,
        source_url="https://www.kimi.com/share/example",
        source_title="CogniChip Deep Research",
    )
    
    # Initialize LLM client
    llm = LLMClient(
        base_url=SETTINGS.llm_base_url,
        api_key=SETTINGS.llm_api_key,
        model=SETTINGS.llm_model,
    )
    
    # Initialize orchestrator
    orchestrator = ThinkingOrchestrator(llm_client=llm)
    
    print("🧠 ARMY OF TOP MINDS Analysis Starting...")
    print(f"📄 Source: {payload.source_title}")
    print()
    
    # Run analysis
    result = await orchestrator.think(
        payload,
        options={
            "output_format": "obsidian",
            "max_insights": 5,
        }
    )
    
    # Display results
    print(f"✅ Analysis Complete!")
    print(f"📊 Confidence: {result.confidence_score:.0%}")
    print(f"🧠 Frameworks: {[fi.framework_type.value for fi in result.framework_insights]}")
    print(f"💡 Insights Generated: {len(result.synthesized_insights)}")
    print(f"⏱️  Processing Time: {result.processing_metadata.get('total_time_ms', 0)}ms")
    print()
    
    # Show top insights
    print("## Top Insights")
    for i, insight in enumerate(result.top_insights[:3], 1):
        print(f"\n{i}. {insight.title}")
        print(f"   {insight.description}")
        print(f"   Confidence: {insight.confidence:.0%}")
        if insight.action_items:
            print(f"   Actions: {', '.join(insight.action_items[:2])}")
    
    # Show formatted output preview
    if result.formatted_output:
        print("\n\n## Formatted Output Preview (first 500 chars)")
        obsidian_output = result.formatted_output.get("obsidian", "")
        print(obsidian_output[:500] + "...")
    
    return result


if __name__ == "__main__":
    asyncio.run(main())
