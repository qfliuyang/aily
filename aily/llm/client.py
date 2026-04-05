from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        response_format: Optional[dict[str, str]] = None,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await self._chat_once(messages, temperature, response_format)
            except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
                last_error = exc
                logger.warning("LLM timeout (attempt %s)", attempt + 1)
            except LLMError:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning("LLM call failed (attempt %s): %s", attempt + 1, exc)
        raise LLMError(f"LLM failed after {self.max_retries + 1} attempts: {last_error}")

    async def _chat_once(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: Optional[dict[str, str]],
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise LLMError("Empty response from LLM")
        content = choices[0].get("message", {}).get("content", "")
        return content.strip()

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
    ) -> Any:
        content = await self.chat(
            messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("Malformed JSON from LLM, attempting repair")
            try:
                import json_repair

                repaired = await asyncio.to_thread(json_repair.repair_json, content)
                return json.loads(repaired)
            except Exception as repair_exc:
                raise LLMError(f"Could not parse or repair JSON: {repair_exc}") from exc
