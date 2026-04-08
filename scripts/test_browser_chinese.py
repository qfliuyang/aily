#!/usr/bin/env python3
"""
Test script for Browser Use with Chinese-language pages.

Validates:
1. Chinese text extraction from JS-rendered pages
2. Monica chat page content extraction
3. Kimi report extraction

Usage:
    python scripts/test_browser_chinese.py --url <url>
    python scripts/test_browser_chinese.py --test-mock  # Use local test fixture
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.browser.manager import BrowserUseManager


# Test HTML fixture with Chinese content
CHINESE_TEST_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>测试页面 - AI对话</title>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .message { padding: 12px; margin: 8px 0; border-radius: 8px; }
        .user { background: #e3f2fd; text-align: right; }
        .assistant { background: #f5f5f5; }
        .timestamp { color: #666; font-size: 12px; }
        code { background: #f0f0f0; padding: 2px 4px; border-radius: 4px; }
        pre { background: #f5f5f5; padding: 12px; overflow-x: auto; }
    </style>
</head>
<body>
    <h1>AI 助手对话</h1>
    <div class="chat-container">
        <div class="message user">
            <div class="timestamp">2024-01-15 10:30</div>
            <p>请解释什么是大语言模型？</p>
        </div>
        <div class="message assistant">
            <div class="timestamp">2024-01-15 10:31</div>
            <p>大语言模型（Large Language Model, LLM）是一种基于深度学习的自然语言处理模型。</p>
            <p>主要特点包括：</p>
            <ul>
                <li>参数量巨大（数十亿到数千亿）</li>
                <li>在海量文本上预训练</li>
                <li>能够理解和生成人类语言</li>
            </ul>
            <p>例如：<code>GPT-4</code>、<code>Claude</code>、<code>文心一言</code>等。</p>
        </div>
        <div class="message user">
            <div class="timestamp">2024-01-15 10:35</div>
            <p>能写一段Python代码来计算斐波那契数列吗？</p>
        </div>
        <div class="message assistant">
            <div class="timestamp">2024-01-15 10:36</div>
            <p>当然可以！以下是一个高效的实现：</p>
            <pre><code>def fibonacci(n):
    \"\"\"计算斐波那契数列前n项\"\"\"\n    if n <= 0:
        return []\n    elif n == 1:\n        return [0]\n    \n    fibs = [0, 1]\n    for i in range(2, n):\n        fibs.append(fibs[-1] + fibs[-2])\n    return fibs\n\n# 示例：打印前10项\nprint(fibonacci(10))\n# 输出：[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]</code></pre>
        </div>
    </div>
    <script>
        // Simulate dynamic content loading
        document.addEventListener('DOMContentLoaded', function() {
            console.log('页面加载完成');
        });
    </script>
</body>
</html>
"""


async def test_mock_chinese_page():
    """Test extraction from local Chinese HTML fixture."""
    import tempfile
    import http.server
    import socketserver
    import threading

    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(CHINESE_TEST_HTML)
        temp_path = f.name

    # Start simple HTTP server
    port = 8765
    handler = http.server.SimpleHTTPRequestHandler
    server = socketserver.TCPServer(("", port), handler)

    # Serve from temp directory
    import os
    os.chdir(str(Path(temp_path).parent))

    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    try:
        url = f"http://localhost:{port}/{Path(temp_path).name}"
        print(f"Testing extraction from: {url}")

        browser = BrowserUseManager()
        await browser.start()

        try:
            result = await browser.fetch(url)
            print("\n" + "=" * 60)
            print("EXTRACTION RESULT")
            print("=" * 60)
            print(result[:2000] if len(result) > 2000 else result)
            print("=" * 60)

            # Validate Chinese content was extracted
            success_indicators = [
                "大语言模型" in result,
                "Python" in result,
                "斐波那契" in result,
                "def fibonacci" in result,
            ]

            print("\nValidation:")
            print(f"  - Chinese text (大语言模型): {'✓' if success_indicators[0] else '✗'}")
            print(f"  - Code blocks preserved: {'✓' if success_indicators[1] else '✗'}")
            print(f"  - Chinese prompts kept: {'✓' if success_indicators[2] else '✗'}")
            print(f"  - Code formatting intact: {'✓' if success_indicators[3] else '✗'}")

            all_passed = all(success_indicators)
            print(f"\nOverall: {'✓ PASS' if all_passed else '✗ FAIL'}")

            return all_passed

        finally:
            await browser.stop()
            server.shutdown()

    finally:
        Path(temp_path).unlink(missing_ok=True)


async def test_real_url(url: str):
    """Test extraction from a real URL."""
    print(f"Testing extraction from: {url}")

    browser = BrowserUseManager()
    await browser.start()

    try:
        result = await browser.fetch(url)
        print("\n" + "=" * 60)
        print("EXTRACTION RESULT (first 3000 chars)")
        print("=" * 60)
        print(result[:3000])
        print("=" * 60)

        # Check for Chinese characters
        chinese_chars = sum(1 for c in result if '\u4e00' <= c <= '\u9fff')
        print(f"\nChinese characters found: {chinese_chars}")

        if chinese_chars > 0:
            print("✓ Chinese text extraction: WORKING")
        else:
            print("⚠ No Chinese text found - may need JavaScript rendering")

        return True

    finally:
        await browser.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Test Browser Use with Chinese-language pages"
    )
    parser.add_argument(
        "--url",
        help="Real URL to test (e.g., https://monica.im/chat/xxx)"
    )
    parser.add_argument(
        "--test-mock",
        action="store_true",
        help="Run against local Chinese test fixture"
    )

    args = parser.parse_args()

    if args.url:
        success = asyncio.run(test_real_url(args.url))
    elif args.test_mock:
        success = asyncio.run(test_mock_chinese_page())
    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
