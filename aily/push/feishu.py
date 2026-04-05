from __future__ import annotations

import json

from lark_oapi import Client
from lark_oapi.api.im.v1 import (
    CreateMessageRequestBodyBuilder,
    CreateMessageRequestBuilder,
)


class FeishuPusher:
    def __init__(self, app_id: str, app_secret: str) -> None:
        self.client = (
            Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .build()
        )

    async def send_message(self, receive_id: str, content: str) -> bool:
        body = (
            CreateMessageRequestBodyBuilder()
            .receive_id(receive_id)
            .msg_type("text")
            .content(json.dumps({"text": content}, ensure_ascii=False))
            .build()
        )
        req = (
            CreateMessageRequestBuilder()
            .receive_id_type("open_id")
            .request_body(body)
            .build()
        )
        resp = await self.client.im.v1.message.create.arequest(req)
        return resp.success()
