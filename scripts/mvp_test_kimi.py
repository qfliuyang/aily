#!/usr/bin/env python3
"""MVP test: Process Kimi link -> Zettelkasten -> Feishu.

Usage: python scripts/mvp_test_kimi.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.config import SETTINGS
from aily.queue.db import QueueDB
from aily.graph.db import GraphDB
from aily.llm.client import LLMClient
from aily.push.feishu import FeishuPusher
from aily.browser.fetcher import BrowserFetcher
from aily.parser import registry
from aily.parser.parsers import parse_kimi
from aily.processing.atomicizer import AtomicNoteGenerator


async def main():
    """Run MVP test."""
    url = "https://www.kimi.com/share/19d7012e-23d2-8df8-8000-00004c0aad17"
    open_id = SETTINGS.aily_digest_feishu_open_id or ""
    feishu_enabled = bool(open_id)

    if not SETTINGS.llm_api_key:
        print("ERROR: No LLM API key configured")
        return

    print(f"🚀 MVP Test: Processing {url}")
    if feishu_enabled:
        print(f"📱 Target Feishu open_id: {open_id[:20]}...")
    else:
        print("📱 Feishu: Disabled (no open_id configured)")
        print("   Output will be saved to local file")

    # Initialize components
    queue_db = QueueDB(SETTINGS.queue_db_path)
    graph_db = GraphDB(SETTINGS.graph_db_path)
    await queue_db.initialize()
    await graph_db.initialize()

    llm = LLMClient(
        base_url=SETTINGS.llm_base_url,
        api_key=SETTINGS.llm_api_key,
        model=SETTINGS.llm_model,
    )
    pusher = FeishuPusher(SETTINGS.feishu_app_id, SETTINGS.feishu_app_secret) if feishu_enabled else None
    fetcher = BrowserFetcher()

    # Register Kimi parser
    registry.register(r"^https://kimi\.moonshot\.cn/share/", parse_kimi)
    registry.register(r"^https://www\.kimi\.com/share/", parse_kimi)

    try:
        # Step 1: Fetch the URL
        print("\n📥 Step 1: Fetching content...")
        if pusher:
            await pusher.send_message(open_id, "🚀 MVP Test started! Fetching your Kimi conversation...")

        raw_text = await fetcher.fetch(url)
        print(f"   Fetched {len(raw_text)} chars")

        # Step 2: Parse content
        print("\n🔍 Step 2: Parsing Kimi content...")
        parsed = registry.parse(url, raw_text)
        print(f"   Title: {parsed.title[:80]}...")
        print(f"   Markdown: {len(parsed.markdown)} chars")

        # Step 3: Generate Zettelkasten (atomic notes)
        print("\n🧠 Step 3: Generating Zettelkasten notes...")

        # Create raw log entry for atomicizer reference
        raw_log_id = await queue_db.insert_raw_log(url, source="mvp_test")
        if not raw_log_id:
            # URL may already exist, get existing
            logs = await queue_db.get_raw_logs_within_hours(24)
            for log in logs:
                if log["url"] == url:
                    raw_log_id = log["id"]
                    break
            if not raw_log_id:
                raw_log_id = "mvp_test_" + url.split("/")[-1][:20]

        atomicizer = AtomicNoteGenerator(llm, graph_db)
        notes = await atomicizer.atomize(
            content=parsed.markdown,
            source_url=url,
            raw_log_id=raw_log_id,
        )
        print(f"   Generated {len(notes)} atomic notes")

        # Step 4: Generate connection suggestions
        print("\n🔗 Step 4: Finding connections...")
        all_connections = []
        for note in notes[:3]:  # Limit to first 3 for speed
            connections = await atomicizer.suggest_connections(note)
            if connections:
                all_connections.extend(connections)
        print(f"   Found {len(all_connections)} connection suggestions")

        # Step 5: Send Zettelkasten to Feishu
        print("\n📤 Step 5: Sending Zettelkasten to Feishu...")

        # Build message
        lines = [
            f"✅ **MVP Test Complete!**",
            f"",
            f"📄 **Source**: [{parsed.title[:50]}]({url})",
            f"📝 **Extracted**: {len(parsed.markdown)} chars",
            f"🧠 **Atomic Notes**: {len(notes)}",
            f"🔗 **Connections**: {len(all_connections)}",
            f"",
            f"---",
            f"",
            f"## 🧠 Zettelkasten Notes",
            f"",
        ]

        for i, note in enumerate(notes[:10], 1):  # Show first 10
            lines.append(f"**{i}.** {note.content[:200]}...")
            if note.tags:
                lines.append(f"   🏷️ {', '.join(note.tags[:3])}")
            lines.append("")

        if len(notes) > 10:
            lines.append(f"... and {len(notes) - 10} more notes")
            lines.append("")

        if all_connections:
            lines.append("---")
            lines.append("")
            lines.append("## 🔗 Connection Suggestions")
            lines.append("")
            for conn in all_connections[:5]:
                lines.append(f"• {conn.explanation} (confidence: {conn.confidence_score:.2f})")

        message = "\n".join(lines)

        # Send to Feishu or save to file
        if pusher:
            if len(message) > 8000:
                await pusher.send_message(open_id, "\n".join(lines[:15]))
                await pusher.send_message(open_id, "...(truncated)...")
            else:
                await pusher.send_message(open_id, message)
            print("\n✅ MVP Test complete! Check Feishu for results.")
        else:
            # Save to local file
            output_path = Path("mvp_test_output.md")
            output_path.write_text(message)
            print(f"\n✅ MVP Test complete! Output saved to: {output_path.absolute()}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        if pusher:
            await pusher.send_message(open_id, f"❌ MVP Test failed: {str(e)[:200]}")
        raise

    finally:
        await fetcher.stop()
        await queue_db.close()
        await graph_db.close()


if __name__ == "__main__":
    asyncio.run(main())
