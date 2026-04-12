#!/usr/bin/env python3
"""
Extract chat content from authenticated AI services (Monica, Kimi).

REQUIRES: You must be logged into the service in your Chrome browser.
This uses your local Chrome profile to access authenticated content.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.config import SETTINGS
from aily.browser.manager import BrowserUseManager
from aily.llm.client import LLMClient
from aily.writer.obsidian import ObsidianWriter


class AuthenticatedChatExtractor:
    """Extract chat content from authenticated AI services using local browser."""

    def __init__(self) -> None:
        self.llm = LLMClient(
            base_url=SETTINGS.llm_base_url,
            api_key=SETTINGS.llm_api_key,
            model=SETTINGS.llm_model,
        )
        self.writer = ObsidianWriter(
            api_key=SETTINGS.obsidian_rest_api_key,
            vault_path=SETTINGS.obsidian_vault_path,
            port=SETTINGS.obsidian_rest_api_port,
        )

    async def extract_chat(
        self,
        url: str,
        service_name: str = "AI Chat",
        use_personal_profile: bool = True,
        timeout: int = 300,
    ) -> dict:
        """Extract chat content using local browser with authenticated profile."""
        print(f"🔍 Extracting from: {url}")
        print(f"   Service: {service_name}")
        print(f"   Using local browser with your Chrome profile")
        print(f"   ⚠️  IMPORTANT: You must be logged into {service_name} in Chrome")

        # Use local browser only (skip commercial API which gets blocked)
        browser = BrowserUseManager(
            worker_type="agent",
            llm_config={
                "provider": "openai",
                "model": SETTINGS.llm_model,
                "api_key": SETTINGS.llm_api_key,
                "base_url": SETTINGS.llm_base_url,
            }
        )

        await browser.start()
        try:
            text = await browser.fetch(
                url,
                timeout=timeout,
                use_personal_profile=use_personal_profile,
            )
            return {"status": "ok", "text": text}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            await browser.stop()

    async def summarize_conversation(self, raw_content: str, service_name: str) -> dict:
        """Use LLM to summarize the conversation into structured knowledge."""
        print(f"\n🧠 Summarizing {service_name} conversation...")

        messages = [
            {
                "role": "system",
                "content": f"""You are a knowledge curator. Analyze the {service_name} conversation and create a well-structured knowledge card.

Extract and organize:
1. **Main Topic** - What is this conversation about?
2. **Key Insights** - 3-5 important points or learnings
3. **Action Items** - Any tasks, decisions, or follow-ups mentioned
4. **Resources** - Links, tools, or references mentioned
5. **Summary** - A concise 2-3 paragraph summary

Return ONLY valid JSON in this format:
{{
  "title": "Short descriptive title",
  "topic": "Main topic",
  "date": "YYYY-MM-DD",
  "insights": ["insight 1", "insight 2", ...],
  "action_items": ["action 1", "action 2", ...],
  "resources": ["resource 1", "resource 2", ...],
  "summary": "Concise summary paragraphs"
}}""",
            },
            {
                "role": "user",
                "content": f"Please analyze this {service_name} conversation:\n\n{raw_content[:8000]}",
            },
        ]

        try:
            result = await self.llm.chat_json(messages, temperature=0.3)
            print(f"   ✅ Summarized: {result.get('title', 'Untitled')}")
            return result
        except Exception as e:
            print(f"   ⚠️  Summarization failed: {e}")
            return {
                "title": f"{service_name} Conversation",
                "topic": "Unknown",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "insights": [],
                "action_items": [],
                "resources": [],
                "summary": raw_content[:1000] if raw_content else "Extraction failed",
            }

    def create_obsidian_note(self, summary: dict, source_url: str, raw_content: str) -> str:
        """Create formatted Obsidian note from summary."""
        date_str = summary.get("date", datetime.now().strftime("%Y-%m-%d"))
        title = summary.get("title", "Untitled Conversation")

        # Create filename
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").rstrip()
        filename = f"Aily/Daily/{date_str} - {safe_title}.md"

        # Format content
        insights = "\n".join(f"- {i}" for i in summary.get("insights", []))
        actions = "\n".join(f"- [ ] {a}" for a in summary.get("action_items", []))
        resources = "\n".join(f"- {r}" for r in summary.get("resources", []))

        content = f"""---
aily_generated: true
aily_source: "{source_url}"
aily_type: "chat_extraction"
aily_created: "{datetime.now().isoformat()}"
topic: "{summary.get('topic', '')}"
---

# {title}

**Date:** {date_str}
**Source:** [{source_url}]({source_url})

## Summary

{summary.get('summary', 'No summary available')}

## Key Insights

{insights if insights else "- No specific insights extracted"}

## Action Items

{actions if actions else "- No action items"}

## Resources

{resources if resources else "- No resources mentioned"}

## Full Conversation

<details>
<summary>Click to expand full conversation</summary>

```
{raw_content[:5000] if raw_content else "No content extracted"}
```

</details>
"""
        return filename, content

    async def process(
        self,
        url: str,
        service_name: str = "AI Chat",
        use_personal_profile: bool = True,
        save_to_obsidian: bool = True,
    ) -> dict:
        """Full pipeline: extract, summarize, save."""
        print(f"\n{'='*60}")
        print(f"Processing {service_name} conversation")
        print(f"{'='*60}\n")

        # Step 1: Extract
        extraction_result = await self.extract_chat(
            url=url,
            service_name=service_name,
            use_personal_profile=use_personal_profile,
        )

        if extraction_result.get("status") != "ok":
            print(f"❌ Extraction failed: {extraction_result.get('message')}")
            return extraction_result

        raw_content = extraction_result.get("text", "")
        if not raw_content or len(raw_content) < 100:
            print(f"⚠️  Warning: Extracted content is very short")
            print(f"   Content: {raw_content[:200]}")

        print(f"\n   Extracted {len(raw_content)} characters")

        # Step 2: Summarize
        summary = await self.summarize_conversation(raw_content, service_name)

        # Step 3: Save to Obsidian
        if save_to_obsidian:
            print(f"\n💾 Saving to Obsidian...")
            filename, content = self.create_obsidian_note(summary, url, raw_content)

            try:
                result = self.writer.write_file(filename, content)
                print(f"   ✅ Saved to: {filename}")
                summary["obsidian_path"] = filename
                summary["obsidian_result"] = result
            except Exception as e:
                print(f"   ❌ Failed to save: {e}")
                summary["obsidian_error"] = str(e)

        print(f"\n{'='*60}")
        print(f"Done! Title: {summary.get('title')}")
        print(f"{'='*60}")

        return {
            "status": "ok",
            "url": url,
            "summary": summary,
            "raw_content_length": len(raw_content),
        }


async def main():
    parser = argparse.ArgumentParser(
        description="Extract authenticated chat content from Monica/Kimi"
    )
    parser.add_argument("url", help="URL of the chat conversation")
    parser.add_argument(
        "--service",
        choices=["monica", "kimi", "chatgpt", "claude", "custom"],
        default="custom",
        help="Service type (for better extraction prompts)",
    )
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Don't use personal Chrome profile (will likely fail for authenticated content)",
    )
    parser.add_argument(
        "--no-obsidian",
        action="store_true",
        help="Skip saving to Obsidian (just print to console)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Extraction timeout in seconds (default: 300)",
    )

    args = parser.parse_args()

    service_names = {
        "monica": "Monica AI",
        "kimi": "Kimi AI",
        "chatgpt": "ChatGPT",
        "claude": "Claude",
        "custom": "AI Chat",
    }

    extractor = AuthenticatedChatExtractor()
    result = await extractor.process(
        url=args.url,
        service_name=service_names[args.service],
        use_personal_profile=not args.no_profile,
        save_to_obsidian=not args.no_obsidian,
    )

    if result.get("status") == "ok":
        print(f"\n📝 Summary:")
        summary = result["summary"]
        print(f"   Title: {summary.get('title')}")
        print(f"   Topic: {summary.get('topic')}")
        print(f"   Insights: {len(summary.get('insights', []))}")
        print(f"   Actions: {len(summary.get('action_items', []))}")
        if "obsidian_path" in summary:
            print(f"   Saved to: {summary['obsidian_path']}")
    else:
        print(f"\n❌ Failed: {result.get('message')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
