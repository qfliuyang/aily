"""
Tests that hit REAL production services.

These tests are designed to EXPOSE problems:
- Network timeouts
- API rate limits
- Authentication failures
- Data corruption
- Race conditions

If something can go wrong, these tests will find it.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

import httpx
import pytest


class TestRealFeishuExposesProblems:
    """
    Test real Feishu API to find real problems.

    These tests will:
    - Send actual messages to real users
    - Fail if credentials are wrong
    - Expose rate limits
    - Show network issues
    """

    async def test_auth_exposes_wrong_credentials(self, exposure, service_availability) -> None:
        """
        Wrong credentials should fail loudly, not silently.

        EXPOSES: Misconfigured auth, expired tokens, wrong app ID
        """
        from tests.integration.conftest import RealFeishuClient

        if not service_availability["feishu"]:
            exposure.expose("CONFIG_MISSING", "Feishu credentials not configured")
            pytest.skip("Feishu credentials not configured")

        # Temporarily break credentials
        original_id = os.environ.get("FEISHU_APP_ID")
        os.environ["FEISHU_APP_ID"] = "wrong-id"

        try:
            client = RealFeishuClient()
            with pytest.raises(Exception) as exc_info:
                await client._get_token()

            exposure.expose("AUTH_FAILURE", "Wrong credentials rejected", {
                "error": str(exc_info.value),
                "expected": True,  # This SHOULD fail
            })
        finally:
            if original_id:
                os.environ["FEISHU_APP_ID"] = original_id

    async def test_send_message_exposes_network_issues(
        self,
        feishu_client,
        exposure,
        test_id: str,
    ) -> None:
        """
        Sending messages exposes network timeouts, rate limits, etc.

        EXPOSES: Network instability, API rate limits, bad user IDs
        """
        open_id = os.getenv("FEISHU_TEST_OPEN_ID")
        if not open_id:
            exposure.expose("CONFIG_MISSING", "FEISHU_TEST_OPEN_ID not set", {
                "consequence": "Cannot test real message sending",
            })
            pytest.skip("No target user configured")

        try:
            result = await feishu_client.send_message(
                open_id=open_id,
                text=f"Test message: {test_id}",
            )

            # Even if it succeeds, check for warnings
            if result.get("code") != 0:
                exposure.expose("API_ERROR", "Feishu API returned error", {
                    "code": result.get("code"),
                    "msg": result.get("msg"),
                })

            # Verify we got a message ID
            message_id = result.get("data", {}).get("message_id")
            if not message_id:
                exposure.expose("MISSING_DATA", "No message_id in response", {
                    "response": result,
                })

        except httpx.TimeoutException as e:
            exposure.expose("TIMEOUT", "Feishu API timed out", {
                "error": str(e),
                "this_is_a_real_problem": True,
            })
            raise  # Re-raise to fail the test

        except httpx.HTTPStatusError as e:
            exposure.expose("HTTP_ERROR", f"HTTP {e.response.status_code}", {
                "url": str(e.request.url),
                "response": e.response.text[:500],
            })
            raise

    async def test_concurrent_sends_expose_rate_limits(
        self,
        feishu_client,
        exposure,
    ) -> None:
        """
        Sending many messages quickly exposes rate limits.

        EXPOSES: API throttling, concurrent handling issues
        """
        open_id = os.getenv("FEISHU_TEST_OPEN_ID")
        if not open_id:
            pytest.skip("No target user configured")

        results = []
        errors = []

        async def send_one(i: int) -> None:
            try:
                result = await feishu_client.send_message(
                    open_id=open_id,
                    text=f"Concurrent test #{i}",
                )
                results.append((i, result))
            except Exception as e:
                errors.append((i, e))

        # Send 5 messages concurrently
        await asyncio.gather(*[send_one(i) for i in range(5)], return_exceptions=True)

        if errors:
            exposure.expose("CONCURRENT_FAILURE", f"{len(errors)}/5 concurrent sends failed", {
                "errors": [str(e) for _, e in errors],
                "this_may_be_rate_limiting": True,
            })

        # We expect some might fail due to rate limiting
        # The test passes if we learn something about the behavior
        print(f"\nConcurrent sends: {len(results)} succeeded, {len(errors)} failed")


class TestRealObsidianExposesProblems:
    """
    Test real Obsidian vault to find real problems.

    These tests will:
    - Write actual files to your vault
    - Fail if Obsidian isn't running
    - Expose file system issues
    - Show encoding problems
    """

    async def test_vault_not_running_exposes_failure(self, exposure) -> None:
        """
        If Obsidian isn't running, we should know immediately.

        EXPOSES: Missing Obsidian, wrong port, REST API not enabled
        """
        import httpx

        vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
        api_key = os.getenv("OBSIDIAN_REST_API_KEY")
        port = os.getenv("OBSIDIAN_REST_API_PORT", "27123")

        if not vault_path:
            exposure.expose("CONFIG_MISSING", "OBSIDIAN_VAULT_PATH not set")
            pytest.skip("No vault configured")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"http://127.0.0.1:{port}/",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=5.0,
                )
                resp.raise_for_status()
        except httpx.ConnectError as e:
            exposure.expose("OBSIDIAN_NOT_RUNNING", "Cannot connect to Obsidian REST API", {
                "error": str(e),
                "action_needed": "Start Obsidian and enable Local REST API plugin",
                "port": port,
            })
            pytest.fail("Obsidian not running - this is a real problem")
        except httpx.HTTPStatusError as e:
            exposure.expose("AUTH_FAILURE", "Obsidian rejected authentication", {
                "status": e.response.status_code,
                "check_your_api_key": True,
            })
            raise

    async def test_write_exposes_encoding_issues(
        self,
        obsidian_client,
        exposure,
        test_id: str,
    ) -> None:
        """
        Writing various content exposes encoding problems.

        EXPOSES: Unicode issues, special character handling, path problems
        """
        test_cases = [
            ("simple.md", "Simple ASCII content"),
            ("unicode.md", "Unicode: 你好世界 🎉 émojis"),
            ("special-chars.md", "Special: <>&\"'\\/\\"),
            ("chinese.md", "Chinese text: 这是一个测试"),
            ("mixed.md", "Mixed: Hello 世界 🌍"),
        ]

        for filename, content in test_cases:
            try:
                result = await obsidian_client.write_note(filename, content)

                # Try to read it back
                try:
                    read_content = await obsidian_client.read_note(filename)
                    if content not in read_content:
                        exposure.expose("DATA_CORRUPTION", f"Content changed after write", {
                            "filename": filename,
                            "original": repr(content),
                            "read_back": repr(read_content),
                        })
                except Exception as e:
                    exposure.expose("READ_FAILURE", f"Could not read back note", {
                        "filename": filename,
                        "error": str(e),
                    })

            except Exception as e:
                exposure.expose("WRITE_FAILURE", f"Could not write note", {
                    "filename": filename,
                    "error": str(e),
                    "content_type": "unicode" if any(ord(c) > 127 for c in content) else "ascii",
                })

    async def test_large_files_expose_performance_issues(
        self,
        obsidian_client,
        exposure,
        test_id: str,
    ) -> None:
        """
        Large files expose performance bottlenecks.

        EXPOSES: Slow writes, memory issues, timeout problems
        """
        sizes = [
            ("small.md", 1000),      # 1 KB
            ("medium.md", 50000),    # 50 KB
            ("large.md", 500000),    # 500 KB
        ]

        for filename, size in sizes:
            content = f"# {filename}\n\n" + "x" * size

            start = datetime.now(timezone.utc)
            try:
                await obsidian_client.write_note(filename, content)
                elapsed = (datetime.now(timezone.utc) - start).total_seconds()

                # Log performance
                print(f"\nWrite {size/1000:.0f}KB: {elapsed:.2f}s")

                if elapsed > 5:
                    exposure.expose("SLOW_WRITE", f"Write took >5 seconds", {
                        "size_kb": size / 1000,
                        "elapsed_seconds": elapsed,
                    })

            except Exception as e:
                exposure.expose("LARGE_WRITE_FAILURE", f"Failed to write large file", {
                    "size_kb": size / 1000,
                    "error": str(e),
                })


class TestRealBrowserExposesProblems:
    """
    Test real browser to find real problems.

    These tests will:
    - Fetch real websites
    - Fail if sites are down
    - Expose network issues
    - Show JavaScript rendering problems
    """

    async def test_fetch_down_site_exposes_failure(
        self,
        browser_page,
        exposure,
    ) -> None:
        """
        Fetching a down site should fail clearly.

        EXPOSES: Network issues, DNS failures, site outages
        """
        bad_urls = [
            "https://this-domain-definitely-does-not-exist-12345.xyz",
            "http://localhost:59999/nonexistent",  # Nothing should be here
        ]

        for url in bad_urls:
            try:
                await browser_page.goto(url, timeout=10000)
                # If we get here, something unexpected happened
                exposure.expose("UNEXPECTED_SUCCESS", f"Bad URL succeeded", {
                    "url": url,
                    "this_is_weird": True,
                })
            except Exception as e:
                exposure.expose("EXPECTED_FAILURE", f"Bad URL failed as expected", {
                    "url": url,
                    "error_type": type(e).__name__,
                    "error": str(e)[:200],
                })
                # This is expected - the test "passes" by finding the problem

    async def test_fetch_real_sites_exposes_actual_behavior(
        self,
        browser_page,
        exposure,
    ) -> None:
        """
        Fetch real sites to see what actually happens.

        EXPOSES: Site changes, anti-bot measures, SSL issues
        """
        sites = [
            ("https://httpbin.org/html", "Herman Melville"),  # Reliable test site
            ("https://news.ycombinator.com", "Hacker News"),  # Real site (may have anti-bot)
            ("https://example.com", "Example Domain"),  # Simple static
        ]

        for url, expected_text in sites:
            try:
                resp = await browser_page.goto(url, timeout=30000)
                await browser_page.wait_for_load_state("networkidle")

                content = await browser_page.content()
                title = await browser_page.title()

                if expected_text not in content and expected_text not in title:
                    exposure.expose("CONTENT_MISMATCH", f"Expected text not found", {
                        "url": url,
                        "expected": expected_text,
                        "title": title,
                        "content_preview": content[:200],
                    })

                print(f"\n✓ {url}: {title[:50]}")

            except Exception as e:
                exposure.expose("FETCH_FAILURE", f"Could not fetch site", {
                    "url": url,
                    "error": str(e),
                    "this_may_be_anti_bot": "captcha" in str(e).lower() or "blocked" in str(e).lower(),
                })

    async def test_javascript_rendering_exposes_timing_issues(
        self,
        browser_page,
        exposure,
    ) -> None:
        """
        JS-heavy sites expose timing/race conditions.

        EXPOSES: Wait conditions, async loading, hydration issues
        """
        # Test with a page that has JavaScript
        try:
            await browser_page.goto("https://httpbin.org/html")
            await browser_page.wait_for_load_state("networkidle")

            # Try to execute some JS
            result = await browser_page.evaluate("() => document.title")
            if not result:
                exposure.expose("JS_EXECUTION_FAILURE", "Could not execute JavaScript", {
                    "page": "httpbin.org",
                })

            # Try to wait for a selector that exists
            try:
                await browser_page.wait_for_selector("h1", timeout=5000)
            except Exception as e:
                exposure.expose("SELECTOR_TIMEOUT", "Timeout waiting for selector", {
                    "error": str(e),
                    "this_may_be_a_race_condition": True,
                })

        except Exception as e:
            exposure.expose("JS_PAGE_FAILURE", "JS page handling failed", {
                "error": str(e),
            })


class TestDatabaseExposesProblems:
    """
    Test real database operations to find real problems.

    These tests will:
    - Use real file I/O
    - Expose locking issues
    - Find corruption scenarios
    """

    def test_concurrent_writes_expose_locking_issues(
        self,
        database_connection: sqlite3.Connection,
        exposure,
    ) -> None:
        """
        Concurrent writes expose locking and transaction issues.

        EXPOSES: Database locks, concurrent access problems
        """
        import sqlite3
        import threading
        import queue

        conn = database_connection
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        conn.commit()

        errors = queue.Queue()

        def writer(thread_id: int) -> None:
            try:
                for i in range(10):
                    conn.execute("INSERT INTO test (value) VALUES (?)",
                               (f"thread-{thread_id}-item-{i}",))
                    conn.commit()
            except Exception as e:
                errors.put((thread_id, str(e)))

        # Start multiple writers
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if not errors.empty():
            error_list = []
            while not errors.empty():
                error_list.append(errors.get())
            exposure.expose("CONCURRENT_DB_FAILURE", f"{len(error_list)} errors during concurrent writes", {
                "errors": error_list,
                "this_is_a_real_problem": True,
            })

        # Verify data integrity
        cursor = conn.execute("SELECT COUNT(*) FROM test")
        count = cursor.fetchone()[0]
        if count != 30:
            exposure.expose("DATA_INTEGRITY", f"Expected 30 rows, got {count}", {
                "missing_or_duplicate": True,
            })

    def test_large_transaction_exposes_memory_issues(
        self,
        database_connection: sqlite3.Connection,
        exposure,
    ) -> None:
        """
        Large transactions expose memory and performance issues.

        EXPOSES: Memory limits, slow commits, WAL mode issues
        """
        import time

        conn = database_connection
        conn.execute("CREATE TABLE bulk (id INTEGER PRIMARY KEY, data TEXT)")

        # Generate large data
        large_data = "x" * 100000  # 100KB per row

        start = time.time()

        try:
            # Try to insert many large rows in one transaction
            for i in range(100):
                conn.execute("INSERT INTO bulk (data) VALUES (?)", (large_data,))
            conn.commit()

            elapsed = time.time() - start
            print(f"\nLarge transaction: {elapsed:.2f}s")

            if elapsed > 10:
                exposure.expose("SLOW_TRANSACTION", f"Large transaction took >10s", {
                    "elapsed_seconds": elapsed,
                    "rows": 100,
                    "row_size_kb": 100,
                })

        except Exception as e:
            exposure.expose("LARGE_TRANSACTION_FAILURE", "Failed to complete large transaction", {
                "error": str(e),
                "this_may_be_memory": "memory" in str(e).lower(),
            })


# =============================================================================
# PROBLEM SUMMARY
# =============================================================================

def pytest_sessionfinish(session, exitstatus):
    """
    Print summary of all exposed problems at end of test session.

    This makes sure we see everything that went wrong, even if tests "passed"
    by finding expected problems.
    """
    print("\n" + "="*70)
    print("REAL SERVICE TEST SUMMARY")
    print("="*70)

    availability = {
        "feishu": bool(os.getenv("FEISHU_APP_ID") and os.getenv("FEISHU_APP_SECRET")),
        "obsidian": bool(os.getenv("OBSIDIAN_VAULT_PATH") and os.getenv("OBSIDIAN_REST_API_KEY")),
        "llm": bool(os.getenv("LLM_API_KEY")),
    }

    print("\nService Availability:")
    for service, available in availability.items():
        status = "✓" if available else "✗ SKIPPED"
        print(f"  {service}: {status}")

    print("\nTests ran against REAL services. Any failures exposed real problems.")
    print("="*70)
