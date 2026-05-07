from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_customer_ship_readiness import audit
from scripts.run_docker_preprod_e2e import _is_impact_or_later, _llm_receipt_summary


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
        "Customer-ready status: Achieved\n"
        "CSHIP-001\nCSHIP-002\nCSHIP-003\nCSHIP-004\n"
        "Next verification checkpoint\n",
        encoding="utf-8",
    )
    (docs / "CUSTOMER_SHIPPING_RUNBOOK.md").write_text(
        "single-tenant/private deployment\n--require-real-llm\n"
        "provider_verified_dikiwi=true\nSecurity boundaries\nKnown limits\n",
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
            "vault_counts_after": {
                stage: 1
                for stage in ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]
            },
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
        "Customer-ready status: Achieved\n"
        "CSHIP-001\nCSHIP-002\nCSHIP-003\nCSHIP-004\n"
        "Next verification checkpoint\n",
        encoding="utf-8",
    )
    (docs / "CUSTOMER_SHIPPING_RUNBOOK.md").write_text(
        "single-tenant/private deployment\n--require-real-llm\n"
        "provider_verified_dikiwi=true\nSecurity boundaries\nKnown limits\n",
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
            "vault_counts_after": {
                stage: 1
                for stage in ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]
            },
            "acceptance": {
                "mocked": False,
                "real_docker": True,
                "real_browser": True,
                "real_fastapi": True,
                "real_vault": True,
                "real_graph_db": True,
                "real_llm": True,
                "provider_verified_dikiwi": True,
            },
        },
    )

    result = audit(tmp_path, head_sha=head)

    assert result["blocking_gaps"] == []
    assert result["ready_to_ship_customers"] is True


def test_customer_ship_audit_rejects_combined_run_without_provider_receipts(tmp_path: Path) -> None:
    head = "HEADSHA"
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "CUSTOMER_SHIP_READINESS_AUDIT.md").write_text(
        "Customer-ready status: Achieved\n"
        "CSHIP-001\nCSHIP-002\nCSHIP-003\nCSHIP-004\n"
        "Next verification checkpoint\n",
        encoding="utf-8",
    )
    (docs / "CUSTOMER_SHIPPING_RUNBOOK.md").write_text(
        "single-tenant/private deployment\n--require-real-llm\n"
        "provider_verified_dikiwi=true\nSecurity boundaries\nKnown limits\n",
        encoding="utf-8",
    )
    _write_manifest(
        tmp_path,
        "combined-unverified",
        {
            "git_sha": head,
            "dirty_worktree": False,
            "exit_code": 0,
            "scenario": "docker_customer_real_llm_browser_e2e",
            "vault_counts_after": {
                stage: 1
                for stage in ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]
            },
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
    by_id = {criterion["id"]: criterion for criterion in result["criteria"]}

    assert by_id["CSHIP-004"]["passed"] is False
    assert result["ready_to_ship_customers"] is False


def test_docker_llm_receipt_summary_rejects_unverified_successes() -> None:
    summary = _llm_receipt_summary([
        {
            "success": True,
            "provider": "kimi",
            "base_url": "https://api.moonshot.cn/v1",
            "model": "kimi-k2.6",
            "status_code": 200,
            "provider_response_id": "chatcmpl-real",
            "usage": {"total_tokens": 10},
        },
        {"success": True, "model": "kimi-k2.6", "status_code": 200},
    ])

    assert summary["successes"] == 2
    assert summary["provider_verified_successes"] == 1
    assert summary["unverified_successes"] == 1


def test_docker_real_llm_gate_accepts_impact_or_downstream_final_stage() -> None:
    assert _is_impact_or_later("IMPACT") is True
    assert _is_impact_or_later("RESIDUAL") is True
    assert _is_impact_or_later("KNOWLEDGE") is False
