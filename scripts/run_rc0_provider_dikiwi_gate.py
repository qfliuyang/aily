#!/usr/bin/env python3
"""Run provider-verified DIKIWI RC0 evidence and audits.

This gate is intentionally real-boundary only: it runs the real full-pipeline
scenario with `--log-llm`, builds a fresh SourceStore sample ledger, and then
audits the resulting vault/graph/LLM trace for provider receipt metadata.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def _run(argv: list[str], *, cwd: Path, stdout: Path, stderr: Path, timeout: int) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    stdout.parent.mkdir(parents=True, exist_ok=True)
    with stdout.open("w", encoding="utf-8") as out, stderr.open("w", encoding="utf-8") as err:
        try:
            proc = subprocess.run(
                argv,
                cwd=cwd,
                text=True,
                stdout=out,
                stderr=err,
                check=False,
                timeout=timeout,
            )
            exit_code = proc.returncode
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            err.write(f"\nCommand timed out after {timeout} seconds: {exc}\n")
            exit_code = 124
            timed_out = True
    return {
        "argv": argv,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "stdout": str(stdout.relative_to(ROOT)),
        "stderr": str(stderr.relative_to(ROOT)),
    }


def _latest_json(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"No {pattern!r} files found under {directory}")
    return matches[0]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real provider DIKIWI RC0 gate.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max", type=int, default=1)
    parser.add_argument("--phase-timeout", type=int, default=900)
    parser.add_argument("--min-eval-notes", type=int, default=25)
    args = parser.parse_args()

    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = output_dir.name
    vault = Path(f"/private/tmp/aily-{run_id}-provider-dikiwi-vault")
    full_pipeline_dir = output_dir / "full-pipeline"
    commands: list[dict[str, Any]] = []

    full_pipeline_cmd = [
        sys.executable,
        "scripts/run_test_suite.py",
        "full-pipeline",
        "--max",
        str(args.max),
        "--skip-business",
        "--log-llm",
        "--vault",
        str(vault),
        "--report-dir",
        str(full_pipeline_dir),
        "--phase-timeout",
        str(args.phase_timeout),
    ]
    commands.append(
        {
            "name": "full_pipeline_real_provider",
            **_run(
                full_pipeline_cmd,
                cwd=ROOT,
                stdout=output_dir / "full-pipeline.stdout.log",
                stderr=output_dir / "full-pipeline.stderr.log",
                timeout=args.phase_timeout + 180,
            ),
        }
    )
    if commands[-1]["exit_code"] != 0:
        return _write_manifest_and_exit(output_dir, commands, passed=False)

    report_path = _latest_json(full_pipeline_dir, "e2e_report_*.json")
    report = _load_json(report_path)
    evidence_manifest = Path(report["evidence_manifest"])
    llm_log = ROOT / report["llm_log_file"] if not Path(report["llm_log_file"]).is_absolute() else Path(report["llm_log_file"])
    manifest = _load_json(evidence_manifest)
    vault = Path(manifest["vault_path"])
    graph_db = Path(manifest["graph_db_path"])
    source_pdf = Path(report["results"][0]["bridge_result"]["source_path"])

    ledger_path = output_dir / "traceability-sample-ledger.json"
    audit_commands = [
        (
            "traceability_sample_ledger",
            [
                sys.executable,
                "scripts/build_rc0_traceability_sample_ledger.py",
                "--output",
                str(ledger_path),
                "--pdf",
                str(source_pdf),
            ],
            120,
        ),
        (
            "dikiwi_traceability_audit",
            [
                sys.executable,
                "scripts/audit_rc0_dikiwi_traceability.py",
                "--manifest",
                str(evidence_manifest),
                "--vault",
                str(vault),
                "--output",
                str(output_dir / "dikiwi-traceability-report.json"),
                "--llm-log",
                str(llm_log),
                "--sample-ledger",
                str(ledger_path),
            ],
            120,
        ),
        (
            "note_quality_audit",
            [
                sys.executable,
                "scripts/audit_rc0_note_quality.py",
                "--vault",
                str(vault),
                "--output",
                str(output_dir / "note-quality-report.json"),
                "--min-eval-notes",
                str(args.min_eval_notes),
            ],
            120,
        ),
        (
            "vault_graph_safety_audit",
            [
                sys.executable,
                "scripts/audit_rc0_vault_graph_safety.py",
                "--vault",
                str(vault),
                "--output",
                str(output_dir / "vault-graph-safety-report.json"),
            ],
            120,
        ),
        (
            "dikiwi_quality_audit",
            [
                sys.executable,
                "scripts/audit_dikiwi_quality.py",
                "--vault",
                str(vault),
                "--graph-db",
                str(graph_db),
                "--llm-log",
                str(llm_log),
                "--output",
                str(output_dir / "dikiwi-quality-report.json"),
                "--strict-graph",
                "--max-unresolved-wikilinks",
                "0",
            ],
            120,
        ),
    ]
    for name, argv, timeout in audit_commands:
        commands.append(
            {
                "name": name,
                **_run(
                    argv,
                    cwd=ROOT,
                    stdout=output_dir / f"{name}.stdout.log",
                    stderr=output_dir / f"{name}.stderr.log",
                    timeout=timeout,
                ),
            }
        )
        if commands[-1]["exit_code"] != 0:
            return _write_manifest_and_exit(output_dir, commands, passed=False)

    return _write_manifest_and_exit(
        output_dir,
        commands,
        passed=True,
        artifacts={
            "full_pipeline_report": str(report_path.relative_to(ROOT)),
            "evidence_manifest": str(evidence_manifest.relative_to(ROOT)),
            "vault": str(vault),
            "graph_db": str(graph_db),
            "llm_log": str(llm_log.relative_to(ROOT)),
            "sample_ledger": str(ledger_path.relative_to(ROOT)),
            "traceability_report": str((output_dir / "dikiwi-traceability-report.json").relative_to(ROOT)),
            "note_quality_report": str((output_dir / "note-quality-report.json").relative_to(ROOT)),
            "graph_safety_report": str((output_dir / "vault-graph-safety-report.json").relative_to(ROOT)),
            "dikiwi_quality_report": str((output_dir / "dikiwi-quality-report.json").relative_to(ROOT)),
        },
    )


def _write_manifest_and_exit(
    output_dir: Path,
    commands: list[dict[str, Any]],
    *,
    passed: bool,
    artifacts: dict[str, str] | None = None,
) -> int:
    manifest = {
        "run_id": output_dir.name,
        "scenario": "rc0_provider_dikiwi_gate",
        "mocked": False,
        "real_files": True,
        "real_source_store": True,
        "real_queue": True,
        "real_vault": True,
        "real_graph_db": True,
        "real_llm": True,
        "requires_provider_receipts": True,
        "started_at": commands[0]["started_at"] if commands else datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "exit_code": 0 if passed else 1,
        "commands": commands,
        "artifacts": artifacts or {},
    }
    path = output_dir / "provider-dikiwi-gate-manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
