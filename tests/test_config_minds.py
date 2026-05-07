from __future__ import annotations

from aily.config import MindsConfig


def test_minds_config_accepts_prefixed_and_normalized_env_keys() -> None:
    normalized = MindsConfig.from_settings(
        {
            "proposal_max_per_session": "2",
            "proposal_min_confidence": "0.55",
            "mac_enabled": "false",
        }
    )
    prefixed = MindsConfig.from_settings(
        {
            "aily_proposal_max_per_session": "3",
            "aily_proposal_min_confidence": "0.65",
            "aily_mac_enabled": "true",
        }
    )

    assert normalized.proposal_max_per_session == 2
    assert normalized.proposal_min_confidence == 0.55
    assert normalized.mac_enabled is False
    assert prefixed.proposal_max_per_session == 3
    assert prefixed.proposal_min_confidence == 0.65
    assert prefixed.mac_enabled is True


def test_runtime_security_rejects_placeholder_hosted_token(monkeypatch) -> None:
    from aily.config import SETTINGS

    monkeypatch.setattr(SETTINGS, "hosted_mode", True)
    monkeypatch.setattr(SETTINGS, "ui_auth_enabled", False)
    monkeypatch.setattr(SETTINGS, "ui_auth_token", "change-me")

    errors = SETTINGS.validate_runtime_security()

    assert errors
    assert "UI_AUTH_TOKEN" in errors[0]


def test_runtime_security_accepts_strong_hosted_token(monkeypatch) -> None:
    from aily.config import SETTINGS

    monkeypatch.setattr(SETTINGS, "hosted_mode", True)
    monkeypatch.setattr(SETTINGS, "ui_auth_token", "strong-random-token-123")

    assert SETTINGS.validate_runtime_security() == []
