from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_customer_ship_readiness import audit


pytestmark = pytest.mark.contract


def _write_manifest(root: Path, run_id: str, data: dict) -> None:
    run_dir = root / "logs" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(data), encoding="utf-8")


def test_customer_ship_audit_rejects_split_ui_docker_and_provider_proof(tmp_path: Path) -> None:
    head = "HEADSHA"
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "CUSTOMER_SHIP_READINESS_AUDIT.md").write_text(
        "Customer-ready status: Not achieved\n"
        "CSHIP-001\nCSHIP-002\nCSHIP-003\nCSHIP-004\n"
        "Blocking gaps\nNext verification checkpoint\n",
        encoding="utf-8",
    )
    _write_manifest(
        tmp_path,
        "studio",
        {
            "git_sha": head,
            "dirty_worktree": False,
            "exit_code": 0,
            "scenario": "studio_agent_browser_e2e",
            "acceptance": {
                "mocked": False,
                "real_browser": True,
                "real_fastapi": True,
                "real_vault": True,
                "real_graph_db": True,
                "real_llm": False,
            },
        },
    )
    _write_manifest(
        tmp_path,
        "docker",
        {
            "git_sha": head,
            "dirty_worktree": False,
            "exit_code": 0,
            "scenario": "docker_preprod_e2e",
            "acceptance": {
                "mocked": False,
                "real_docker": True,
                "real_browser": True,
                "real_fastapi": True,
                "real_vault": True,
                "real_graph_db": True,
                "real_llm": False,
            },
        },
    )
    _write_manifest(
        tmp_path,
        "provider-parent",
        {
            "git_sha": "PARENTSHA",
            "dirty_worktree": False,
            "exit_code": 0,
            "scenario": "full_pipeline_1pdf",
            "vault_counts_after": {stage: 1 for stage in ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]},
            "acceptance": {"mocked": False, "real_llm": True, "real_vault": True, "real_graph_db": True},
        },
    )

    result = audit(tmp_path, head_sha=head)

    by_id = {criterion["id"]: criterion for criterion in result["criteria"]}
    assert by_id["CSHIP-001"]["passed"] is True
    assert by_id["CSHIP-002"]["passed"] is True
    assert by_id["CSHIP-003"]["passed"] is False
    assert by_id["CSHIP-004"]["passed"] is False
    assert result["ready_to_ship_customers"] is False


def test_customer_ship_audit_requires_a_single_current_clean_combined_customer_run(tmp_path: Path) -> None:
    head = "HEADSHA"
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "CUSTOMER_SHIP_READINESS_AUDIT.md").write_text(
        "Customer-ready status: Not achieved\n"
        "CSHIP-001\nCSHIP-002\nCSHIP-003\nCSHIP-004\n"
        "Blocking gaps\nNext verification checkpoint\n",
        encoding="utf-8",
    )
    _write_manifest(
        tmp_path,
        "combined",
        {
            "git_sha": head,
            "dirty_worktree": False,
            "exit_code": 0,
            "scenario": "docker_customer_real_llm_browser_e2e",
            "vault_counts_after": {stage: 1 for stage in ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]},
            "acceptance": {
                "mocked": False,
                "real_docker": True,
                "real_browser": True,
                "real_fastapi": True,
                "real_vault": True,
                "real_graph_db": True,
                "real_llm": True,
            },
        },
    )

    result = audit(tmp_path, head_sha=head)

    assert result["blocking_gaps"] == []
    assert result["ready_to_ship_customers"] is True
