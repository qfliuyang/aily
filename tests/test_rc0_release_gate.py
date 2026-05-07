from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_rc0_release_gate
from scripts.test_framework import full_pipeline_acceptance_failures


pytestmark = pytest.mark.contract


def test_practical_gate_contains_fast_health_and_anti_mock_checks(tmp_path: Path) -> None:
    commands = run_rc0_release_gate._commands("practical", tmp_path)

    names = [command.name for command in commands]

    assert names == [
        "project_health",
        "rc0_gate_self_tests",
        "root_pytest_collection",
        "anti_mock_acceptance_contract",
        "capture_coverage_contract",
        "queue_reliability_contract",
        "dikiwi_audit_contracts",
    ]
    assert all(not command.expensive for command in commands)
    assert all(command.timeout_seconds > 0 for command in commands)
    assert any("scripts/verify_project_health.py" in command.argv for command in commands)
    assert any("tests/verify/test_no_mock_acceptance.py" in command.argv for command in commands)


def test_full_gate_extends_practical_gate_with_expensive_release_checks(tmp_path: Path) -> None:
    commands = run_rc0_release_gate._commands("full", tmp_path)
    names = [command.name for command in commands]

    assert names[:4] == [
        "project_health",
        "rc0_gate_self_tests",
        "root_pytest_collection",
        "anti_mock_acceptance_contract",
    ]
    assert names[4:7] == ["capture_coverage_contract", "queue_reliability_contract", "dikiwi_audit_contracts"]
    assert {
        "provider_verified_dikiwi_e2e",
        "frontend_build",
        "studio_browser_e2e",
        "docker_preprod_e2e",
        "chaos_failure_readiness",
    } <= set(names)
    provider_gate = next(command for command in commands if command.name == "provider_verified_dikiwi_e2e")
    assert "scripts/run_rc0_provider_dikiwi_gate.py" in provider_gate.argv
    assert "AILY-RC0-005" in provider_gate.target_ids
    assert "AILY-RC0-006" in provider_gate.target_ids
    assert any(command.expensive for command in commands if command.name == "docker_preprod_e2e")
    assert all(command.timeout_seconds <= 1200 for command in commands)
    assert any("tests/chaos/test_failure_readiness.py" in command.argv for command in commands)


def test_manifest_records_failed_command_and_real_boundary_flags(tmp_path: Path) -> None:
    results = [
        {
            "name": "project_health",
            "argv": ["python", "scripts/verify_project_health.py"],
            "target_ids": ["AILY-RC0-001"],
            "expensive": False,
            "started_at": "2026-05-06T00:00:00+00:00",
            "completed_at": "2026-05-06T00:00:01+00:00",
            "exit_code": 1,
            "stdout": "stdout.log",
            "stderr": "stderr.log",
        }
    ]

    run_rc0_release_gate._write_manifest(tmp_path, "full", results, listed_only=False)

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["exit_code"] == 1
    assert manifest["acceptance"]["mocked"] is False
    assert manifest["acceptance"]["real_browser"] is False
    assert manifest["acceptance"]["real_docker"] is False
    assert manifest["commands"][0]["target_ids"] == ["AILY-RC0-001"]


def test_manifest_real_boundary_flags_require_successful_real_commands(tmp_path: Path) -> None:
    results = [
        {
            "name": "studio_browser_e2e",
            "argv": ["python", "scripts/run_studio_agent_browser_e2e.py"],
            "target_ids": ["AILY-RC0-008"],
            "expensive": True,
            "started_at": "2026-05-06T00:00:00+00:00",
            "completed_at": "2026-05-06T00:00:01+00:00",
            "exit_code": 0,
            "stdout": "stdout.log",
            "stderr": "stderr.log",
        },
        {
            "name": "docker_preprod_e2e",
            "argv": ["python", "scripts/run_docker_preprod_e2e.py"],
            "target_ids": ["AILY-RC0-009"],
            "expensive": True,
            "started_at": "2026-05-06T00:00:02+00:00",
            "completed_at": "2026-05-06T00:00:03+00:00",
            "exit_code": 1,
            "stdout": "stdout.log",
            "stderr": "stderr.log",
        },
    ]

    run_rc0_release_gate._write_manifest(tmp_path, "full", results, listed_only=False)

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["acceptance"]["real_browser"] is True
    assert manifest["acceptance"]["real_files"] is True
    assert manifest["acceptance"]["real_docker"] is False
    assert manifest["acceptance"]["real_llm"] is False


def test_manifest_real_llm_requires_provider_verified_dikiwi_success(tmp_path: Path) -> None:
    results = [
        {
            "name": "provider_verified_dikiwi_e2e",
            "argv": ["python", "scripts/run_rc0_provider_dikiwi_gate.py"],
            "target_ids": ["AILY-RC0-005", "AILY-RC0-006"],
            "expensive": True,
            "started_at": "2026-05-06T00:00:00+00:00",
            "completed_at": "2026-05-06T00:00:01+00:00",
            "exit_code": 0,
            "stdout": "stdout.log",
            "stderr": "stderr.log",
        }
    ]

    run_rc0_release_gate._write_manifest(tmp_path, "full", results, listed_only=False)

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["acceptance"]["real_llm"] is True
    assert manifest["acceptance"]["provider_verified_dikiwi"] is True
    assert manifest["acceptance"]["real_graph_db"] is True


def test_full_pipeline_acceptance_rejects_partial_dikiwi_success() -> None:
    failures = full_pipeline_acceptance_failures(
        [
            {
                "pdf": "sample.pdf",
                "bridge_result": {
                    "stage": "KNOWLEDGE",
                    "stage_results": [
                        {"stage": "DATA", "success": True, "items_output": 26},
                        {"stage": "INFORMATION", "success": True, "items_output": 26},
                        {"stage": "KNOWLEDGE", "success": True, "items_output": 0},
                    ],
                },
            }
        ],
        {"01-Data": 26, "02-Information": 26},
    )

    messages = {failure["error"] for failure in failures}
    assert "final_stage=KNOWLEDGE expected IMPACT" in messages
    assert "stage KNOWLEDGE produced no output" in messages
    assert "missing stage result IMPACT" in messages
    assert "vault has no persisted notes for 06-Impact" in messages


def test_full_pipeline_acceptance_accepts_complete_dikiwi_run() -> None:
    stage_results = [
        {"stage": stage, "success": True, "items_output": 1}
        for stage in ("DATA", "INFORMATION", "KNOWLEDGE", "INSIGHT", "WISDOM", "IMPACT")
    ]

    failures = full_pipeline_acceptance_failures(
        [{"pdf": "sample.pdf", "bridge_result": {"stage": "IMPACT", "stage_results": stage_results}}],
        {"03-Knowledge": 1, "04-Insight": 1, "05-Wisdom": 1, "06-Impact": 1},
    )

    assert failures == []
