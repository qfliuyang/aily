from __future__ import annotations

import asyncio
import json
import logging
import time
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
        thinking: bool = False,
        max_concurrency: int = 1,
        min_interval_seconds: float = 0.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.thinking = thinking
        self.max_concurrency = max(1, int(max_concurrency))
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._pace_lock = asyncio.Lock()
        self._last_request_started = 0.0
        self.usage_stats = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}

    async def _wait_for_rate_window(self) -> None:
        """Ensure request starts are spaced out to avoid bursty imports."""
        if self.min_interval_seconds <= 0:
            return

        async with self._pace_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_started
            if elapsed < self.min_interval_seconds:
                await asyncio.sleep(self.min_interval_seconds - elapsed)
            self._last_request_started = time.monotonic()

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
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
            except httpx.HTTPStatusError as exc:
                last_error = exc
                # Rate limiting (429) - use longer backoff
                if exc.response.status_code == 429:
                    wait_time = 5 * (2 ** attempt)  # 5s, 10s, 20s
                    logger.warning("Rate limited (429), waiting %ss before retry %s", wait_time, attempt + 1)
                    if attempt < self.max_retries:
                        await asyncio.sleep(wait_time)
                else:
                    logger.warning("LLM HTTP error (attempt %s): %s", attempt + 1, exc)
                    if attempt < self.max_retries:
                        await asyncio.sleep(2 ** attempt)
            except LLMError:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning("LLM call failed (attempt %s): %s", attempt + 1, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
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
        # Enable thinking mode for kimi-k2.5
        if self.thinking and "kimi-k2" in self.model:
            payload["thinking"] = {"type": "enabled"}

        async with self._semaphore:
            await self._wait_for_rate_window()
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
        usage = data.get("usage", {})
        self.usage_stats["prompt_tokens"] += usage.get("prompt_tokens", 0)
        self.usage_stats["completion_tokens"] += usage.get("completion_tokens", 0)
        self.usage_stats["total_tokens"] += usage.get("total_tokens", 0)
        self.usage_stats["calls"] += 1
        return content.strip()

    def get_usage_stats(self) -> dict[str, int]:
        return self.usage_stats.copy()

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
