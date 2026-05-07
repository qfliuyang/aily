from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.contract


def test_rc0_quickstart_covers_release_documentation_contract() -> None:
    text = Path("docs/RC0_QUICKSTART.md").read_text(encoding="utf-8")
    required_phrases = [
        "docker compose build",
        "docker compose up -d",
        "Studio",
        "Upload files",
        "Submit URLs",
        "Submit text",
        "/health",
        "/ready",
        "create_backup",
        "restore_backup_dry_run",
        "Troubleshooting",
        "Known Limitations",
        "UI_AUTH_TOKEN",
        "LLM provider key",
    ]

    missing = [phrase for phrase in required_phrases if phrase not in text]

    assert missing == []


def test_rc0_quickstart_links_to_operator_sources() -> None:
    text = Path("docs/RC0_QUICKSTART.md").read_text(encoding="utf-8")
    linked_docs = [
        "DOCKER_PREPROD.md",
        "HOSTED_PRIVATE_WEBSITE_RUNBOOK.md",
        "AILY_RC0_GOAL_CONTRACT.md",
        "release-rc0-evidence.md",
    ]

    missing = [doc for doc in linked_docs if f"]({doc})" not in text or not (Path("docs") / doc).exists()]

    assert missing == []
