"""
Feishu WebSocket long connection client.

This uses Feishu's SDK to establish a WebSocket connection to Feishu servers,
eliminating the need for public webhook URLs.
"""

from __future__ import annotations

import asyncio
import logging
import json
from typing import Callable

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from aily.config import SETTINGS
from aily.queue.db import QueueDB

logger = logging.getLogger(__name__)


class FeishuWSClient:
    """
    Feishu WebSocket client for receiving events via long connection.

    This avoids the need for public webhook URLs by establishing a WebSocket
    connection from local machine to Feishu servers.
    """

    def __init__(self, db: QueueDB) -> None:
        self.db = db
        self.client: lark.ws.Client | None = None
        self._running = False

    def _handle_message(self, data: P2ImMessageReceiveV1) -> None:
        """Handle incoming message event."""
        logger.info("[FeishuWS] Received message: %s", data.header.event_id)

        # Extract message info
        message = data.event.message
        sender = data.event.sender

        msg_type = message.message_type
        open_id = sender.sender_id.open_id if sender.sender_id else ""

        logger.info("[FeishuWS] Message type: %s from: %s", msg_type, open_id)

        # Handle text messages
        if msg_type == "text":
            content = json.loads(message.content)
            text = content.get("text", "")

            # Extract URL if present
            import re
            url_match = re.search(r"https?://\S+", text)

            if url_match:
                url = url_match.group(0)
                logger.info("[FeishuWS] URL found: %s", url)

                # Enqueue URL fetch job
                asyncio.create_task(self._enqueue_url(url, open_id))
            else:
                logger.info("[FeishuWS] Text message (no URL): %s", text[:50])

        # Handle voice messages
        elif msg_type == "voice":
            content = json.loads(message.content)
            file_key = content.get("file_key")
            file_name = content.get("file_name", "voice.mp3")

            if file_key and SETTINGS.feishu_voice_enabled:
                logger.info("[FeishuWS] Voice message: %s", file_key)
                asyncio.create_task(self._enqueue_voice(file_key, file_name, open_id))

    async def _enqueue_url(self, url: str, open_id: str) -> None:
        """Enqueue URL fetch job."""
        try:
            enqueued = await self.db.enqueue_url(url, open_id=open_id, source="manual")
            if enqueued:
                logger.info("[FeishuWS] URL enqueued: %s", url)
            else:
                logger.info("[FeishuWS] URL deduplicated: %s", url)
        except Exception as e:
            logger.exception("[FeishuWS] Failed to enqueue URL: %s", e)

    async def _enqueue_voice(self, file_key: str, file_name: str, open_id: str) -> None:
        """Enqueue voice message job."""
        try:
            await self.db.enqueue(
                "voice_message",
                {
                    "file_key": file_key,
                    "file_name": file_name,
                    "open_id": open_id,
                    "message_id": "",
                },
            )
            logger.info("[FeishuWS] Voice enqueued: %s", file_key)
        except Exception as e:
            logger.exception("[FeishuWS] Failed to enqueue voice: %s", e)

    def start(self) -> None:
        """Start the WebSocket client."""
        if self._running:
            logger.warning("[FeishuWS] Already running")
            return

        self._running = True

        # Build event handler
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_message)
            .build()
        )

        # Create WebSocket client
        self.client = lark.ws.Client(
            SETTINGS.feishu_app_id,
            SETTINGS.feishu_app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        # Start in background thread
        import threading
        self._thread = threading.Thread(target=self._run_client, daemon=True)
        self._thread.start()

        logger.info("[FeishuWS] Client started (APP_ID: %s...)", SETTINGS.feishu_app_id[:20])

    def _run_client(self) -> None:
        """Run the client (blocking)."""
        try:
            self.client.start()
        except Exception as e:
            logger.exception("[FeishuWS] Client error: %s", e)
            self._running = False

    def stop(self) -> None:
        """Stop the WebSocket client."""
        self._running = False
        if self.client:
            # Note: lark.ws.Client doesn't have a clean stop method
            # It will be terminated when the process ends
            pass
        logger.info("[FeishuWS] Client stopped")


# Singleton instance
_ws_client: FeishuWSClient | None = None


def get_ws_client(db: QueueDB | None = None) -> FeishuWSClient:
    """Get or create WebSocket client singleton."""
    global _ws_client
    if _ws_client is None:
        if db is None:
            from aily.queue.db import QueueDB
            from aily.config import SETTINGS
            db = QueueDB(SETTINGS.queue_db_path)
        _ws_client = FeishuWSClient(db)
    return _ws_client
