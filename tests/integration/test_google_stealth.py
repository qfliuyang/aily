"""
Google Search Anti-Bot Test using Playwright Stealth.

Tests if playwright-stealth can bypass Google's reCAPTCHA detection.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_google_search_with_stealth(
    visual_browser_page,
    visual_helper,
    exposure,
    test_id: str,
) -> None:
    """
    Attempt Google search with stealth mode enabled.

    EXPOSES: Anti-bot detection, CAPTCHA triggers, stealth effectiveness.
    """
    page, artifacts_dir = visual_browser_page
    helper = visual_helper(page, artifacts_dir, exposure)

    test_query = "What is the weight of LLM"

    try:
        # Navigate to Google
        await page.goto("https://www.google.com", timeout=30000)
        await page.wait_for_timeout(2000)  # Let page settle

        # Screenshot: Initial load
        await helper.screenshot("01_google_home")

        # Find and fill search box
        search_box = await page.query_selector("textarea[name='q'], input[name='q']")
        if not search_box:
            # Try alternative selectors
            search_box = await page.query_selector("[role='combobox']")

        if search_box:
            await search_box.click()
            await search_box.fill(test_query)
            await helper.screenshot("02_query_typed")

            # Submit search
            await search_box.press("Enter")
            await page.wait_for_timeout(3000)

            # Screenshot: Results or CAPTCHA
            await helper.screenshot("03_search_results")

            # Check for CAPTCHA
            captcha_selectors = [
                "#captcha",
                ".g-recaptcha",
                "iframe[src*='recaptcha']",
                "text=I'm not a robot",
                "text=Verify you're human",
            ]

            captcha_found = False
            for selector in captcha_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        captcha_found = True
                        exposure.expose("RECAPTCHA_DETECTED", f"CAPTCHA found: {selector}", {
                            "selector": selector,
                            "query": test_query,
                        })
                        break
                except Exception:
                    pass

            if captcha_found:
                exposure.expose("STEALTH_FAILED", "playwright-stealth did not bypass detection", {
                    "recommendation": "May need additional evasion techniques or residential proxy",
                })
            else:
                # Check if we got actual search results
                result_selectors = [
                    "#search",
                    "#rso",
                    ".g",
                    "[data-header-feature]",
                ]

                results_found = False
                for selector in result_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            results_found = True
                            break
                    except Exception:
                        pass

                if results_found:
                    exposure.expose("STEALTH_SUCCESS", "Google search completed without CAPTCHA", {
                        "query": test_query,
                    })
                else:
                    exposure.expose("UNKNOWN_STATE", "Neither CAPTCHA nor results detected", {
                        "page_title": await page.title(),
                        "url": page.url,
                    })
        else:
            exposure.expose("SEARCH_BOX_NOT_FOUND", "Could not locate Google search box", {
                "page_title": await page.title(),
            })

    except Exception as e:
        await helper.screenshot("error_state")
        exposure.expose("GOOGLE_TEST_FAILED", str(e), {
            "error_type": type(e).__name__,
        })
        raise

    finally:
        # Report artifacts
        report = helper.get_artifacts_report()
        exposure.expose("VISUAL_ARTIFACTS", f"Captured {report['total_artifacts']} artifacts", report)


def pytest_sessionfinish(session, exitstatus):
    """Print summary after test."""
    print("\n" + "="*70)
    print("GOOGLE STEALTH TEST SUMMARY")
    print("="*70)
    print(f"Test completed at: {datetime.now(timezone.utc).isoformat()}")
    print("Check test-artifacts/ for screenshots")
    print("="*70)
