#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Finding:
    kind: str
    path: str
    detail: str
    severity: str = "info"

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "path": self.path,
            "detail": self.detail,
            "severity": self.severity,
        }


def _tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        text=True,
    )
    return [REPO_ROOT / line.strip() for line in output.splitlines() if line.strip()]


def scan_skipped_tests(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        if not path.name.startswith("test_") or path.suffix != ".py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for idx, line in enumerate(text.splitlines(), start=1):
            if "@pytest.mark.skip" in line or "pytest.skip(" in line:
                findings.append(Finding("skipped_test", str(path.relative_to(REPO_ROOT)), f"line {idx}: {line.strip()}", "warn"))
    return findings


def scan_markdown_links(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)#][^)]+)\)")
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in link_pattern.finditer(text):
            target = match.group(1).strip()
            if "://" in target or target.startswith("mailto:"):
                continue
            target_path = (path.parent / target.split(":", 1)[0]).resolve()
            try:
                target_path.relative_to(REPO_ROOT)
            except ValueError:
                continue
            if not target_path.exists():
                findings.append(Finding("stale_doc_link", str(path.relative_to(REPO_ROOT)), f"missing target: {target}", "warn"))
    return findings


def scan_dead_code_candidates(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    py_files = [path for path in files if path.suffix == ".py" and "tests" not in path.parts]
    all_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files if path.suffix in {".py", ".md"})
    for path in py_files:
        if path.name == "__init__.py":
            continue
        rel = str(path.relative_to(REPO_ROOT))
        module_name = rel[:-3].replace("/", ".")
        if module_name not in all_text and path.name not in {"main.py", "config.py"}:
            findings.append(Finding("dead_code_candidate", rel, "module path is not referenced by tracked Python/Markdown files"))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            findings.append(Finding("syntax_error", rel, str(exc), "error"))
            continue
        for node in tree.body:
            name = getattr(node, "name", "")
            if name.startswith("_"):
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                occurrences = all_text.count(name)
                if occurrences <= 1:
                    findings.append(Finding("unused_symbol_candidate", rel, f"{name} appears only in its definition"))
    return findings[:200]


def scan_generated_artifacts(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        rel = str(path.relative_to(REPO_ROOT))
        if rel.startswith(("frontend/dist/", "logs/runs/", "test-artifacts/")):
            findings.append(Finding("tracked_generated_artifact", rel, "generated/runtime artifact is tracked", "warn"))
    return findings


def build_report() -> dict[str, Any]:
    files = _tracked_files()
    findings = [
        *scan_skipped_tests(files),
        *scan_markdown_links(files),
        *scan_dead_code_candidates(files),
        *scan_generated_artifacts(files),
    ]
    by_kind: dict[str, int] = {}
    for finding in findings:
        by_kind[finding.kind] = by_kind.get(finding.kind, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tracked_file_count": len(files),
        "finding_count": len(findings),
        "by_kind": dict(sorted(by_kind.items())),
        "findings": [finding.to_dict() for finding in findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect real repo health for autopilot safety.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument("--output", type=Path, default=Path("logs/project_health_report.json"))
    args = parser.parse_args()

    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"tracked files: {report['tracked_file_count']}")
        print(f"findings: {report['finding_count']}")
        print(json.dumps(report["by_kind"], ensure_ascii=False, indent=2))
        print(f"report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
