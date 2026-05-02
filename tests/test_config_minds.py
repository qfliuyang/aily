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
