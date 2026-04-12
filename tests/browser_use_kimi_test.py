#!/usr/bin/env python3
"""
Test Browser Use Commercial API with Kimi chat page.

Tests:
1. Navigate to kimi.moonshot.cn
2. Extract content from Kimi chat page
3. Document anti-bot detection (CAPTCHA, blocks, rate limits)
4. Compare extraction results

Usage:
    BROWSER_USE_API_KEY=your_key python tests/browser_use_kimi_test.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from browser_use.browser.cloud.cloud import CloudBrowserClient
from browser_use.browser.cloud.views import CreateBrowserRequest


# Test API key from task
DEFAULT_API_KEY = "bu_cr_lbyBviJBUvnw4b1-hNQdLSEi3aALlTIjSYVE1Zso"


class KimiBrowserTest:
    """Test Browser Use API with Kimi chat pages."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("BROWSER_USE_API_KEY") or DEFAULT_API_KEY
        self.results: list[dict] = []
        self.client = CloudBrowserClient()

    async def test_kimi_homepage(self) -> dict:
        """Test accessing Kimi homepage."""
        print("\n" + "=" * 60)
        print("TEST 1: Kimi Homepage (kimi.moonshot.cn)")
        print("=" * 60)

        browser = None
        try:
            # Create cloud browser
            request = CreateBrowserRequest(
                proxy_country_code="us",
                timeout=10
            )

            # Set API key in environment for the client
            os.environ["BROWSER_USE_API_KEY"] = self.api_key

            browser = await self.client.create_browser(request)
            print(f"✓ Browser created: {browser.id}")
            print(f"  Live URL: {browser.liveUrl}")
            print(f"  CDP URL: {browser.cdpUrl[:60]}...")

            # Now we need to use playwright to connect to this CDP URL
            result = await self._extract_with_playwright(
                cdp_url=browser.cdpUrl,
                url="https://kimi.moonshot.cn",
                task="Navigate to the page and extract the main content, structure, and any visible chat interface"
            )

            test_result = {
                "test": "kimi_homepage",
                "url": "https://kimi.moonshot.cn",
                "success": result.get("success", False),
                "browser_id": browser.id,
                "live_url": browser.liveUrl,
                "content_preview": result.get("content", "")[:500] if result.get("content") else None,
                "anti_bot_detected": result.get("anti_bot", False),
                "anti_bot_type": result.get("anti_bot_type"),
                "error": result.get("error"),
                "timestamp": datetime.now().isoformat(),
            }

            self.results.append(test_result)
            return test_result

        except Exception as e:
            error_result = {
                "test": "kimi_homepage",
                "url": "https://kimi.moonshot.cn",
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat(),
            }
            self.results.append(error_result)
            return error_result
        finally:
            if browser:
                try:
                    await self.client.stop_browser(browser.id)
                    print("✓ Browser stopped")
                except Exception as e:
                    print(f"⚠ Error stopping browser: {e}")

    async def test_kimi_chat_page(self) -> dict:
        """Test accessing a Kimi chat page (if publicly accessible)."""
        print("\n" + "=" * 60)
        print("TEST 2: Kimi Chat Interface")
        print("=" * 60)

        browser = None
        try:
            os.environ["BROWSER_USE_API_KEY"] = self.api_key

            request = CreateBrowserRequest(
                proxy_country_code="us",
                timeout=10
            )

            browser = await self.client.create_browser(request)
            print(f"✓ Browser created: {browser.id}")

            # Try to navigate and explore the chat interface
            result = await self._extract_with_playwright(
                cdp_url=browser.cdpUrl,
                url="https://kimi.moonshot.cn",
                task="""
                Navigate to Kimi and:
                1. Check if there's a chat interface visible
                2. Look for any "share" or "public chat" features
                3. Document the page structure
                4. Check if login is required to access chat features
                5. Look for any anti-bot measures (CAPTCHA, verification)
                Return a detailed report of findings.
                """
            )

            test_result = {
                "test": "kimi_chat_interface",
                "url": "https://kimi.moonshot.cn",
                "success": result.get("success", False),
                "browser_id": browser.id,
                "chat_interface_found": "chat" in (result.get("content", "")).lower(),
                "login_required": "login" in (result.get("content", "")).lower() or "登录" in (result.get("content", "")).lower(),
                "content_preview": result.get("content", "")[:800] if result.get("content") else None,
                "anti_bot_detected": result.get("anti_bot", False),
                "anti_bot_type": result.get("anti_bot_type"),
                "error": result.get("error"),
                "timestamp": datetime.now().isoformat(),
            }

            self.results.append(test_result)
            return test_result

        except Exception as e:
            error_result = {
                "test": "kimi_chat_interface",
                "url": "https://kimi.moonshot.cn",
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat(),
            }
            self.results.append(error_result)
            return error_result
        finally:
            if browser:
                try:
                    await self.client.stop_browser(browser.id)
                    print("✓ Browser stopped")
                except Exception as e:
                    print(f"⚠ Error stopping browser: {e}")

    async def test_api_connectivity(self) -> dict:
        """Test basic API connectivity without creating a browser."""
        print("\n" + "=" * 60)
        print("TEST 0: API Connectivity Check")
        print("=" * 60)

        try:
            async with httpx.AsyncClient() as client:
                # Try to hit the API health endpoint or similar
                response = await client.get(
                    "https://api.browser-use.com/api/v2/browsers",
                    headers={"X-Browser-Use-API-Key": self.api_key},
                    timeout=10.0
                )

                result = {
                    "test": "api_connectivity",
                    "success": response.status_code in [200, 401, 403],  # Any of these means API is reachable
                    "status_code": response.status_code,
                    "response_preview": response.text[:200] if response.text else None,
                    "timestamp": datetime.now().isoformat(),
                }

                if response.status_code == 200:
                    print(f"✓ API is accessible (status {response.status_code})")
                elif response.status_code == 401:
                    print(f"⚠ API returned 401 - Authentication issue")
                elif response.status_code == 403:
                    print(f"⚠ API returned 403 - Forbidden")
                else:
                    print(f"⚠ API returned {response.status_code}")

                self.results.append(result)
                return result

        except Exception as e:
            error_result = {
                "test": "api_connectivity",
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat(),
            }
            self.results.append(error_result)
            print(f"✗ API connectivity failed: {e}")
            return error_result

    async def _extract_with_playwright(
        self,
        cdp_url: str,
        url: str,
        task: str,
        timeout: int = 60
    ) -> dict:
        """Use playwright to connect to cloud browser and extract content."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                # Connect to the cloud browser via CDP
                browser = await p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = context.pages[0] if context.pages else await context.new_page()

                print(f"  Navigating to {url}...")

                # Navigate with longer timeout
                response = await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)

                print(f"  Page loaded: {response.status if response else 'unknown'}")

                # Wait a bit for any dynamic content
                await asyncio.sleep(3)

                # Check for anti-bot indicators
                anti_bot_indicators = await self._detect_anti_bot(page)

                # Get page content
                title = await page.title()
                content = await page.content()

                # Extract text content
                text_content = await page.evaluate("""
                    () => {
                        const body = document.body;
                        if (!body) return '';
                        return body.innerText;
                    }
                """)

                await browser.close()

                return {
                    "success": True,
                    "title": title,
                    "content": text_content[:2000] if text_content else content[:2000],
                    "anti_bot": anti_bot_indicators["detected"],
                    "anti_bot_type": anti_bot_indicators["type"],
                    "http_status": response.status if response else None,
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "anti_bot": "timeout" in str(e).lower() or "navigating" in str(e).lower(),
            }

    async def _detect_anti_bot(self, page) -> dict:
        """Detect anti-bot measures on the page."""
        indicators = {
            "captcha": [
                "captcha", "recaptcha", "g-recaptcha", "hcaptcha",
                "验证码", "安全验证"
            ],
            "blocked": [
                "access denied", "blocked", "forbidden", "403",
                "ip blocked", "rate limit", "too many requests"
            ],
            "verification": [
                "verify you are human", "verification required",
                "prove you're not a robot", "安全检查"
            ]
        }

        page_text = await page.evaluate("() => document.body?.innerText?.toLowerCase() || ''")
        page_html = await page.content()
        page_html_lower = page_html.lower()

        for anti_type, keywords in indicators.items():
            for keyword in keywords:
                if keyword in page_text or keyword in page_html_lower:
                    print(f"  ⚠ Anti-bot detected: {anti_type.upper()}")
                    return {"detected": True, "type": anti_type}

        return {"detected": False, "type": None}

    async def run_all_tests(self) -> list[dict]:
        """Run all tests."""
        print("\n" + "=" * 60)
        print("BROWSER USE API - KIMI CHAT PAGE EXTRACTION TEST")
        print("=" * 60)
        print(f"API Key: {self.api_key[:20]}...")

        # Test 0: API connectivity
        await self.test_api_connectivity()

        # Test 1: Homepage
        await self.test_kimi_homepage()

        # Test 2: Chat interface
        await self.test_kimi_chat_page()

        return self.results

    def generate_report(self) -> str:
        """Generate markdown report."""
        report_lines = [
            "# Browser Use API - Kimi Chat Page Extraction Test Results",
            "",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**API Key:** {self.api_key[:20]}...",
            "",
            "## Summary",
            "",
        ]

        for result in self.results:
            test_name = result.get("test", "unknown")
            success = result.get("success", False)
            status = "✓ PASS" if success else "✗ FAIL"

            report_lines.extend([
                f"### {test_name}",
                f"**Status:** {status}",
            ])

            if "url" in result:
                report_lines.append(f"**URL:** {result['url']}")

            if "status_code" in result:
                report_lines.append(f"**HTTP Status:** {result['status_code']}")

            if "anti_bot_detected" in result:
                detected = result["anti_bot_detected"]
                bot_type = result.get("anti_bot_type", "unknown")
                report_lines.append(f"**Anti-bot Detected:** {'Yes' if detected else 'No'}")
                if detected:
                    report_lines.append(f"**Anti-bot Type:** {bot_type}")

            if "content_preview" in result and result["content_preview"]:
                report_lines.extend([
                    "",
                    "**Content Preview:**",
                    "```",
                    result["content_preview"][:500],
                    "```",
                ])

            if "error" in result and result["error"]:
                report_lines.extend([
                    "",
                    f"**Error:** `{result['error']}`",
                ])
                if "error_type" in result:
                    report_lines.append(f"**Error Type:** {result['error_type']}")

            report_lines.append("")

        # Add recommendations
        report_lines.extend([
            "## Recommendations",
            "",
            "Based on the test results:",
            "",
        ])

        any_anti_bot = any(r.get("anti_bot_detected") for r in self.results)
        any_failures = any(not r.get("success") for r in self.results)

        if any_anti_bot:
            report_lines.append("1. **Anti-bot measures detected** - Consider using residential proxies or rotating IPs")
            report_lines.append("2. **Rate limiting may apply** - Implement delays between requests")
        elif any_failures:
            report_lines.append("1. **API connectivity issues** - Check API key and subscription status")
            report_lines.append("2. **Browser creation failed** - Verify API limits and quotas")
        else:
            report_lines.append("1. **No anti-bot measures detected** - Standard extraction should work")
            report_lines.append("2. **API is functional** - Ready for production use")

        report_lines.extend([
            "",
            "## Raw JSON Data",
            "",
            "```json",
            json.dumps(self.results, indent=2, default=str),
            "```",
        ])

        return "\n".join(report_lines)


async def main():
    """Main entry point."""
    test = KimiBrowserTest()
    await test.run_all_tests()

    # Generate report
    report = test.generate_report()

    # Save to file
    output_path = Path(__file__).parent / "browser_use_kimi_results.md"
    output_path.write_text(report)
    print(f"\n✓ Report saved to: {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for result in test.results:
        status = "✓" if result.get("success") else "✗"
        print(f"{status} {result['test']}")

    return test.results


if __name__ == "__main__":
    results = asyncio.run(main())
    sys.exit(0 if all(r.get("success") for r in results) else 1)
