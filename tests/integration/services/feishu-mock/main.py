"""
Feishu Mock Service

Simulates Feishu bot webhooks for integration testing.
Records all incoming requests for test verification.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Feishu Mock Service")

# In-memory storage for test verification
received_messages: list[dict] = []
sent_responses: list[dict] = []

WEBHOOK_SECRET = "test-secret"
VERIFICATION_TOKEN = "test-verification-token"


class FeishuMessage(BaseModel):
    """Standard Feishu message format."""
    message_type: str
    content: str
    message_id: Optional[str] = None


class FeishuEvent(BaseModel):
    """Standard Feishu event format."""
    sender: dict
    message: FeishuMessage
    timestamp: int


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "feishu-mock"}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_lark_signature: Optional[str] = Header(None),
    x_lark_request_timestamp: Optional[str] = Header(None),
) -> dict:
    """Receive webhook from Aily (simulating what Feishu would send)."""
    body = await request.body()
    data = json.loads(body)

    logger.info(f"Received webhook: {json.dumps(data, indent=2)}")

    # Verify signature if provided
    if x_lark_signature:
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            f"{x_lark_request_timestamp}\n{body.decode()}\n".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(x_lark_signature.replace("sha256=", ""), expected):
            raise HTTPException(status_code=403, detail="Invalid signature")

    # Handle challenge verification (Feishu bot setup)
    if "challenge" in data:
        return {"challenge": data["challenge"]}

    # Store message for test verification
    event_id = data.get("header", {}).get("event_id", str(uuid.uuid4()))
    received_messages.append({
        "event_id": event_id,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    })

    return {"status": "ok", "event_id": event_id}


@app.post("/open-apis/bot/v2/hook/{token}/send")
async def send_message(token: str, request: Request) -> dict:
    """Simulate Feishu bot sending message to user."""
    data = await request.json()

    logger.info(f"Bot sending message: {json.dumps(data, indent=2)}")

    message_id = str(uuid.uuid4())
    sent_responses.append({
        "message_id": message_id,
        "token": token,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    })

    return {
        "code": 0,
        "msg": "success",
        "data": {
            "message_id": message_id,
        }
    }


@app.post("/open-apis/auth/v3/tenant_access_token/internal")
async def get_access_token(request: Request) -> dict:
    """Simulate Feishu auth token endpoint."""
    data = await request.json()

    logger.info(f"Auth request for app: {data.get('app_id')}")

    return {
        "code": 0,
        "msg": "success",
        "tenant_access_token": f"mock-token-{int(time.time())}",
        "expire": 7200,
    }


@app.get("/open-apis/im/v1/messages/{message_id}"
)
async def get_message(message_id: str) -> dict:
    """Simulate getting message details."""
    return {
        "code": 0,
        "msg": "success",
        "data": {
            "items": [{
                "message_id": message_id,
                "content": json.dumps({"text": "Mock message content"}),
            }]
        }
    }


# Test inspection endpoints
@app.get("/__test/messages")
async def get_received_messages() -> dict:
    """Get all received messages (for test verification)."""
    return {"messages": received_messages}


@app.get("/__test/responses")
async def get_sent_responses() -> dict:
    """Get all sent responses (for test verification)."""
    return {"responses": sent_responses}


@app.post("/__test/reset")
async def reset_storage() -> dict:
    """Reset stored messages (call between tests)."""
    received_messages.clear()
    sent_responses.clear()
    return {"status": "reset"}


@app.post("/__test/simulate-message")
async def simulate_message(event: FeishuEvent) -> dict:
    """Simulate Feishu sending a message to Aily."""
    payload = {
        "header": {
            "event_id": str(uuid.uuid4()),
            "event_type": "im.message.receive_v1",
            "timestamp": int(time.time() * 1000),
        },
        "event": event.model_dump(),
    }

    # This would typically call Aily's webhook
    # For tests, we store it and the test will verify
    received_messages.append({
        "event_id": payload["header"]["event_id"],
        "timestamp": datetime.utcnow().isoformat(),
        "data": payload,
        "source": "simulated",
    })

    return {"status": "simulated", "event_id": payload["header"]["event_id"]}
