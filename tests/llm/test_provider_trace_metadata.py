from __future__ import annotations

import pytest
import time

from aily.llm.client import LLMClient

pytestmark = pytest.mark.unit


def test_llm_client_builds_provider_receipt_metadata() -> None:
    client = LLMClient(base_url="https://api.moonshot.cn/v1", api_key="test-key", model="kimi-k2.6")

    metadata = client._provider_trace_metadata(
        request_id="local-request-123",
        started=time.monotonic(),
        success=True,
        status_code=200,
        response_data={
            "id": "chatcmpl-moonshot-123",
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        },
        response_headers={"x-request-id": "moonshot-request-123"},
    )

    assert metadata["success"] is True
    assert metadata["provider"] == "kimi"
    assert metadata["base_url"] == "https://api.moonshot.cn/v1"
    assert metadata["status_code"] == 200
    assert metadata["provider_response_id"] == "chatcmpl-moonshot-123"
    assert metadata["provider_request_id"] == "moonshot-request-123"
    assert metadata["usage"]["total_tokens"] == 10
