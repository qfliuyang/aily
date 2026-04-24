from __future__ import annotations

from aily.config import Settings
from aily.llm.provider_routes import PrimaryLLMRoute


def test_primary_route_builds_kimi_client_from_settings():
    settings = Settings(
        llm_provider="kimi",
        kimi_api_key="test-kimi-key",
        kimi_model="kimi-k2.6",
        llm_max_concurrency=1,
        llm_min_interval_seconds=3.0,
    )

    client = PrimaryLLMRoute.from_settings(settings)

    assert client.base_url == "https://api.moonshot.cn/v1"
    assert client.api_key == "test-kimi-key"
    assert client.model == "kimi-k2.6"
    assert client.max_concurrency == 1
    assert client.min_interval_seconds == 3.0


def test_primary_route_resolves_workload_override_hierarchically():
    settings = Settings(
        llm_provider="kimi",
        kimi_api_key="test-kimi-key",
        kimi_model="kimi-k2.6",
        deepseek_api_key="test-deepseek-key",
        deepseek_model="deepseek-v4-pro",
        llm_workload_routes_json=(
            '{"dikiwi":{"provider":"deepseek","model":"deepseek-v4-pro"},'
            '"dikiwi.insight":{"model":"deepseek-v4-pro","thinking":true}}'
        ),
    )

    route = PrimaryLLMRoute.resolve_route(settings, workload="dikiwi.insight")

    assert route.provider == "deepseek"
    assert route.api_key == "test-deepseek-key"
    assert route.model == "deepseek-v4-pro"
    assert route.thinking is True
    assert route.base_url == "https://api.deepseek.com"


def test_primary_route_supports_workload_specific_client_building():
    settings = Settings(
        llm_provider="kimi",
        kimi_api_key="test-kimi-key",
        kimi_model="kimi-k2.6",
        deepseek_api_key="test-deepseek-key",
        llm_workload_routes_json='{"guru":{"provider":"deepseek","model":"deepseek-v4-pro","thinking":true}}',
    )

    client = PrimaryLLMRoute.from_settings(settings, workload="guru")

    assert client.base_url == "https://api.deepseek.com"
    assert client.api_key == "test-deepseek-key"
    assert client.model == "deepseek-v4-pro"
    assert client.thinking is True


def test_primary_route_rejects_deepseek_for_multimodal_vision_workload():
    settings = Settings(
        llm_provider="kimi",
        kimi_api_key="test-kimi-key",
        deepseek_api_key="test-deepseek-key",
        llm_workload_routes_json='{"chaos.vision":{"provider":"deepseek","model":"deepseek-v4-pro"}}',
    )

    import pytest

    with pytest.raises(ValueError, match="DeepSeek is not configured for chaos.vision"):
        PrimaryLLMRoute.resolve_route(settings, workload="chaos.vision")


def test_primary_route_uses_provider_specific_vision_model_for_zhipu():
    settings = Settings(
        llm_provider="zhipu",
        zhipu_api_key="test-zhipu-key",
        zhipu_model="glm-5.1",
        zhipu_vision_model="glm-4.5v",
    )

    route = PrimaryLLMRoute.resolve_route(settings, workload="chaos.vision")

    assert route.provider == "zhipu"
    assert route.model == "glm-4.5v"
