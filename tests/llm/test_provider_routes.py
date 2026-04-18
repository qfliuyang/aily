from __future__ import annotations

from aily.config import Settings
from aily.llm.provider_routes import PrimaryLLMRoute


def test_primary_route_builds_kimi_client_from_settings():
    settings = Settings(
        llm_provider="kimi",
        kimi_api_key="test-kimi-key",
        kimi_model="kimi-k2.5",
        llm_max_concurrency=1,
        llm_min_interval_seconds=3.0,
    )

    client = PrimaryLLMRoute.from_settings(settings)

    assert client.base_url == "https://api.moonshot.cn/v1"
    assert client.api_key == "test-kimi-key"
    assert client.model == "kimi-k2.5"
    assert client.max_concurrency == 1
    assert client.min_interval_seconds == 3.0
