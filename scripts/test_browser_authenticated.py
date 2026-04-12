#!/usr/bin/env python3
"""
Test script for Browser Use with authenticated Chrome profile.

This allows you to extract content from Monica/Kimi while logged in as yourself.

Prerequisites:
1. You must be logged into Monica/Kimi in your regular Chrome browser
2. Chrome must be closed before running this script (profile lock)

Usage:
    python scripts/test_browser_authenticated.py --url https://kimi.moonshot.cn
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.browser.manager import BrowserUseManager


async def test_authenticated_extraction(url: str, timeout: int = 120):
    """Extract content using your logged-in Chrome profile."""
    print(f"Testing authenticated extraction from: {url}")
    print("=" * 60)

    # Create manager with agent worker type
    browser = BrowserUseManager(
        worker_type="agent",
        llm_config={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": "",  # Will use OPENAI_API_KEY env var
        }
    )

    await browser.start()

    try:
        # Use personal profile - this will use your Chrome where you're logged in
        print("\nUsing your personal Chrome profile (where you're logged in)...")
        print("Note: Chrome must be closed for this to work (profile lock)")
        print("Note: Browser will be visible (headless=False)\n")

        result = await browser.fetch(url, timeout=timeout, use_personal_profile=True)

        print("\n" + "=" * 60)
        print("EXTRACTION RESULT")
        print("=" * 60)
        print(result[:3000] if len(result) > 3000 else result)
        print("=" * 60)

        # Check for content indicators
        success_indicators = [
            len(result) > 500,  # Substantial content
            "chat" in result.lower() or "conversation" in result.lower(),
            "kimi" in result.lower() or "monica" in result.lower(),
        ]

        print("\nValidation:")
        print(f"  - Content length: {len(result)} chars")
        print(f"  - Has chat content: {'✓' if success_indicators[1] else '✗'}")
        print(f"  - Service detected: {'✓' if success_indicators[2] else '✗'}")

        all_passed = all(success_indicators)
        print(f"\nOverall: {'✓ SUCCESS' if all_passed else '⚠ PARTIAL'}")

        return result

    finally:
        await browser.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Test Browser Use with authenticated Chrome profile"
    )
    parser.add_argument(
        "--url",
        default="https://kimi.moonshot.cn",
        help="URL to extract (default: https://kimi.moonshot.cn)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout in seconds (default: 120)"
    )

    args = parser.parse_args()

    # Check for OPENAI_API_KEY
    import os
    if not os.environ.get("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not set. Set it to use the agent.")
        print("You can still run but the agent won't work without an API key.")
        print()

    # Run the test
    result = asyncio.run(test_authenticated_extraction(args.url, args.timeout))

    # Save result
    output_file = Path("tests/browser_authenticated_result.md")
    output_file.write_text(f"""# Authenticated Browser Extraction Result

**URL:** {args.url}
**Date:** {asyncio.get_event_loop().time()}

## Extracted Content

```
{result[:5000]}
```

{'(truncated...)' if len(result) > 5000 else ''}
""")
    print(f"\nResult saved to: {output_file}")


if __name__ == "__main__":
    main()
