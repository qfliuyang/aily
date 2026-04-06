import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from aily.bot.webhook import router, dedup_cache
from aily.config import SETTINGS


@pytest.fixture
def client():
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _sign(body: bytes, timestamp: str = "1234567890") -> str:
    expected = hmac.new(
        SETTINGS.feishu_encrypt_key.encode(),
        f"{timestamp}\n{body.decode()}\n".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={expected}"


def test_challenge(client: TestClient):
    payload = {"challenge": "abc123"}
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhook/feishu",
        content=body,
        headers={
            "X-Lark-Request-Timestamp": "1234567890",
            "X-Lark-Signature": _sign(body),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "abc123"


def test_valid_webhook_with_url(client: TestClient):
    dedup_cache.clear()
    payload = {
        "header": {"event_id": "evt_1"},
        "event": {
            "sender": {"sender_id": {"open_id": "u1"}},
            "message": {
                "message_type": "text",
                "content": json.dumps({"text": "Check this https://example.com"}),
            },
        },
    }
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhook/feishu",
        content=body,
        headers={
            "X-Lark-Request-Timestamp": "1234567890",
            "X-Lark-Signature": _sign(body),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_duplicate_event_id_deduped(client: TestClient):
    dedup_cache.clear()
    payload = {
        "header": {"event_id": "evt_dup"},
        "event": {
            "sender": {"sender_id": {"open_id": "u1"}},
            "message": {
                "message_type": "text",
                "content": json.dumps({"text": "https://example.com"}),
            },
        },
    }
    body = json.dumps(payload).encode()
    resp1 = client.post(
        "/webhook/feishu",
        content=body,
        headers={
            "X-Lark-Request-Timestamp": "1234567890",
            "X-Lark-Signature": _sign(body),
        },
    )
    resp2 = client.post(
        "/webhook/feishu",
        content=body,
        headers={
            "X-Lark-Request-Timestamp": "1234567890",
            "X-Lark-Signature": _sign(body),
        },
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200


def test_invalid_signature(client: TestClient):
    payload = {"header": {"event_id": "evt_bad"}, "event": {}}
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhook/feishu",
        content=body,
        headers={
            "X-Lark-Request-Timestamp": "1234567890",
            "X-Lark-Signature": "sha256=badhash",
        },
    )
    assert resp.status_code == 403


def test_missing_url_returns_ok(client: TestClient):
    dedup_cache.clear()
    payload = {
        "header": {"event_id": "evt_no_url"},
        "event": {
            "sender": {"sender_id": {"open_id": "u1"}},
            "message": {
                "message_type": "text",
                "content": json.dumps({"text": "hello world"}),
            },
        },
    }
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhook/feishu",
        content=body,
        headers={
            "X-Lark-Request-Timestamp": "1234567890",
            "X-Lark-Signature": _sign(body),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_text_message_enqueues_agent_request(client: TestClient):
    dedup_cache.clear()
    payload = {
        "header": {"event_id": "evt_agent"},
        "event": {
            "sender": {"sender_id": {"open_id": "u1"}},
            "message": {
                "message_type": "text",
                "content": json.dumps({"text": "summarize yesterday"}),
            },
        },
    }
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhook/feishu",
        content=body,
        headers={
            "X-Lark-Request-Timestamp": "1234567890",
            "X-Lark-Signature": _sign(body),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
