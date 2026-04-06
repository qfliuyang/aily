from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Request, HTTPException

from aily.config import SETTINGS
from aily.queue.db import QueueDB

logger = logging.getLogger(__name__)
router = APIRouter()

dedup_cache: dict[str, float] = {}
DEDUP_TTL = 60.0


def _extract_url(text: str) -> Optional[str]:
    m = re.search(r"https?://\S+", text)
    return m.group(0) if m else None


def _clean_dedup() -> None:
    now = time.time()
    expired = [k for k, v in dedup_cache.items() if now - v > DEDUP_TTL]
    for k in expired:
        dedup_cache.pop(k, None)


def _verify_signature(body: bytes, timestamp: str, signature: str, encrypt_key: str) -> bool:
    if not signature or not timestamp:
        return False
    sign = signature[len("sha256="):]
    expected = hmac.new(
        encrypt_key.encode(),
        f"{timestamp}\n{body.decode()}\n".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sign, expected)


@router.post("/webhook/feishu")
async def feishu_webhook(request: Request) -> dict:
    body = await request.body()
    timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
    signature = request.headers.get("X-Lark-Signature", "")

    if not _verify_signature(body, timestamp, signature, SETTINGS.feishu_encrypt_key):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = json.loads(body)

    if "challenge" in data:
        return {"challenge": data["challenge"]}

    event_id = data.get("header", {}).get("event_id", "")
    _clean_dedup()
    now = time.time()
    if event_id in dedup_cache:
        return {"status": "ok"}
    dedup_cache[event_id] = now

    event = data.get("event", {})
    message = event.get("message", {})
    if message.get("message_type") != "text":
        return {"status": "ok"}

    content = json.loads(message.get("content", "{}"))
    text = content.get("text", "")
    url = _extract_url(text)

    db = QueueDB(SETTINGS.queue_db_path)
    await db.initialize()
    open_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")

    if url is None:
        await db.enqueue("agent_request", {"request": text, "open_id": open_id})
        logger.info("Enqueued agent request from Feishu: %s", text[:50])
        return {"status": "ok"}

    log_id = await db.insert_raw_log(url, source="manual")
    if log_id is None:
        logger.info("Deduplicated URL from Feishu: %s", url)
        return {"status": "ok"}
    await db.enqueue("url_fetch", {"url": url, "open_id": open_id})
    logger.info("Enqueued URL from Feishu: %s", url)
    return {"status": "ok"}
