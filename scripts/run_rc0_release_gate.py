#!/usr/bin/env python3
"""Run Aily RC0 verification gates and write reproducible evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LOG_ROOT = ROOT / "logs" / "runs"


@dataclass(frozen=True)
class GateCommand:
    name: str
    argv: list[str]
    target_ids: list[str]
    expensive: bool = False
    timeout_seconds: int = 300


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    ).stdout.strip()


def _dirty_worktree() -> bool:
    return bool(
        subprocess.run(
            ["git", "status", "--short"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        ).stdout.strip()
    )


def _commands(mode: str, run_dir: Path) -> list[GateCommand]:
    python = sys.executable
    practical = [
        GateCommand(
            name="project_health",
            argv=[
                python,
                "scripts/verify_project_health.py",
                "--check",
                "--json",
                "--output",
                str(run_dir / "project-health.json"),
            ],
            target_ids=["AILY-RC0-001", "AILY-RC0-002", "AILY-RC0-012"],
            timeout_seconds=120,
        ),
        GateCommand(
            name="rc0_gate_self_tests",
            argv=[python, "-m", "pytest", "-q", "tests/test_rc0_release_gate.py"],
            target_ids=["AILY-RC0-001"],
            timeout_seconds=60,
        ),
        GateCommand(
            name="root_pytest_collection",
            argv=[python, "-m", "pytest", "--collect-only", "-q", "tests"],
            target_ids=["AILY-RC0-001", "AILY-RC0-002"],
            timeout_seconds=120,
        ),
        GateCommand(
            name="anti_mock_acceptance_contract",
            argv=[
                python,
                "-m",
                "pytest",
                "-q",
                "tests/test_project_health.py",
                "tests/e2e/test_acceptance_manifest.py",
                "tests/verify/test_no_mock_acceptance.py",
                "tests/integration/test_conftest_quality.py",
            ],
            target_ids=["AILY-RC0-001", "AILY-RC0-002"],
            timeout_seconds=120,
        ),
        GateCommand(
            name="capture_coverage_contract",
            argv=[python, "-m", "pytest", "-q", "tests/test_capture_coverage.py"],
            target_ids=["AILY-RC0-001", "AILY-RC0-003"],
            timeout_seconds=60,
        ),
        GateCommand(
            name="queue_reliability_contract",
            argv=[python, "-m", "pytest", "-q", "tests/test_queue_reliability_contract.py"],
            target_ids=["AILY-RC0-001", "AILY-RC0-004"],
            timeout_seconds=60,
        ),
        GateCommand(
            name="dikiwi_audit_contracts",
            argv=[python, "-m", "pytest", "-q", "tests/test_rc0_dikiwi_audits.py"],
            target_ids=["AILY-RC0-001", "AILY-RC0-005", "AILY-RC0-006"],
            timeout_seconds=60,
        ),
    ]
    if mode == "practical":
        return practical

    return practical + [
        GateCommand(
            name="provider_verified_dikiwi_e2e",
            argv=[
                python,
                "scripts/run_rc0_provider_dikiwi_gate.py",
                "--output-dir",
                str(run_dir / "provider_verified_dikiwi_e2e"),
                "--max",
                "1",
                "--phase-timeout",
                "900",
            ],
            target_ids=["AILY-RC0-001", "AILY-RC0-005", "AILY-RC0-006", "AILY-RC0-007"],
            expensive=True,
            timeout_seconds=1200,
        ),
        GateCommand(
            name="fast_local_pytest",
            argv=[
                python,
                "-m",
                "pytest",
                "-q",
                "--ignore=tests/integration",
                "--ignore=tests/e2e",
            ],
            target_ids=["AILY-RC0-001"],
            expensive=True,
            timeout_seconds=240,
        ),
        GateCommand(
            name="frontend_build",
            argv=["npm", "--prefix", "frontend", "run", "build"],
            target_ids=["AILY-RC0-001", "AILY-RC0-008"],
            expensive=True,
            timeout_seconds=120,
        ),
        GateCommand(
            name="studio_browser_e2e",
            argv=[
                python,
                "scripts/run_studio_agent_browser_e2e.py",
                "--hosted-auth",
                "--exercise-retry",
                "--exercise-url",
                *(
                    ["--inspect-vault", os.environ["AILY_RC0_INSPECT_VAULT"]]
                    if os.environ.get("AILY_RC0_INSPECT_VAULT")
                    else []
                ),
            ],
            target_ids=["AILY-RC0-001", "AILY-RC0-008"],
            expensive=True,
            timeout_seconds=300,
        ),
        GateCommand(
            name="docker_preprod_e2e",
            argv=[
                python,
                "scripts/run_docker_preprod_e2e.py",
                "--build",
                "--exercise-url",
                "--exercise-retry",
            ],
            target_ids=["AILY-RC0-001", "AILY-RC0-009", "AILY-RC0-010"],
            expensive=True,
            timeout_seconds=900,
        ),
        GateCommand(
            name="chaos_failure_readiness",
            argv=[python, "-m", "pytest", "-q", "tests/chaos/test_failure_readiness.py"],
            target_ids=["AILY-RC0-001", "AILY-RC0-011"],
            expensive=True,
            timeout_seconds=120,
        ),
    ]


def _run_command(command: GateCommand, run_dir: Path) -> dict[str, object]:
    started_at = datetime.now(timezone.utc).isoformat()
    stdout_path = run_dir / f"{command.name}.stdout.log"
    stderr_path = run_dir / f"{command.name}.stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        try:
            proc = subprocess.run(
                command.argv,
                cwd=ROOT,
                text=True,
                stdout=stdout,
                stderr=stderr,
                check=False,
                timeout=command.timeout_seconds,
            )
            exit_code = proc.returncode
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            stderr.write(f"\nCommand timed out after {command.timeout_seconds} seconds: {exc}\n")
            exit_code = 124
            timed_out = True
    completed_at = datetime.now(timezone.utc).isoformat()
    return {
        "name": command.name,
        "argv": command.argv,
        "target_ids": command.target_ids,
        "expensive": command.expensive,
        "timeout_seconds": command.timeout_seconds,
        "started_at": started_at,
        "completed_at": completed_at,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": str(stdout_path.relative_to(ROOT)),
        "stderr": str(stderr_path.relative_to(ROOT)),
    }


def _passed_command_names(results: list[dict[str, object]]) -> set[str]:
    return {str(result["name"]) for result in results if int(result.get("exit_code", 1)) == 0}


def _acceptance_summary(results: list[dict[str, object]], listed_only: bool) -> dict[str, object]:
    """Summarize only evidence that actually ran and passed.

    The RC0 gate is intentionally anti-cheat: a requested full gate is not the
    same thing as real-boundary evidence. Failed or merely listed commands do
    not earn real browser/Docker/vault claims in the aggregate manifest.
    """

    passed = _passed_command_names(results)
    provider_dikiwi_passed = "provider_verified_dikiwi_e2e" in passed
    studio_passed = "studio_browser_e2e" in passed
    docker_passed = "docker_preprod_e2e" in passed
    if listed_only:
        provider_dikiwi_passed = False
        studio_passed = False
        docker_passed = False

    return {
        "mocked": False,
        "real_files": provider_dikiwi_passed or studio_passed or docker_passed,
        "real_graph_db": provider_dikiwi_passed or studio_passed or docker_passed,
        "real_vault": provider_dikiwi_passed or studio_passed or docker_passed,
        "real_llm": provider_dikiwi_passed,
        "real_browser": studio_passed or docker_passed,
        "real_docker": docker_passed,
        "provider_verified_dikiwi": provider_dikiwi_passed,
        "anti_cheat_note": (
            "Aggregate flags are true only for real-boundary commands that completed with exit_code=0; "
            "see per-command manifests for scenario-specific evidence."
        ),
    }


def _write_manifest(run_dir: Path, mode: str, results: list[dict[str, object]], listed_only: bool) -> None:
    manifest = {
        "run_id": run_dir.name,
        "scenario": "rc0_release_gate",
        "mode": mode,
        "listed_only": listed_only,
        "git_sha": _git_sha(),
        "dirty_worktree": _dirty_worktree(),
        "started_at": results[0]["started_at"] if results else datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "exit_code": 0 if listed_only or all(result["exit_code"] == 0 for result in results) else 1,
        "commands": results,
        "acceptance": _acceptance_summary(results, listed_only),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Aily RC0 release verification gates.")
    parser.add_argument("--mode", choices=["practical", "full"], default="practical")
    parser.add_argument("--list", action="store_true", help="List the commands without running them.")
    parser.add_argument("--run-id", help="Override evidence run id.")
    args = parser.parse_args()

    run_id = args.run_id or f"{_timestamp()}_rc0_{args.mode}_gate"
    run_dir = LOG_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    commands = _commands(args.mode, run_dir)
    (run_dir / "command.txt").write_text(
        " ".join([sys.executable, *sys.argv]) + "\n",
        encoding="utf-8",
    )
    (run_dir / "environment.json").write_text(
        json.dumps(
            {
                "cwd": str(ROOT),
                "python": sys.executable,
                "mode": args.mode,
                "env_flags": {
                    key: os.environ.get(key, "")
                    for key in ["HOSTED_MODE", "UI_AUTH_ENABLED", "LLM_PROVIDER"]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if args.list:
        results = [
            {
                "name": command.name,
                "argv": command.argv,
                "target_ids": command.target_ids,
                "expensive": command.expensive,
                "timeout_seconds": command.timeout_seconds,
                "exit_code": 0,
                "timed_out": False,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "stdout": "",
                "stderr": "",
            }
            for command in commands
        ]
        for command in commands:
            print(command.name + ": " + " ".join(command.argv))
        _write_manifest(run_dir, args.mode, results, listed_only=True)
        print(f"manifest: {run_dir / 'manifest.json'}")
        return 0

    results = []
    for command in commands:
        print(f"[rc0:{args.mode}] {command.name}")
        result = _run_command(command, run_dir)
        results.append(result)
        if result["exit_code"] != 0:
            _write_manifest(run_dir, args.mode, results, listed_only=False)
            print(f"FAILED {command.name}; manifest: {run_dir / 'manifest.json'}", file=sys.stderr)
            return int(result["exit_code"])

    _write_manifest(run_dir, args.mode, results, listed_only=False)
    print(f"PASS; manifest: {run_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
