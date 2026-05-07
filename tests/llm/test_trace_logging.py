from __future__ import annotations

import json
from pathlib import Path

import pytest

from aily.config import SETTINGS
from aily.llm.client import LLMClient


pytestmark = pytest.mark.unit


def test_llm_trace_log_writes_non_secret_provider_receipt(tmp_path: Path) -> None:
    old_path = SETTINGS.llm_trace_log_path
    SETTINGS.llm_trace_log_path = tmp_path / "llm-calls.jsonl"
    try:
        client = LLMClient(base_url="https://api.moonshot.cn/v1", api_key="secret-key", model="kimi-k2.6")
        client._append_trace_log(
            {
                "success": True,
                "provider": "kimi",
                "base_url": "https://api.moonshot.cn/v1",
                "model": "kimi-k2.6",
                "status_code": 200,
                "provider_response_id": "chatcmpl-real",
                "provider_request_id": "req-real",
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
            {"pipeline_id": "pipe-1", "upload_id": "upload-1", "stage": "DATA", "workload": "dikiwi"},
        )
    finally:
        SETTINGS.llm_trace_log_path = old_path

    records = [json.loads(line) for line in (tmp_path / "llm-calls.jsonl").read_text().splitlines()]

    assert records[0]["provider"] == "kimi"
    assert records[0]["provider_response_id"] == "chatcmpl-real"
    assert records[0]["pipeline_id"] == "pipe-1"
    assert "secret-key" not in json.dumps(records[0])
