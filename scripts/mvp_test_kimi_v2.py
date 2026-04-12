#!/usr/bin/env python3
"""MVP test v2: Process Kimi link -> Zettelkasten with delay and content cleaning."""

import asyncio
import sys
import re
from pathlib import Path

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


def clean_kimi_content(text: str) -> str:
    ui_patterns = [r'新建会话', r'⌘', r'K\n', r'网站\n', r'文档\n', r'PPT\n', r'表格\n']
    for pattern in ui_patterns:
        text = re.sub(pattern, '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines)


async def main():
    open_id = sys.argv[1] if len(sys.argv) > 1 else SETTINGS.aily_digest_feishu_open_id or ""
    feishu_enabled = bool(open_id)

    if not SETTINGS.llm_api_key:
        print("ERROR: No LLM API key configured")
        return

    url = "https://www.kimi.com/share/19d7012e-23d2-8df8-8000-00004c0aad17"
    print(f"🚀 MVP Test v2: Processing {url}")

    if feishu_enabled:
        print(f"📱 Feishu open_id: {open_id[:20]}...")
    else:
        print("📱 Output will be saved to local file")

    queue_db = QueueDB(SETTINGS.queue_db_path)
    graph_db = GraphDB(SETTINGS.graph_db_path)
    await queue_db.initialize()
    await graph_db.initialize()

    llm = LLMClient(base_url=SETTINGS.llm_base_url, api_key=SETTINGS.llm_api_key, model=SETTINGS.llm_model)
    pusher = FeishuPusher(SETTINGS.feishu_app_id, SETTINGS.feishu_app_secret) if feishu_enabled else None
    fetcher = BrowserFetcher()

    try:
        print("\n📥 Fetching content...")
        raw_text = await fetcher.fetch(url)
        print(f"   Fetched {len(raw_text)} chars")

        print("\n🧹 Cleaning content...")
        cleaned = clean_kimi_content(raw_text)
        print(f"   Cleaned to {len(cleaned)} chars")

        print("\n🧠 Generating Zettelkasten (waiting 60s for rate limit)...")
        await asyncio.sleep(60)

        raw_log_id = await queue_db.insert_raw_log(url, source="mvp_test_v2") or "mvp_v2_test"
        atomicizer = AtomicNoteGenerator(llm, graph_db)
        notes = await atomicizer.atomize(content=cleaned[:15000], source_url=url, raw_log_id=raw_log_id)
        print(f"   Generated {len(notes)} atomic notes")

        lines = ["✅ **MVP Test v2 Complete!**", "", f"📄 Source: {url}", f"🧠 Atomic Notes: {len(notes)}", "", "## 🧠 Zettelkasten Notes", ""]
        for i, note in enumerate(notes[:15], 1):
            lines.append(f"**{i}.** {note.content[:300]}...")
            if note.tags:
                lines.append(f"   🏷️ {', '.join(note.tags[:3])}")
            lines.append("")

        message = "\n".join(lines)

        if pusher:
            await pusher.send_message(open_id, message[:7000])
            print("\n✅ Sent to Feishu!")
        else:
            Path("mvp_test_v2_output.md").write_text(message)
            print("\n✅ Saved to mvp_test_v2_output.md")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        await fetcher.stop()
        await queue_db.close()
        await graph_db.close()


if __name__ == "__main__":
    asyncio.run(main())
