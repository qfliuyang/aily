from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from aily.config import Settings


pytestmark = pytest.mark.contract


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_hosted_mode_requires_strong_ui_auth_token() -> None:
    cfg = settings(hosted_mode=True, ui_auth_enabled=True, ui_auth_token="change-me", aily_dikiwi_enabled=False)

    errors = cfg.validate_runtime_security()

    assert any("UI_AUTH_TOKEN" in error for error in errors)


def test_hosted_dikiwi_requires_real_provider_key() -> None:
    cfg = settings(
        hosted_mode=True,
        ui_auth_enabled=True,
        ui_auth_token="0123456789abcdef0123456789abcdef",
        llm_provider="kimi",
        llm_api_key="",
        kimi_api_key="",
        dikiwi_vault_path="/vault",
        aily_dikiwi_enabled=True,
    )

    errors = cfg.validate_runtime_security()

    assert any("real LLM provider key" in error for error in errors)


def test_hosted_dikiwi_accepts_auth_key_and_vault_path() -> None:
    cfg = settings(
        hosted_mode=True,
        ui_auth_enabled=True,
        ui_auth_token="0123456789abcdef0123456789abcdef",
        llm_provider="kimi",
        kimi_api_key="test-provider-key-not-a-real-secret",
        dikiwi_vault_path="/vault",
        aily_dikiwi_enabled=True,
    )

    assert cfg.validate_runtime_security() == []


def test_env_example_documents_production_security_and_provider_settings() -> None:
    text = Path(".env.example").read_text(encoding="utf-8")
    required_names = {
        "HOSTED_MODE",
        "UI_AUTH_ENABLED",
        "UI_AUTH_TOKEN",
        "OBSIDIAN_VAULT_PATH",
        "DIKIWI_VAULT_PATH",
        "AILY_DIKIWI_ENABLED",
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "KIMI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ZHIPU_API_KEY",
        "TAVILY_API_KEY",
        "BROWSER_USE_API_KEY",
    }

    missing = sorted(name for name in required_names if f"{name}=" not in text)

    assert missing == []
    assert "tvly-dev-" not in text
    assert "kimi-k2.6" in text


def test_tracked_files_do_not_contain_hardcoded_secret_literals() -> None:
    tracked = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    secret_pattern = re.compile(
        r"(sk-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9_]{10,}|AIza[0-9A-Za-z_-]{10,}|xox[baprs]-[A-Za-z0-9-]+|tvly-[A-Za-z0-9_-]{8,})"
    )
    ignored_prefixes = ("frontend/node_modules/", "logs/", ".omx/", ".omc/")
    allowed_placeholders = {"tvly-dev-xxxxxxxx"}
    findings: list[str] = []
    for rel in tracked:
        if rel.startswith(ignored_prefixes):
            continue
        path = Path(rel)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in secret_pattern.finditer(text):
            token = match.group(0)
            if token in allowed_placeholders or set(token.split("-", 1)[-1]) <= {"x"}:
                continue
            findings.append(f"{rel}: {token[:8]}...")

    assert findings == []
