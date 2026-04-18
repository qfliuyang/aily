#!/usr/bin/env python3
"""
Extract Monica conversation, summarize with LLM, save to Obsidian.

Tests all configured services:
- Browser Use (local or API) for extraction
- Kimi for summarization
- Obsidian for permanent storage
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.config import SETTINGS
from aily.browser.manager import BrowserUseManager
from aily.llm.client import LLMClient
from aily.writer.obsidian import ObsidianWriter


class MonicaToObsidianPipeline:
    """Pipeline to extract Monica chat, summarize, and save to Obsidian."""

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

    async def extract_with_browser_use_api(self, url: str, timeout: int = 180) -> str:
        """Extract content using Browser Use commercial API."""
        print(f"🔍 Extracting from: {url}")
        print(f"   Using Browser Use commercial API")

        import os
        import requests
        import time

        api_key = os.environ.get("BROWSER_USE_API_KEY") or SETTINGS.__dict__.get("browser_use_api_key", "")
        if not api_key:
            raise Exception("BROWSER_USE_API_KEY not configured")

        base_url = "https://api.browser-use.com/api/v3"

        # Create session
        headers = {
            "X-Browser-Use-API-Key": api_key,
            "Content-Type": "application/json"
        }

        task_prompt = f"""Navigate to {url} and extract the conversation content.

You are viewing a Monica chat conversation. Your task:
1. Navigate to the URL and wait for it to load
2. Look for chat messages, conversation threads, or dialogue content
3. Extract all visible conversation text (both user and assistant messages)
4. Preserve the structure - identify who said what
5. If you see a chat interface, explore it to find the full conversation
6. Return the complete conversation text

Be thorough and capture as much of the conversation as possible."""

        print("   Creating Browser Use session...")
        response = requests.post(
            f"{base_url}/sessions",
            headers=headers,
            json={"task": task_prompt, "max_steps": 30},
            timeout=30
        )
        response.raise_for_status()
        session = response.json()
        session_id = session["id"]
        print(f"   Session created: {session_id}")

        # Poll for completion
        print("   Waiting for extraction (this may take 1-2 minutes)...")
        max_wait = timeout
        poll_interval = 5

        for i in range(0, max_wait, poll_interval):
            await asyncio.sleep(poll_interval)

            resp = requests.get(
                f"{base_url}/sessions/{session_id}",
                headers=headers,
                timeout=30
            )
            data = resp.json()
            status = data.get("status", "unknown")

            if status == "completed":
                output = data.get("output", "")
                print(f"   ✅ Extraction completed in {i + poll_interval}s")
                return output
            elif status in ("failed", "error"):
                raise Exception(f"Browser Use task failed: {data}")
            elif i % 30 == 0:
                print(f"   ... still working ({i}s)")

        raise TimeoutError(f"Extraction did not complete within {max_wait} seconds")

    async def extract_with_browser(
        self,
        url: str,
        use_personal_profile: bool = True,
        timeout: int = 180,
    ) -> str:
        """Extract content from Monica using browser automation."""
        print(f"🔍 Extracting from: {url}")

        # Try Browser Use API first (more reliable)
        try:
            return await self.extract_with_browser_use_api(url, timeout)
        except Exception as e:
            print(f"   Browser Use API failed: {e}")
            print(f"   Falling back to local browser...")

        # Fallback to local browser-use
        print(f"   Using personal Chrome profile: {use_personal_profile}")

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
            result = await browser.fetch(
                url,
                timeout=timeout,
                use_personal_profile=use_personal_profile,
            )
            return result
        finally:
            await browser.stop()

    async def summarize_conversation(self, raw_content: str) -> dict:
        """Use LLM to summarize the conversation into structured knowledge."""
        print("\n🧠 Summarizing with Kimi...")

        messages = [
            {
                "role": "system",
                "content": """You are a knowledge curator. Analyze the conversation and create a well-structured knowledge card.

Extract and organize:
1. **Main Topic** - What is this conversation about?
2. **Key Insights** - 3-5 important points or learnings
3. **Action Items** - Any tasks, decisions, or follow-ups mentioned
4. **Resources** - Links, tools, or references mentioned
5. **Summary** - A concise 2-3 paragraph summary

Return ONLY valid JSON in this format:
{
  "title": "Short descriptive title",
  "topic": "Main topic",
  "date": "YYYY-MM-DD",
  "insights": ["insight 1", "insight 2", ...],
  "action_items": ["action 1", "action 2", ...],
  "resources": ["resource 1", "resource 2", ...],
  "summary": "Concise summary text"
}"""
            },
            {
                "role": "user",
                "content": f"Please analyze and summarize this Monica conversation:\n\n{raw_content[:15000]}"  # Limit context
            }
        ]

        try:
            result = await self.llm.chat_json(messages, temperature=0.3)
            return result
        except Exception as e:
            print(f"⚠️  LLM summarization failed: {e}")
            # Fallback: return basic structure
            return {
                "title": "Monica Conversation Summary",
                "topic": "Conversation",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "insights": ["Extraction completed but summarization failed"],
                "action_items": [],
                "resources": [],
                "summary": raw_content[:2000] + "..." if len(raw_content) > 2000 else raw_content,
            }

    def format_knowledge_card(self, data: dict, source_url: str) -> str:
        """Format the summary as a beautiful Obsidian note."""
        date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
        title = data.get("title", "Monica Conversation")

        markdown = f"""# {title}

> 📅 **Date:** {date}
> 🔗 **Source:** [Monica Conversation]({source_url})
> 🤖 **Generated by:** Aily Knowledge Pipeline

## 🎯 Topic

{data.get("topic", "N/A")}

## 📝 Summary

{data.get("summary", "No summary available")}

## 💡 Key Insights

"""
        for i, insight in enumerate(data.get("insights", []), 1):
            markdown += f"{i}. {insight}\n"

        if data.get("action_items"):
            markdown += """
## ✅ Action Items

"""
            for item in data.get("action_items", []):
                markdown += f"- [ ] {item}\n"

        if data.get("resources"):
            markdown += """
## 🔗 Resources

"""
            for resource in data.get("resources", []):
                markdown += f"- {resource}\n"

        markdown += """
---

## 🧠 Permanent Memory

This note was automatically generated from a Monica conversation and saved as part of your knowledge base.

#knowledge-card #monica #ai-conversation
"""
        return markdown

    async def run(
        self,
        url: str,
        use_personal_profile: bool = True,
    ) -> str:
        """Run the complete pipeline."""
        print("=" * 60)
        print("🚀 Monica to Obsidian Pipeline")
        print("=" * 60)

        # Step 1: Extract
        raw_content = await self.extract_with_browser(url, use_personal_profile)
        if not raw_content or len(raw_content) < 100:
            raise Exception("Failed to extract meaningful content from Monica")

        print(f"\n✅ Extracted {len(raw_content)} characters")

        # Step 2: Summarize
        summary_data = await self.summarize_conversation(raw_content)
        print(f"✅ Summary generated: {summary_data.get('title', 'Untitled')}")

        # Step 3: Format
        markdown = self.format_knowledge_card(summary_data, url)

        # Step 4: Save to Obsidian
        safe_title = summary_data.get("title", "Monica Conversation").replace("/", "_")[:80]
        note_path = await self.writer.write_note(
            title=f"Monica-{safe_title}",
            markdown=markdown,
            source_url=url,
        )
        print(f"\n✅ Saved to Obsidian: {note_path}")

        # Step 5: Print knowledge card
        print("\n" + "=" * 60)
        print("📇 KNOWLEDGE CARD")
        print("=" * 60)
        print(markdown)
        print("=" * 60)

        return markdown


def main():
    parser = argparse.ArgumentParser(description="Extract Monica conversation to Obsidian")
    parser.add_argument(
        "--url",
        default="https://monica.im/home/chat/Monica/monica?convId=conv%3Ab743d1ff-7dc1-4c59-8f0d-43d054fc15a7",
        help="Monica conversation URL"
    )
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Don't use personal Chrome profile (anonymous mode)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Save markdown to file (optional)"
    )

    args = parser.parse_args()

    # Check prerequisites
    if not SETTINGS.obsidian_rest_api_key:
        print("❌ Error: OBSIDIAN_REST_API_KEY not configured")
        sys.exit(1)
    if not SETTINGS.llm_api_key:
        print("❌ Error: LLM_API_KEY not configured")
        sys.exit(1)

    # Run pipeline
    pipeline = MonicaToObsidianPipeline()

    try:
        result = asyncio.run(pipeline.run(
            url=args.url,
            use_personal_profile=not args.no_profile,
        ))

        if args.output:
            Path(args.output).write_text(result, encoding="utf-8")
            print(f"\n💾 Also saved to: {args.output}")

        print("\n✨ Pipeline completed successfully!")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
