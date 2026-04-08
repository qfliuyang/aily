#!/usr/bin/env python3
"""
Test script for Browser Use commercial API connectivity.

Tests:
1. API key authentication
2. Session creation
3. Basic navigation (example.com)
4. Response format and latency measurement
"""

import asyncio
import time
import json
import os
from datetime import datetime
from typing import Any

# API Configuration
API_KEY = "bu_cr_lbyBviJBUvnw4b1-hNQdLSEi3aALlTIjSYVE1Zso"
BASE_URL = "https://api.browser-use.com/api/v3"

# Test results collector
results = {
    "timestamp": datetime.now().isoformat(),
    "api_key_prefix": API_KEY[:10] + "..." if len(API_KEY) > 10 else "invalid",
    "base_url": BASE_URL,
    "tests": {}
}


async def test_api_connectivity():
    """Test 1: Basic API connectivity and authentication."""
    print("=" * 60)
    print("TEST 1: API Connectivity & Authentication")
    print("=" * 60)

    test_result = {
        "name": "API Connectivity",
        "status": "pending",
        "latency_ms": None,
        "errors": [],
        "details": {}
    }

    try:
        import aiohttp

        start_time = time.time()

        # Try to list sessions (lightweight authenticated request)
        async with aiohttp.ClientSession() as session:
            headers = {
                "X-Browser-Use-API-Key": API_KEY,
                "Content-Type": "application/json"
            }

            async with session.get(
                f"{BASE_URL}/sessions",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                latency_ms = (time.time() - start_time) * 1000
                test_result["latency_ms"] = round(latency_ms, 2)

                status_code = response.status
                test_result["details"]["status_code"] = status_code

                if status_code == 200:
                    data = await response.json()
                    test_result["status"] = "passed"
                    test_result["details"]["response"] = data
                    print(f"✓ API key is valid and authenticated")
                    print(f"  Status: {status_code}")
                    print(f"  Latency: {latency_ms:.2f}ms")
                    print(f"  Response: {json.dumps(data, indent=2)[:200]}...")
                elif status_code == 401:
                    test_result["status"] = "failed"
                    test_result["errors"].append("Authentication failed - invalid API key")
                    print(f"✗ Authentication failed (401)")
                    print(f"  The API key appears to be invalid")
                else:
                    text = await response.text()
                    test_result["status"] = "failed"
                    test_result["errors"].append(f"Unexpected status code: {status_code}")
                    test_result["details"]["response_text"] = text
                    print(f"✗ Unexpected response (status: {status_code})")
                    print(f"  Response: {text[:200]}")

    except ImportError:
        # Fall back to requests
        try:
            import requests

            start_time = time.time()

            headers = {
                "X-Browser-Use-API-Key": API_KEY,
                "Content-Type": "application/json"
            }

            response = requests.get(
                f"{BASE_URL}/sessions",
                headers=headers,
                timeout=30
            )

            latency_ms = (time.time() - start_time) * 1000
            test_result["latency_ms"] = round(latency_ms, 2)
            test_result["details"]["status_code"] = response.status_code

            if response.status_code == 200:
                test_result["status"] = "passed"
                test_result["details"]["response"] = response.json()
                print(f"✓ API key is valid and authenticated")
                print(f"  Status: {response.status_code}")
                print(f"  Latency: {latency_ms:.2f}ms")
            elif response.status_code == 401:
                test_result["status"] = "failed"
                test_result["errors"].append("Authentication failed - invalid API key")
                print(f"✗ Authentication failed (401)")
            else:
                test_result["status"] = "failed"
                test_result["errors"].append(f"Unexpected status code: {response.status_code}")
                test_result["details"]["response_text"] = response.text
                print(f"✗ Unexpected response (status: {response.status_code})")

        except ImportError:
            test_result["status"] = "error"
            test_result["errors"].append("Neither aiohttp nor requests library available")
            print("✗ Neither aiohttp nor requests library is installed")
    except Exception as e:
        test_result["status"] = "error"
        test_result["errors"].append(str(e))
        print(f"✗ Error during connectivity test: {e}")

    results["tests"]["connectivity"] = test_result
    print()
    return test_result["status"] == "passed"


async def test_create_session():
    """Test 2: Create a session/task."""
    print("=" * 60)
    print("TEST 2: Create Session/Task")
    print("=" * 60)

    test_result = {
        "name": "Create Session",
        "status": "pending",
        "latency_ms": None,
        "errors": [],
        "details": {}
    }

    try:
        import aiohttp

        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            headers = {
                "X-Browser-Use-API-Key": API_KEY,
                "Content-Type": "application/json"
            }

            payload = {
                "task": "Navigate to example.com and extract the page title and main heading"
            }

            print(f"Creating session with task: {payload['task']}")

            async with session.post(
                f"{BASE_URL}/sessions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                latency_ms = (time.time() - start_time) * 1000
                test_result["latency_ms"] = round(latency_ms, 2)

                status_code = response.status
                test_result["details"]["status_code"] = status_code

                if status_code in (200, 201):
                    data = await response.json()
                    test_result["status"] = "passed"
                    test_result["details"]["response"] = data

                    session_id = data.get("id") or data.get("session_id")
                    if session_id:
                        test_result["details"]["session_id"] = session_id
                        print(f"✓ Session created successfully")
                        print(f"  Session ID: {session_id}")
                        print(f"  Latency: {latency_ms:.2f}ms")
                        print(f"  Full response: {json.dumps(data, indent=2)}")
                        return session_id
                    else:
                        print(f"✓ Session created but no ID returned")
                        print(f"  Response: {json.dumps(data, indent=2)}")
                        return None
                else:
                    text = await response.text()
                    test_result["status"] = "failed"
                    test_result["errors"].append(f"Failed to create session: {status_code}")
                    test_result["details"]["response_text"] = text
                    print(f"✗ Failed to create session (status: {status_code})")
                    print(f"  Response: {text[:500]}")
                    return None

    except ImportError:
        try:
            import requests

            start_time = time.time()

            headers = {
                "X-Browser-Use-API-Key": API_KEY,
                "Content-Type": "application/json"
            }

            payload = {
                "task": "Navigate to example.com and extract the page title and main heading"
            }

            response = requests.post(
                f"{BASE_URL}/sessions",
                headers=headers,
                json=payload,
                timeout=60
            )

            latency_ms = (time.time() - start_time) * 1000
            test_result["latency_ms"] = round(latency_ms, 2)
            test_result["details"]["status_code"] = response.status_code

            if response.status_code in (200, 201):
                data = response.json()
                test_result["status"] = "passed"
                test_result["details"]["response"] = data

                session_id = data.get("id") or data.get("session_id")
                if session_id:
                    test_result["details"]["session_id"] = session_id
                    print(f"✓ Session created successfully")
                    print(f"  Session ID: {session_id}")
                    print(f"  Latency: {latency_ms:.2f}ms")
                    return session_id
                else:
                    return None
            else:
                test_result["status"] = "failed"
                test_result["errors"].append(f"Failed to create session: {response.status_code}")
                test_result["details"]["response_text"] = response.text
                print(f"✗ Failed to create session (status: {response.status_code})")
                return None

        except ImportError:
            test_result["status"] = "error"
            test_result["errors"].append("Neither aiohttp nor requests library available")
            print("✗ Neither aiohttp nor requests library is installed")
            return None
    except Exception as e:
        test_result["status"] = "error"
        test_result["errors"].append(str(e))
        print(f"✗ Error creating session: {e}")
        return None
    finally:
        results["tests"]["create_session"] = test_result
        print()


async def test_get_session_results(session_id: str):
    """Test 3: Get session results."""
    print("=" * 60)
    print("TEST 3: Get Session Results")
    print("=" * 60)

    test_result = {
        "name": "Get Session Results",
        "status": "pending",
        "latency_ms": None,
        "errors": [],
        "details": {}
    }

    if not session_id:
        test_result["status"] = "skipped"
        test_result["errors"].append("No session ID available")
        results["tests"]["get_results"] = test_result
        print("⚠ Skipped - no session ID from previous test")
        print()
        return

    try:
        import aiohttp

        print(f"Polling for results (session: {session_id})...")
        print("Waiting up to 60 seconds for task completion...")

        async with aiohttp.ClientSession() as session:
            headers = {
                "X-Browser-Use-API-Key": API_KEY,
                "Content-Type": "application/json"
            }

            start_time = time.time()
            poll_count = 0
            max_polls = 12  # 12 * 5 seconds = 60 seconds max

            while poll_count < max_polls:
                poll_start = time.time()

                async with session.get(
                    f"{BASE_URL}/sessions/{session_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        status = data.get("status")

                        print(f"  Poll {poll_count + 1}: status = {status}")

                        if status in ("completed", "success", "done"):
                            total_latency = (time.time() - start_time) * 1000
                            test_result["latency_ms"] = round(total_latency, 2)
                            test_result["status"] = "passed"
                            test_result["details"]["response"] = data
                            test_result["details"]["poll_count"] = poll_count + 1

                            print(f"✓ Task completed!")
                            print(f"  Total time: {total_latency:.2f}ms ({total_latency/1000:.1f}s)")
                            print(f"  Polls: {poll_count + 1}")
                            print(f"  Output: {json.dumps(data, indent=2)[:1000]}...")
                            return
                        elif status in ("failed", "error"):
                            test_result["status"] = "failed"
                            test_result["errors"].append(f"Task failed with status: {status}")
                            test_result["details"]["response"] = data
                            print(f"✗ Task failed with status: {status}")
                            return
                        # Still running, wait and poll again

                    elif response.status == 404:
                        test_result["status"] = "failed"
                        test_result["errors"].append("Session not found")
                        print(f"✗ Session not found (404)")
                        return
                    else:
                        text = await response.text()
                        test_result["status"] = "error"
                        test_result["errors"].append(f"Unexpected status: {response.status}")
                        print(f"✗ Unexpected status: {response.status}")
                        return

                poll_count += 1
                await asyncio.sleep(5)  # Wait 5 seconds between polls

            # Timeout
            test_result["status"] = "timeout"
            test_result["errors"].append("Timeout waiting for task completion")
            print("⚠ Timeout - task did not complete within 60 seconds")

    except ImportError:
        try:
            import requests

            print(f"Polling for results (session: {session_id})...")
            print("Waiting up to 60 seconds for task completion...")

            headers = {
                "X-Browser-Use-API-Key": API_KEY,
                "Content-Type": "application/json"
            }

            start_time = time.time()
            poll_count = 0
            max_polls = 12

            while poll_count < max_polls:
                response = requests.get(
                    f"{BASE_URL}/sessions/{session_id}",
                    headers=headers,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")

                    print(f"  Poll {poll_count + 1}: status = {status}")

                    if status in ("completed", "success", "done"):
                        total_latency = (time.time() - start_time) * 1000
                        test_result["latency_ms"] = round(total_latency, 2)
                        test_result["status"] = "passed"
                        test_result["details"]["response"] = data
                        test_result["details"]["poll_count"] = poll_count + 1

                        print(f"✓ Task completed!")
                        print(f"  Total time: {total_latency:.2f}ms ({total_latency/1000:.1f}s)")
                        return
                    elif status in ("failed", "error"):
                        test_result["status"] = "failed"
                        test_result["errors"].append(f"Task failed with status: {status}")
                        print(f"✗ Task failed with status: {status}")
                        return

                poll_count += 1
                time.sleep(5)

            test_result["status"] = "timeout"
            test_result["errors"].append("Timeout waiting for task completion")
            print("⚠ Timeout - task did not complete within 60 seconds")

        except ImportError:
            test_result["status"] = "error"
            test_result["errors"].append("Neither aiohttp nor requests library available")
            print("✗ Neither aiohttp nor requests library is installed")
    except Exception as e:
        test_result["status"] = "error"
        test_result["errors"].append(str(e))
        print(f"✗ Error getting results: {e}")
    finally:
        results["tests"]["get_results"] = test_result
        print()


async def test_sdk_availability():
    """Test 4: Check if browser-use-sdk is available."""
    print("=" * 60)
    print("TEST 4: SDK Availability")
    print("=" * 60)

    test_result = {
        "name": "SDK Availability",
        "status": "pending",
        "errors": [],
        "details": {}
    }

    try:
        from browser_use_sdk import AsyncBrowserUse
        test_result["status"] = "passed"
        test_result["details"]["sdk_available"] = True
        test_result["details"]["sdk_version"] = "installed"
        print("✓ browser-use-sdk is installed")
        print("  Can use: from browser_use_sdk import AsyncBrowserUse")
    except ImportError:
        test_result["status"] = "info"
        test_result["details"]["sdk_available"] = False
        test_result["errors"].append("browser-use-sdk not installed")
        print("⚠ browser-use-sdk is NOT installed")
        print("  Install with: pip install browser-use-sdk")
        print("  Falling back to direct HTTP API calls")

    results["tests"]["sdk_availability"] = test_result
    print()


def print_summary():
    """Print test summary."""
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = 0
    failed = 0
    errors = 0
    skipped = 0

    for test_name, test_data in results["tests"].items():
        status = test_data.get("status", "unknown")
        latency = test_data.get("latency_ms")
        latency_str = f" ({latency}ms)" if latency else ""

        if status == "passed":
            print(f"✓ {test_name}: PASSED{latency_str}")
            passed += 1
        elif status == "failed":
            print(f"✗ {test_name}: FAILED{latency_str}")
            failed += 1
        elif status in ("error", "timeout"):
            print(f"✗ {test_name}: ERROR{latency_str}")
            errors += 1
        elif status == "skipped":
            print(f"⚠ {test_name}: SKIPPED")
            skipped += 1
        else:
            print(f"? {test_name}: {status.upper()}{latency_str}")

    print()
    print(f"Total: {passed} passed, {failed} failed, {errors} errors, {skipped} skipped")
    print("=" * 60)


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Browser Use Commercial API Connectivity Test")
    print("=" * 60)
    print(f"Timestamp: {results['timestamp']}")
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {results['api_key_prefix']}")
    print()

    # Test SDK availability first
    await test_sdk_availability()

    # Test 1: Connectivity
    connected = await test_api_connectivity()

    if not connected:
        print("⚠ API connectivity failed - skipping remaining tests")
        results["tests"]["create_session"] = {
            "name": "Create Session",
            "status": "skipped",
            "errors": ["API connectivity failed"]
        }
        results["tests"]["get_results"] = {
            "name": "Get Session Results",
            "status": "skipped",
            "errors": ["API connectivity failed"]
        }
        print_summary()
        return

    # Test 2: Create Session
    session_id = await test_create_session()

    # Test 3: Get Results
    await test_get_session_results(session_id)

    # Print summary
    print_summary()

    # Save results to file
    output_file = "tests/browser_use_api_connectivity.json"
    os.makedirs("tests", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
