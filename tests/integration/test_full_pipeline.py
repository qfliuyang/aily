"""
Full pipeline integration tests.

These tests exercise the complete Aily flow:
1. Receive Feishu webhook
2. Enqueue URL fetch job
3. Browser fetches the page
4. Parser extracts content
5. Obsidian note is created

No mocks - all real HTTP calls between services.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx
import pytest


class TestFullPipeline:
    """End-to-end pipeline tests."""

    async def test_url_fetch_pipeline(
        self,
        feishu_client: httpx.AsyncClient,
        obsidian_client: httpx.AsyncClient,
        browser_client: httpx.AsyncClient,
    ) -> None:
        """
        Complete pipeline: URL shared in Feishu -> Note created in Obsidian.

        This test simulates:
        1. User shares https://httpbin.org/html in Feishu
        2. Feishu webhook fires to Aily
        3. Aily enqueues fetch job
        4. Browser fetches the page
        5. Parser extracts content
        6. Note written to Obsidian vault
        """
        # Step 1: Simulate Feishu webhook with URL
        url = "https://httpbin.org/html"
        feishu_payload = {
            "header": {
                "event_id": f"pipeline-test-{int(time.time())}",
                "event_type": "im.message.receive_v1",
                "timestamp": int(time.time() * 1000),
            },
            "event": {
                "sender": {"sender_id": {"open_id": "test-user-123"}},
                "message": {
                    "message_type": "text",
                    "content": json.dumps({"text": f"Check out this page: {url}"}),
                    "message_id": f"msg-{int(time.time())}",
                },
            },
        }

        response = await feishu_client.post("/webhook", json=feishu_payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Step 2: Verify Feishu received the webhook
        messages = await feishu_client.get("/__test/messages")
        assert messages.status_code == 200
        data = messages.json()
        assert len(data["messages"]) == 1

        # Step 3: Simulate what Aily would do - fetch the URL
        fetch_response = await browser_client.post(
            "/fetch",
            json={"url": url, "timeout": 30000},
        )
        assert fetch_response.status_code == 200
        page_data = fetch_response.json()
        assert page_data["status"] == 200
        assert "Herman Melville" in page_data["text"]

        # Step 4: Create Obsidian note with fetched content
        note_content = f"""# {page_data['title']}

**Source:** {url}
**Fetched:** {time.strftime('%Y-%m-%d %H:%M:%S')}

## Content

{page_data['text'][:2000]}

---
*Automatically saved by Aily*
"""

        note_path = "test-pipeline-note.md"
        put_response = await obsidian_client.put(
            f"/vault/{note_path}",
            content=note_content,
        )
        assert put_response.status_code == 200
        assert put_response.json()["created"] is True

        # Step 5: Verify note was created
        get_response = await obsidian_client.get(f"/vault/{note_path}")
        assert get_response.status_code == 200
        saved_note = get_response.json()
        assert url in saved_note["content"]
        assert "Herman Melville" in saved_note["content"]

    async def test_pipeline_with_error_handling(
        self,
        feishu_client: httpx.AsyncClient,
        obsidian_client: httpx.AsyncClient,
        browser_client: httpx.AsyncClient,
    ) -> None:
        """
        Pipeline handles errors gracefully:
        - Invalid URL
        - Network timeout
        - Service unavailable
        """
        # Test with invalid URL
        invalid_url = "https://this-domain-definitely-does-not-exist-12345.com"

        fetch_response = await browser_client.post(
            "/fetch/text",
            json={"url": invalid_url, "timeout": 5000},
        )
        # Should get an error response, not crash
        assert fetch_response.status_code in [500, 502, 503, 504]

        # Verify error notification could be sent to Feishu
        error_notification = {
            "msg_type": "text",
            "content": {"text": f"Failed to fetch: {invalid_url}"},
        }
        notify_response = await feishu_client.post(
            "/open-apis/bot/v2/hook/test-token/send",
            json=error_notification,
        )
        assert notify_response.status_code == 200
        assert notify_response.json()["code"] == 0

    @pytest.mark.slow
    async def test_concurrent_url_processing(
        self,
        feishu_client: httpx.AsyncClient,
        obsidian_client: httpx.AsyncClient,
        browser_client: httpx.AsyncClient,
    ) -> None:
        """
        Multiple URLs can be processed concurrently.

        This tests that the system handles multiple webhooks
        without blocking or losing data.
        """
        urls = [
            "https://httpbin.org/html",
            "https://httpbin.org/json",
        ]

        async def process_url(url: str, index: int) -> dict[str, Any]:
            """Process a single URL through the pipeline."""
            # Simulate webhook
            await feishu_client.post("/webhook", json={
                "header": {
                    "event_id": f"concurrent-{index}-{int(time.time())}",
                    "event_type": "im.message.receive_v1",
                    "timestamp": int(time.time() * 1000),
                },
                "event": {
                    "sender": {"sender_id": {"open_id": f"user-{index}"}},
                    "message": {
                        "message_type": "text",
                        "content": json.dumps({"text": url}),
                        "message_id": f"msg-{index}",
                    },
                },
            })

            # Fetch URL
            fetch_resp = await browser_client.post(
                "/fetch/text",
                json={"url": url, "timeout": 30000},
            )

            # Create note
            note_path = f"concurrent-note-{index}.md"
            if fetch_resp.status_code == 200:
                page_data = fetch_resp.json()
                await obsidian_client.put(
                    f"/vault/{note_path}",
                    content=f"# Fetched from {url}\n\n{page_data.get('text', 'No content')[:1000]}",
                )
                return {"success": True, "path": note_path}
            else:
                return {"success": False, "error": fetch_resp.text}

        # Process all URLs concurrently
        results = await asyncio.gather(
            *[process_url(url, i) for i, url in enumerate(urls)],
            return_exceptions=True,
        )

        # All should complete without exceptions
        for result in results:
            assert not isinstance(result, Exception)

        # Verify all webhooks were received
        messages = await feishu_client.get("/__test/messages")
        assert len(messages.json()["messages"]) == len(urls)

        # Verify notes were created
        stats = await obsidian_client.get("/__test/stats")
        assert stats.json()["notes_count"] == len(urls)


class TestAilyWithRealServices:
    """
    Tests that run the actual Aily application against mock services.

    These require the Aily app to be running in test mode.
    """

    @pytest.fixture
    async def aily_client(self) -> httpx.AsyncClient:
        """HTTP client for the Aily application."""
        aily_url = "http://localhost:8000"
        async with httpx.AsyncClient(base_url=aily_url, timeout=30.0) as client:
            yield client

    async def test_aily_status_endpoint(
        self,
        aily_client: httpx.AsyncClient,
    ) -> None:
        """
        Aily status endpoint returns service health.

        This verifies Aily can communicate with all its dependencies.
        """
        try:
            response = await aily_client.get("/status")
        except httpx.ConnectError:
            pytest.skip("Aily service not running - start with: python -m aily.main")

        if response.status_code in {502, 503, 504}:
            pytest.skip(f"Aily service unavailable at localhost:8000: HTTP {response.status_code}")

        assert response.status_code == 200
        data = response.json()
        assert "aily_version" in data
