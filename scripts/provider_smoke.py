#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aily.config import Settings
from aily.llm.provider_routes import PrimaryLLMRoute


SMOKE_PROMPT = (
    "Return strict JSON with keys provider_check, innovation_angle, and risk. "
    "Use one sentence per value. Topic: AI-assisted EDA second-brain innovation."
)


def _provider_key(settings: Settings, provider: str) -> str:
    if provider == "kimi":
        return settings.kimi_api_key or settings.llm_api_key
    if provider == "deepseek":
        return settings.deepseek_api_key or settings.llm_api_key
    return ""


async def smoke_provider(provider: str, settings: Settings, timeout: float) -> dict[str, Any]:
    if not _provider_key(settings, provider):
        return {"provider": provider, "status": "skipped", "reason": "missing_api_key"}
    route = PrimaryLLMRoute.resolve_route(
        settings,
        workload="provider_smoke",
    )
    route = replace(
        route,
        provider=provider,
        api_key=_provider_key(settings, provider),
        model=getattr(settings, f"{provider}_model", "") or route.model,
        base_url=PrimaryLLMRoute._default_route_for_provider(provider).base_url,
        timeout=timeout,
        max_retries=0,
    )
    client = PrimaryLLMRoute.build_client(route)
    started = datetime.now(timezone.utc)
    try:
        payload = await client.chat_json(
            [
                {"role": "system", "content": "You are a provider smoke-test endpoint. Output only valid JSON."},
                {"role": "user", "content": SMOKE_PROMPT},
            ],
            temperature=0.2,
        )
        provider_metadata = dict(getattr(client, "last_response_metadata", {}) or {})
        provider_verified = bool(
            provider_metadata.get("provider")
            and provider_metadata.get("base_url")
            and provider_metadata.get("status_code")
            and provider_metadata.get("duration_ms")
            and (provider_metadata.get("provider_response_id") or provider_metadata.get("provider_request_id"))
        )
        status = "passed" if isinstance(payload, dict) and "innovation_angle" in payload and provider_verified else "failed"
        return {
            "provider": provider,
            "model": route.model,
            "status": status,
            "provider_verified": provider_verified,
            "started_at": started.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "provider_metadata": provider_metadata,
            "usage": client.get_usage_stats(),
            "output": payload,
        }
    except Exception as exc:
        return {
            "provider": provider,
            "model": route.model,
            "status": "failed",
            "started_at": started.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "error_type": exc.__class__.__name__,
            "provider_metadata": dict(getattr(client, "last_response_metadata", {}) or {}),
            "usage": client.get_usage_stats(),
        }


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run real provider smoke tests and save a report.")
    parser.add_argument("--providers", nargs="+", default=["kimi", "deepseek"])
    parser.add_argument("--output", type=Path, default=Path("logs/provider_smoke_report.json"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("PROVIDER_SMOKE_TIMEOUT", "45")))
    parser.add_argument(
        "--allow-skips",
        action="store_true",
        help="Return zero when providers are skipped for missing credentials. Never use for release acceptance.",
    )
    args = parser.parse_args()

    settings = Settings()
    results = [await smoke_provider(provider, settings, args.timeout) for provider in args.providers]
    report = {
        "run_id": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ_provider_smoke"),
        "mocked": False,
        "prompt": SMOKE_PROMPT,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    failed = [item for item in results if item["status"] == "failed"]
    skipped = [item for item in results if item["status"] == "skipped"]
    return 1 if failed or (skipped and not args.allow_skips) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
