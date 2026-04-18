from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aily.llm.client import LLMClient
from aily.llm.llm_router import LLMRouter


@dataclass(frozen=True)
class ProviderRoute:
    """Named route to a concrete LLM provider."""

    provider: str
    model: str
    base_url: str
    mode: str


class PrimaryLLMRoute:
    """Build the app's primary LLM client from an explicit provider route."""

    KIMI_ROUTE = ProviderRoute(
        provider="kimi",
        model="kimi-k2.5",
        base_url="https://api.moonshot.cn/v1",
        mode="standard",
    )

    ZHIPU_ROUTE = ProviderRoute(
        provider="zhipu",
        model="glm-4-flash",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        mode="standard",
    )

    @classmethod
    def route_zhipu(
        cls,
        *,
        api_key: str,
        model: str = "glm-4-flash",
        max_concurrency: int = 1,
        min_interval_seconds: float = 3.0,
    ) -> LLMClient:
        return LLMRouter.standard_zhipu(
            api_key=api_key,
            model=model,
            max_concurrency=max_concurrency,
            min_interval_seconds=min_interval_seconds,
        )

    @classmethod
    def route_kimi(
        cls,
        *,
        api_key: str,
        model: str = "kimi-k2.5",
        thinking: bool = True,
        max_concurrency: int = 1,
        min_interval_seconds: float = 3.0,
    ) -> LLMClient:
        return LLMRouter.standard_kimi(
            api_key=api_key,
            model=model,
            thinking=thinking,
            max_concurrency=max_concurrency,
            min_interval_seconds=min_interval_seconds,
        )

    @classmethod
    def from_settings(cls, settings: Any) -> LLMClient:
        provider = str(getattr(settings, "llm_provider", "kimi")).strip().lower()
        max_concurrency = int(getattr(settings, "llm_max_concurrency", 1))
        min_interval_seconds = float(getattr(settings, "llm_min_interval_seconds", 3.0))

        if provider == "kimi":
            api_key = (
                getattr(settings, "kimi_api_key", "")
                or getattr(settings, "llm_api_key", "")
            )
            model = getattr(settings, "kimi_model", "") or cls.KIMI_ROUTE.model
            return cls.route_kimi(
                api_key=api_key,
                model=model,
                max_concurrency=max_concurrency,
                min_interval_seconds=min_interval_seconds,
            )

        if provider == "zhipu":
            api_key = getattr(settings, "zhipu_api_key", "") or getattr(settings, "llm_api_key", "")
            model = getattr(settings, "zhipu_model", "") or cls.ZHIPU_ROUTE.model
            return cls.route_zhipu(
                api_key=api_key,
                model=model,
                max_concurrency=max_concurrency,
                min_interval_seconds=min_interval_seconds,
            )

        raise ValueError(
            f"Unsupported llm_provider={provider!r}. Create a dedicated route for that platform first."
        )
