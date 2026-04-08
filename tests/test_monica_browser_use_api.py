#!/usr/bin/env python3
"""
Test script for Browser Use Commercial API with Monica chat pages.

Tests:
1. Navigate to monica.im and explore the site structure
2. Try to access any public/shared chat features
3. Note any anti-bot detection (CAPTCHA, blocks, rate limits)
4. Document what content was successfully extracted vs what failed

Usage:
    python tests/test_monica_browser_use_api.py

Requirements:
    - browser-use-sdk installed
    - BROWSER_USE_API_KEY environment variable or --api-key flag
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from browser_use_sdk import BrowserUse


class MonicaBrowserUseTester:
    """Test Browser Use commercial API with Monica chat pages."""

    def __init__(self, api_key: str):
        self.client = BrowserUse(api_key=api_key)
        self.results: list[dict] = []
        self.output_dir = Path("tests/browser_use_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def run_test(
        self,
        name: str,
        task: str,
        start_url: str | None = None,
        max_steps: int = 10,
        llm: str = "browser-use-2.0",
    ) -> dict[str, Any]:
        """Run a single browser automation test."""
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print(f"{'='*60}")
        print(f"Task: {task[:100]}...")
        print(f"Start URL: {start_url}")
        print(f"Max Steps: {max_steps}")

        result = {
            "name": name,
            "task": task,
            "start_url": start_url,
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "error": None,
            "task_id": None,
            "output": None,
            "steps": None,
            "duration_seconds": None,
        }

        start_time = asyncio.get_event_loop().time()

        try:
            # Create the task
            create_params = {
                "task": task,
                "llm": llm,
                "max_steps": max_steps,
                "vision": True,
            }
            if start_url:
                create_params["start_url"] = start_url

            task_response = self.client.tasks.create_task(**create_params)
            result["task_id"] = task_response.id
            print(f"Task created: {task_response.id}")

            # Poll for task completion
            output = await self._poll_task(task_response.id, timeout=300)
            result["output"] = output
            result["success"] = True
            print(f"✓ Test completed successfully")

        except Exception as e:
            result["error"] = str(e)
            print(f"✗ Test failed: {e}")

        result["duration_seconds"] = asyncio.get_event_loop().time() - start_time
        self.results.append(result)
        return result

    async def _poll_task(self, task_id: str, timeout: int = 300) -> dict:
        """Poll a task until completion."""
        import time

        start_time = time.time()
        check_interval = 5

        while time.time() - start_time < timeout:
            task_status = self.client.tasks.get_task(task_id)

            # Get task status
            status = task_status.status if hasattr(task_status, 'status') else 'unknown'
            print(f"  Status: {status} ({int(time.time() - start_time)}s)")

            if status == "completed":
                # Get full output
                output = {}
                if hasattr(task_status, 'output'):
                    output['output'] = task_status.output
                if hasattr(task_status, 'steps'):
                    output['steps'] = task_status.steps
                if hasattr(task_status, 'text'):
                    output['text'] = task_status.text
                return output

            elif status in ("failed", "error", "cancelled"):
                error_msg = "Unknown error"
                if hasattr(task_status, 'error'):
                    error_msg = task_status.error
                raise Exception(f"Task {status}: {error_msg}")

            await asyncio.sleep(check_interval)

        raise TimeoutError(f"Task did not complete within {timeout} seconds")

    async def test_monica_homepage(self) -> dict:
        """Test 1: Navigate to Monica.im homepage and explore structure."""
        return await self.run_test(
            name="Monica Homepage Structure",
            task="""
Navigate to monica.im and analyze the website structure.

Your task:
1. Navigate to https://monica.im
2. Wait for the page to fully load
3. Identify the main sections of the site (header, navigation, main content, footer)
4. Look for any chat-related features or links
5. Check if there are any public/shared chat examples or demos
6. Document any login/signup walls you encounter
7. Return a detailed summary of:
   - Page title and description
   - Main navigation items found
   - Any chat-related features visible
   - Whether public chats are accessible
   - Any CAPTCHA or anti-bot detection encountered
""",
            start_url="https://monica.im",
            max_steps=15,
        )

    async def test_monica_chat_exploration(self) -> dict:
        """Test 2: Try to find and access chat features."""
        return await self.run_test(
            name="Monica Chat Features Exploration",
            task="""
Explore Monica.im to find chat-related features and document accessibility.

Your task:
1. Navigate to https://monica.im
2. Look for links to chat features, examples, or shared conversations
3. Try to find any "Examples", "Demos", "Shared Chats", or similar sections
4. Check the footer for useful links
5. If you find any chat interface, try to understand if it's public or requires login
6. Document any authentication requirements
7. Return:
   - All chat-related links/features found
   - Whether they require authentication
   - Any error messages or blocks encountered
   - Screenshots of key findings (if possible)
""",
            start_url="https://monica.im",
            max_steps=20,
        )

    async def test_monica_shared_chat(self, chat_url: str | None = None) -> dict:
        """Test 3: Try to access a specific shared chat URL if available."""
        if not chat_url:
            # Try a hypothetical shared chat URL pattern
            chat_url = "https://monica.im/chat"

        return await self.run_test(
            name=f"Monica Shared Chat Access ({chat_url})",
            task=f"""
Attempt to access a Monica chat page and extract content.

Your task:
1. Navigate to {chat_url}
2. Wait for the page to fully load (allow up to 30 seconds)
3. Check if the page loads successfully or if there's an error/redirect
4. If a chat interface loads:
   - Document the chat structure
   - Try to extract any visible messages or content
   - Note if it requires login to view
5. If blocked, document:
   - Type of block (CAPTCHA, login wall, 404, etc.)
   - Any error messages
   - Whether a retry might work
6. Return detailed findings including:
   - Page accessibility status
   - Content extracted (if any)
   - Authentication requirements
   - Anti-bot measures encountered
""",
            start_url=chat_url,
            max_steps=15,
        )

    async def test_monica_api_endpoints(self) -> dict:
        """Test 4: Check common API endpoints and document findings."""
        return await self.run_test(
            name="Monica API Endpoint Check",
            task="""
Explore Monica.im for API endpoints and developer documentation.

Your task:
1. Navigate to https://monica.im
2. Look for:
   - API documentation links
   - Developer sections
   - Terms of service
   - Robots.txt (check /robots.txt)
3. Document any rate limiting information
4. Check if there are public API endpoints
5. Return:
   - Any API documentation found
   - Terms of service relevant to scraping
   - Rate limit information
   - robots.txt content
""",
            start_url="https://monica.im",
            max_steps=15,
        )

    def generate_report(self) -> str:
        """Generate a markdown report of all test results."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"monica_test_report_{timestamp}.md"

        report_lines = [
            "# Browser Use Commercial API - Monica Chat Extraction Test Report",
            f"\n**Generated:** {datetime.now().isoformat()}",
            f"**Total Tests:** {len(self.results)}",
            f"**Successful:** {sum(1 for r in self.results if r['success'])}",
            f"**Failed:** {sum(1 for r in self.results if not r['success'])}",
            "\n---\n",
        ]

        for i, result in enumerate(self.results, 1):
            report_lines.extend([
                f"\n## Test {i}: {result['name']}",
                f"\n**Status:** {'✅ SUCCESS' if result['success'] else '❌ FAILED'}",
                f"**Timestamp:** {result['timestamp']}",
                f"**Duration:** {result['duration_seconds']:.1f}s",
                f"**Task ID:** {result['task_id'] or 'N/A'}",
                f"\n**URL:** {result['start_url'] or 'N/A'}",
                "\n**Task Description:**",
                f"```\n{result['task'][:500]}...\n```",
            ])

            if result['success'] and result['output']:
                report_lines.extend([
                    "\n**Output:**",
                    "```json",
                    json.dumps(result['output'], indent=2, default=str)[:2000],
                    "```",
                ])

            if result['error']:
                report_lines.extend([
                    "\n**Error:**",
                    f"```\n{result['error']}\n```",
                ])

            report_lines.append("\n---\n")

        # Summary and recommendations
        report_lines.extend([
            "\n## Summary and Recommendations\n",
            "### Findings\n",
        ])

        # Analyze results for common patterns
        anti_bot_detected = any(
            "captcha" in str(r.get('error', '')).lower() or
            "blocked" in str(r.get('output', '')).lower()
            for r in self.results
        )

        login_required = any(
            "login" in str(r.get('output', '')).lower() or
            "auth" in str(r.get('output', '')).lower()
            for r in self.results
        )

        report_lines.extend([
            f"- **Anti-bot detection encountered:** {'Yes' if anti_bot_detected else 'No'}",
            f"- **Login required for chats:** {'Yes' if login_required else 'Unknown'}",
            "\n### Recommendations\n",
        ])

        if anti_bot_detected:
            report_lines.append(
                "1. **Use session persistence:** Consider using Browser Use sessions "
                "to maintain state across requests."
            )
        else:
            report_lines.append(
                "1. **No significant anti-bot detected:** The commercial API appears "
                "to work well for basic navigation."
            )

        report_lines.extend([
            "2. **Rate limiting:** Monitor API usage and implement backoff if needed.",
            "3. **Authentication:** If chats require login, consider using the secrets "
            "feature of Browser Use API for authenticated access.",
        ])

        report_content = "\n".join(report_lines)
        report_path.write_text(report_content, encoding="utf-8")

        return str(report_path)

    def save_raw_results(self) -> str:
        """Save raw JSON results."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_path = self.output_dir / f"monica_test_results_{timestamp}.json"

        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, default=str)

        return str(results_path)


async def main():
    parser = argparse.ArgumentParser(
        description="Test Browser Use Commercial API with Monica chat pages"
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("BROWSER_USE_API_KEY"),
        help="Browser Use API key (or set BROWSER_USE_API_KEY env var)",
    )
    parser.add_argument(
        "--test",
        choices=["all", "homepage", "chat", "api", "shared"],
        default="all",
        help="Which test to run",
    )
    parser.add_argument(
        "--shared-url",
        help="Specific shared chat URL to test (for 'shared' test)",
    )

    args = parser.parse_args()

    if not args.api_key:
        print("Error: API key required. Use --api-key or set BROWSER_USE_API_KEY env var.")
        sys.exit(1)

    tester = MonicaBrowserUseTester(api_key=args.api_key)

    print("=" * 60)
    print("Browser Use Commercial API - Monica Chat Test Suite")
    print("=" * 60)

    # Run selected tests
    if args.test in ("all", "homepage"):
        await tester.test_monica_homepage()

    if args.test in ("all", "chat"):
        await tester.test_monica_chat_exploration()

    if args.test in ("all", "api"):
        await tester.test_monica_api_endpoints()

    if args.test in ("all", "shared"):
        await tester.test_monica_shared_chat(args.shared_url)

    # Generate reports
    print("\n" + "=" * 60)
    print("Generating Reports")
    print("=" * 60)

    report_path = tester.generate_report()
    results_path = tester.save_raw_results()

    print(f"✓ Report saved: {report_path}")
    print(f"✓ Raw results saved: {results_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for r in tester.results:
        status = "✅ PASS" if r['success'] else "❌ FAIL"
        print(f"{status} - {r['name']} ({r['duration_seconds']:.1f}s)")

    # Exit with appropriate code
    all_passed = all(r['success'] for r in tester.results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
