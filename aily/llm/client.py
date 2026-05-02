from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional
from uuid import uuid4

import httpx

from aily.ui.events import emit_ui_event
from aily.ui.telemetry import get_ui_telemetry_context

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

    def _is_kimi_k2_model(self) -> bool:
        return self.model.startswith("kimi-k2")

    def _is_deepseek_model(self) -> bool:
        return self.model.startswith("deepseek-") or "deepseek.com" in self.base_url

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: Optional[dict[str, str]],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        # Kimi K2.x and DeepSeek thinking mode both prefer temperature omitted.
        if not self._is_kimi_k2_model() and not (self._is_deepseek_model() and self.thinking):
            payload["temperature"] = temperature

        if response_format:
            payload["response_format"] = response_format

        if self._is_kimi_k2_model():
            payload["thinking"] = {"type": "enabled" if self.thinking else "disabled"}
        elif self._is_deepseek_model():
            payload["thinking"] = {"type": "enabled" if self.thinking else "disabled"}

        return payload

    def _provider_name(self) -> str:
        if "moonshot" in self.base_url or self.model.startswith("kimi-"):
            return "kimi"
        if "bigmodel" in self.base_url or self.model.startswith("glm-"):
            return "zhipu"
        if "deepseek" in self.base_url or self.model.startswith("deepseek-"):
            return "deepseek"
        return "unknown"

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

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        system_prompt: str | None = None,
    ) -> str:
        """Compatibility wrapper for single-prompt callers.

        Older DIKIWI gates and skills use a completion-style interface while
        provider implementations use OpenAI-compatible chat completions.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages, temperature=temperature)

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
        payload = self._build_payload(messages, temperature, response_format)
        context = get_ui_telemetry_context()
        request_id = str(uuid4())
        started = time.monotonic()
        await emit_ui_event(
            "llm_request_started",
            request_id=request_id,
            provider=self._provider_name(),
            model=self.model,
            base_url=self.base_url,
            message_count=len(messages),
            pipeline_id=context.get("pipeline_id"),
            upload_id=context.get("upload_id"),
            stage=context.get("stage"),
            workload=context.get("workload"),
        )

        try:
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
        except Exception as exc:
            await emit_ui_event(
                "llm_request_failed",
                request_id=request_id,
                provider=self._provider_name(),
                model=self.model,
                pipeline_id=context.get("pipeline_id"),
                upload_id=context.get("upload_id"),
                stage=context.get("stage"),
                workload=context.get("workload"),
                duration_ms=round((time.monotonic() - started) * 1000, 2),
                error=str(exc),
                error_type=exc.__class__.__name__,
            )
            raise

        choices = data.get("choices", [])
        if not choices:
            await emit_ui_event(
                "llm_request_failed",
                request_id=request_id,
                provider=self._provider_name(),
                model=self.model,
                pipeline_id=context.get("pipeline_id"),
                upload_id=context.get("upload_id"),
                stage=context.get("stage"),
                workload=context.get("workload"),
                duration_ms=round((time.monotonic() - started) * 1000, 2),
                error="Empty response from LLM",
                error_type="LLMError",
            )
            raise LLMError("Empty response from LLM")
        content = choices[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        self.usage_stats["prompt_tokens"] += usage.get("prompt_tokens", 0)
        self.usage_stats["completion_tokens"] += usage.get("completion_tokens", 0)
        self.usage_stats["total_tokens"] += usage.get("total_tokens", 0)
        self.usage_stats["calls"] += 1
        await emit_ui_event(
            "llm_request_completed",
            request_id=request_id,
            provider=self._provider_name(),
            model=self.model,
            pipeline_id=context.get("pipeline_id"),
            upload_id=context.get("upload_id"),
            stage=context.get("stage"),
            workload=context.get("workload"),
            duration_ms=round((time.monotonic() - started) * 1000, 2),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )
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
