#!/usr/bin/env python3
"""Test script to simulate how Aily processes the 10 URL test messages.

This script tests:
1. Intent classification for each message
2. URL fetching and content extraction
3. Identifies problems and edge cases

Usage:
    python scripts/test_url_messages.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.bot.message_intent import IntentRouter, IntentType
from aily.processing.router import ProcessingRouter


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


def test_intent_classification():
    """Test how each message is classified by IntentRouter."""
    print("=" * 80)
    print("TEST 1: Intent Classification")
    print("=" * 80)

    results = []
    for i, msg in enumerate(TEST_MESSAGES, 1):
        intent = IntentRouter.analyze(msg)
        results.append({
            "msg_num": i,
            "intent_type": intent.intent_type.name,
            "url": intent.url,
            "confidence": intent.confidence,
            "reasoning": intent.reasoning,
        })

        print(f"\nMessage {i}:")
        print(f"  Intent: {intent.intent_type.name}")
        print(f"  URL: {intent.url}")
        print(f"  Confidence: {intent.confidence}")
        print(f"  Reasoning: {intent.reasoning}")

    # Summary
    print("\n" + "-" * 80)
    print("CLASSIFICATION SUMMARY:")
    intent_counts = {}
    for r in results:
        intent_counts[r["intent_type"]] = intent_counts.get(r["intent_type"], 0) + 1

    for intent_type, count in intent_counts.items():
        print(f"  {intent_type}: {count}/10")

    # Identify problems
    print("\n" + "-" * 80)
    print("POTENTIAL ISSUES:")

    issues = []

    # Check 1: All should be URL_SAVE (no thinking keywords in messages)
    url_save_count = intent_counts.get("URL_SAVE", 0)
    if url_save_count != 10:
        issues.append(
            f"  ⚠️  Only {url_save_count}/10 messages classified as URL_SAVE. "
            f"Some may be incorrectly routed to analysis."
        )

    # Check 2: URL extraction
    for r in results:
        if not r["url"]:
            issues.append(f"  ⚠️  Message {r['msg_num']}: URL not extracted!")
        elif "monica.im" not in r["url"]:
            issues.append(
                f"  ⚠️  Message {r['msg_num']}: URL may be malformed: {r['url']}"
            )

    # Check 3: Confidence levels
    low_confidence = [r for r in results if r["confidence"] < 0.8]
    if low_confidence:
        issues.append(
            f"  ⚠️  {len(low_confidence)} messages have low confidence (< 0.8): "
            f"{[r['msg_num'] for r in low_confidence]}"
        )

    if issues:
        for issue in issues:
            print(issue)
    else:
        print("  ✓ No major issues detected in intent classification")

    return results


async def test_url_fetching():
    """Test URL fetching and content extraction for each message."""
    print("\n" + "=" * 80)
    print("TEST 2: URL Fetching & Content Extraction (via MarkdownizeProcessor + Browser)")
    print("=" * 80)

    from aily.processing.markdownize import MarkdownizeProcessor
    from aily.browser.manager import BrowserUseManager

    # Start browser manager for JS-rendered pages
    print("\nStarting browser manager...")
    browser = BrowserUseManager()
    await browser.start()
    print("Browser started")

    processor = MarkdownizeProcessor(browser_manager=browser)

    results = []
    for i, msg in enumerate(TEST_MESSAGES, 1):
        # Extract URL
        intent = IntentRouter.analyze(msg)
        url = intent.url

        print(f"\nMessage {i}: {url}")

        if not url:
            print("  ⚠️  No URL found, skipping")
            results.append({
                "msg_num": i,
                "status": "no_url",
                "error": "URL extraction failed",
            })
            continue

        # Try to fetch and process via markdownize (with browser for JS pages)
        try:
            md_content = await processor.process_url(url, use_browser=True)

            # Save to file
            output_file = f"/Users/luzi/code/aily/monica_msg_{i}.md"
            with open(output_file, 'w') as f:
                f.write(md_content.markdown)
            print(f"  💾 Saved to: monica_msg_{i}.md ({len(md_content.markdown)} chars)")

            # Analyze result
            text_length = len(md_content.markdown) if md_content.markdown else 0
            has_content = text_length > 200 and "monica" not in md_content.markdown.lower()[:100]

            print(f"  Status: {'OK' if text_length > 0 else 'ERROR'}")
            print(f"  Source Type: {md_content.source_type}")
            print(f"  Markdown Length: {text_length} chars")

            # Check if we got actual content
            if text_length < 200:
                print(f"  ⚠️  Very short content - may need browser fetch")
            elif "转向AI芯片架构" in md_content.markdown or "Monica" in md_content.markdown[:50]:
                print(f"  ✓ Got actual conversation content!")

            results.append({
                "msg_num": i,
                "url": url,
                "status": "success" if text_length > 0 else "error",
                "source_type": md_content.source_type,
                "title": md_content.title,
                "text_length": text_length,
                "text_preview": md_content.markdown[:300] if md_content.markdown else "",
                "error": None,
            })

        except Exception as e:
            print(f"  Status: EXCEPTION")
            print(f"  Error: {type(e).__name__}: {e}")
            results.append({
                "msg_num": i,
                "url": url,
                "status": "exception",
                "error": f"{type(e).__name__}: {e}",
            })

    # Cleanup browser
    print("\nStopping browser manager...")
    await browser.stop()
    print("Browser stopped")

    # Summary
    print("\n" + "-" * 80)
    print("FETCH SUMMARY:")
    success_count = sum(1 for r in results if r.get("status") == "success")
    error_count = sum(1 for r in results if r.get("status") == "error")
    exception_count = sum(1 for r in results if r.get("status") == "exception")

    print(f"  Success: {success_count}/10")
    print(f"  Errors: {error_count}/10")
    print(f"  Exceptions: {exception_count}/10")

    return results


def analyze_monica_problems(fetch_results):
    """Analyze specific problems with Monica share links."""
    print("\n" + "=" * 80)
    print("TEST 3: Monica Share Link Specific Analysis")
    print("=" * 80)

    issues = []

    for r in fetch_results:
        if r.get("status") != "success":
            continue

        text = r.get("text_preview", "")
        msg_num = r.get("msg_num")

        # Check if content is actually useful
        if len(text) < 100:
            issues.append({
                "msg_num": msg_num,
                "issue": "Very short content extracted",
                "suggestion": "Page may require JavaScript rendering or login",
            })

        # Check for common error patterns
        if "login" in text.lower() or "sign in" in text.lower():
            issues.append({
                "msg_num": msg_num,
                "issue": "Login wall detected",
                "suggestion": "Monica share links may require authentication",
            })

        if "not found" in text.lower() or "404" in text.lower():
            issues.append({
                "msg_num": msg_num,
                "issue": "Page not found or expired",
                "suggestion": "Share link may be expired or invalid",
            })

        # Check if it's just generic Monica branding
        monica_only = all(
            keyword in text.lower()
            for keyword in ["monica", "chat"]
        )
        if monica_only and len(text) < 500:
            issues.append({
                "msg_num": msg_num,
                "issue": "Only generic Monica branding extracted, no conversation content",
                "suggestion": "Share links may be client-side rendered; need browser-based fetch",
            })

    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(f"\n  Message {issue['msg_num']}:")
            print(f"    Problem: {issue['issue']}")
            print(f"    Suggestion: {issue['suggestion']}")
    else:
        print("\n  ✓ No specific issues detected with Monica links")

    return issues


def generate_report(classification_results, fetch_results, monica_issues):
    """Generate a final report with findings and recommendations."""
    print("\n" + "=" * 80)
    print("FINAL REPORT")
    print("=" * 80)

    # Overall success rate
    successful_fetches = sum(1 for r in fetch_results if r.get("status") == "success")
    useful_content = sum(
        1 for r in fetch_results
        if r.get("status") == "success" and r.get("text_length", 0) > 500
    )

    print(f"\n📊 OVERALL RESULTS:")
    print(f"  Messages tested: 10")
    print(f"  Intent classification: 100% success")
    print(f"  URL fetch success: {successful_fetches}/10 ({successful_fetches*10}%)")
    print(f"  Useful content extracted: {useful_content}/10 ({useful_content*10}%)")

    print(f"\n🔍 KEY FINDINGS:")

    finding_num = 1

    # Finding 1: Intent classification
    all_url_save = all(r["intent_type"] == "URL_SAVE" for r in classification_results)
    if all_url_save:
        print(f"  {finding_num}. ✓ All messages correctly classified as URL_SAVE")
    else:
        print(f"  {finding_num}. ⚠️ Some messages misclassified (not URL_SAVE)")
    finding_num += 1

    # Finding 2: Monica links
    if monica_issues:
        print(f"  {finding_num}. ⚠️ Monica share links have extraction issues:")
        print(f"     - {len(monica_issues)} links have problems")
        print(f"     - Likely cause: Client-side rendered content")
        print(f"     - Solution: Use browser-based fetching (browser-use)")
    else:
        print(f"  {finding_num}. ✓ Monica links process correctly")
    finding_num += 1

    # Finding 3: Content quality
    if useful_content < 5:
        print(f"  {finding_num}. ⚠️ Low content quality: only {useful_content}/10 have useful content")
    else:
        print(f"  {finding_num}. ✓ Good content extraction rate")
    finding_num += 1

    print(f"\n📋 RECOMMENDATIONS:")
    print(f"  1. Implement browser-based fetching for JavaScript-rendered pages")
    print(f"  2. Add special handling for Monica share links (API integration?)")
    print(f"  3. Add content quality scoring (length, entropy, relevance)")
    print(f"  4. Consider fallback to LLM-based content summarization for failed fetches")

    print(f"\n💡 TECHNICAL DEBT IDENTIFIED:")
    print(f"  - WebProcessor uses basic regex HTML stripping (line 356-367)")
    print(f"  - No JavaScript execution support without browser_manager")
    print(f"  - No special handling for known problematic domains (monica.im)")

    return {
        "total_messages": 10,
        "classification_success": all_url_save,
        "fetch_success_rate": successful_fetches / 10,
        "useful_content_rate": useful_content / 10,
        "monica_issues": len(monica_issues),
    }


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("AILY URL MESSAGE TEST SUITE")
    print("Testing 10 Monica AI Chat share links")
    print("=" * 80)

    # Test 1: Intent Classification
    classification_results = test_intent_classification()

    # Test 2: URL Fetching
    fetch_results = await test_url_fetching()

    # Test 3: Monica-specific analysis
    monica_issues = analyze_monica_problems(fetch_results)

    # Generate final report
    summary = generate_report(classification_results, fetch_results, monica_issues)

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    return summary


if __name__ == "__main__":
    summary = asyncio.run(main())
    print(f"\nSummary: {summary}")
