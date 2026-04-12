"""
Integration tests for individual mock services.

These verify each service works independently before testing the full pipeline.
"""
from __future__ import annotations

import httpx
import pytest


class TestFeishuMock:
    """Tests for the Feishu mock service."""

    async def test_health_check(self, feishu_client: httpx.AsyncClient) -> None:
        """Feishu mock responds to health checks."""
        response = await feishu_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "feishu-mock"

    async def test_challenge_verification(self, feishu_client: httpx.AsyncClient) -> None:
        """Feishu mock responds to challenge requests."""
        challenge = "test-challenge-123"
        response = await feishu_client.post(
            "/webhook",
            json={"challenge": challenge},
        )
        assert response.status_code == 200
        assert response.json()["challenge"] == challenge

    async def test_message_webhook(self, feishu_client: httpx.AsyncClient) -> None:
        """Feishu mock receives and stores webhook messages."""
        payload = {
            "header": {
                "event_id": "test-event-001",
                "event_type": "im.message.receive_v1",
                "timestamp": 1234567890000,
            },
            "event": {
                "sender": {"sender_id": {"open_id": "user-123"}},
                "message": {
                    "message_type": "text",
                    "content": '{"text": "Hello from test"}',
                    "message_id": "msg-001",
                },
            },
        }

        response = await feishu_client.post("/webhook", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify message was stored
        messages = await feishu_client.get("/__test/messages")
        assert messages.status_code == 200
        data = messages.json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["data"]["header"]["event_id"] == "test-event-001"

    async def test_bot_send_message(self, feishu_client: httpx.AsyncClient) -> None:
        """Feishu mock accepts bot messages."""
        response = await feishu_client.post(
            "/open-apis/bot/v2/hook/test-token/send",
            json={
                "msg_type": "text",
                "content": {"text": "Test response"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "message_id" in data["data"]

        # Verify response was stored
        responses = await feishu_client.get("/__test/responses")
        assert responses.status_code == 200
        assert len(responses.json()["responses"]) == 1


class TestObsidianMock:
    """Tests for the Obsidian mock service."""

    async def test_health_check(self, obsidian_client: httpx.AsyncClient) -> None:
        """Obsidian mock responds to health checks."""
        response = await obsidian_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "obsidian-mock"

    async def test_create_note(self, obsidian_client: httpx.AsyncClient) -> None:
        """Obsidian mock accepts note creation."""
        response = await obsidian_client.put(
            "/vault/test-note.md",
            content="# Test Note\n\nThis is test content.",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "test-note.md"
        assert data["created"] is True

    async def test_get_note(self, obsidian_client: httpx.AsyncClient) -> None:
        """Obsidian mock returns stored notes."""
        # Create note
        await obsidian_client.put(
            "/vault/retrieve-me.md",
            content="# Retrieve Me\n\nContent here.",
        )

        # Retrieve note
        response = await obsidian_client.get("/vault/retrieve-me.md")
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "retrieve-me.md"
        assert "Content here" in data["content"]

    async def test_list_files(self, obsidian_client: httpx.AsyncClient) -> None:
        """Obsidian mock lists all files."""
        await obsidian_client.put("/vault/file1.md", content="File 1")
        await obsidian_client.put("/vault/file2.md", content="File 2")

        response = await obsidian_client.get("/vault/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 2

    async def test_search_notes(self, obsidian_client: httpx.AsyncClient) -> None:
        """Obsidian mock supports content search."""
        await obsidian_client.put("/vault/searchable.md", content="Unique keyword XYZ123")

        response = await obsidian_client.get("/__test/notes/search?q=XYZ123")
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert "XYZ123" in data["results"][0]["content"]


class TestBrowserService:
    """Tests for the real browser service."""

    async def test_health_check(self, browser_client: httpx.AsyncClient) -> None:
        """Browser service responds to health checks."""
        response = await browser_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "initializing"]
        assert data["service"] == "browser-service"

    async def test_fetch_simple_page(self, browser_client: httpx.AsyncClient) -> None:
        """Browser service can fetch a simple HTML page."""
        # Use httpbin.org for reliable testing
        response = await browser_client.post(
            "/fetch/text",
            json={
                "url": "https://httpbin.org/html",
                "timeout": 30000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert "text" in data
        assert "title" in data
        # httpbin returns HTML with "Herman Melville" text
        assert "Herman Melville" in data["text"]

    async def test_fetch_with_javascript(self, browser_client: httpx.AsyncClient) -> None:
        """Browser service executes JavaScript on the page."""
        # Fetch a page that requires JS rendering
        response = await browser_client.post(
            "/fetch/text",
            json={
                "url": "https://httpbin.org/html",
                "javascript": True,
                "timeout": 30000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200

    @pytest.mark.slow
    async def test_fetch_real_website(self, browser_client: httpx.AsyncClient) -> None:
        """Browser service can fetch a real website."""
        response = await browser_client.post(
            "/fetch/text",
            json={
                "url": "https://news.ycombinator.com",
                "timeout": 30000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert "Hacker News" in data["title"] or "news.ycombinator" in data["title"]
