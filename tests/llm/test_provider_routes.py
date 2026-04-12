from __future__ import annotations

from aily.config import Settings
from aily.llm.provider_routes import PrimaryLLMRoute


def test_primary_route_builds_zhipu_client_from_settings():
    settings = Settings(
        llm_provider="zhipu",
        zhipu_api_key="test-zhipu-key",
        zhipu_model="glm-4-flash",
        llm_max_concurrency=1,
        llm_min_interval_seconds=3.0,
    )

    client = PrimaryLLMRoute.from_settings(settings)

    assert client.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert client.api_key == "test-zhipu-key"
    assert client.model == "glm-4-flash"
    assert client.max_concurrency == 1
    assert client.min_interval_seconds == 3.0
