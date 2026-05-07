from __future__ import annotations

import httpx
import pytest

from aily.llm.client import LLMClient


pytestmark = pytest.mark.unit


def _http_status_error(status_code: int, headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.moonshot.cn/v1/chat/completions")
    response = httpx.Response(status_code, headers=headers or {}, request=request)
    return httpx.HTTPStatusError("provider error", request=request, response=response)


def test_retry_delay_uses_provider_retry_after_for_rate_limits() -> None:
    client = LLMClient(api_key="test")
    exc = _http_status_error(429, {"retry-after": "17"})

    assert client._retry_delay_seconds(0, exc) == 17.0


def test_retry_delay_uses_conservative_fallback_for_rate_limits() -> None:
    client = LLMClient(api_key="test")
    exc = _http_status_error(429)

    assert client._retry_delay_seconds(0, exc) == 30.0
    assert client._retry_delay_seconds(1, exc) == 60.0
