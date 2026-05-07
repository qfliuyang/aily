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
BASELINE_PATH = REPO_ROOT / "tests" / "quality_baseline.json"
ROOT_PYTEST_INI = REPO_ROOT / "pytest.ini"
REQUIRED_ROOT_MARKERS = {
    "unit",
    "contract",
    "integration",
    "e2e",
    "real_service",
    "acceptance",
    "security",
    "slow",
}
LANE_MARKERS = REQUIRED_ROOT_MARKERS - {"slow"}


@dataclass
class Finding:
    kind: str
    path: str
    detail: str
    severity: str = "info"

    def stable_key(self) -> str:
        return f"{self.kind}|{self.path}|{self.detail}"

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "path": self.path,
            "detail": self.detail,
            "severity": self.severity,
            "key": self.stable_key(),
        }


def _tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        text=True,
    )
    return [path for line in output.splitlines() if line.strip() for path in [REPO_ROOT / line.strip()] if path.exists()]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _test_files(files: list[Path]) -> list[Path]:
    return [
        path
        for path in files
        if path.name.startswith("test_") and path.suffix == ".py" and "__pycache__" not in path.parts
    ]


def _parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError:
        return None


def scan_pytest_contract(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    if not ROOT_PYTEST_INI.exists():
        return [Finding("missing_pytest_config", "pytest.ini", "root pytest.ini is missing", "error")]
    text = ROOT_PYTEST_INI.read_text(encoding="utf-8", errors="replace")
    if "--strict-markers" not in text:
        findings.append(Finding("pytest_contract", "pytest.ini", "root pytest config must enable --strict-markers", "error"))
    missing_markers = sorted(marker for marker in REQUIRED_ROOT_MARKERS if f"{marker}:" not in text)
    if missing_markers:
        findings.append(
            Finding(
                "pytest_contract",
                "pytest.ini",
                f"root pytest config missing production test markers: {', '.join(missing_markers)}",
                "error",
            )
        )
    return findings


def scan_nested_pytest_configs(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in files:
        if path.name != "pytest.ini" or path == ROOT_PYTEST_INI:
            continue
        if "tests" in path.parts:
            findings.append(
                Finding(
                    "nested_pytest_config",
                    _relative(path),
                    "nested pytest.ini can change rootdir and bypass parent conftest enforcement; use root pytest.ini",
                    "error",
                )
            )
    return findings


def scan_skipped_tests(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in _test_files(files):
        text = path.read_text(encoding="utf-8", errors="replace")
        for idx, line in enumerate(text.splitlines(), start=1):
            if "@pytest.mark.skip" in line or "pytest.skip(" in line:
                findings.append(Finding("skipped_test", _relative(path), f"line {idx}: {line.strip()}", "warn"))
    return findings


def scan_test_assertion_strength(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in _test_files(files):
        tree = _parse(path)
        if tree is None:
            findings.append(Finding("syntax_error", _relative(path), "could not parse test file", "error"))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            has_assert = any(isinstance(child, ast.Assert) for child in ast.walk(node))
            has_pytest_raises = any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "raises"
                for child in ast.walk(node)
            )
            if not (has_assert or has_pytest_raises):
                findings.append(
                    Finding(
                        "test_without_assertion",
                        _relative(path),
                        f"line {node.lineno}: {node.name} has no explicit assert or pytest.raises",
                        "warn",
                    )
                )
    return findings


def _marker_names(expr: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(expr, ast.Attribute):
        names.add(expr.attr)
        names.update(_marker_names(expr.value))
    elif isinstance(expr, ast.Call):
        names.update(_marker_names(expr.func))
    elif isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        for element in expr.elts:
            names.update(_marker_names(element))
    return names


def _decorator_lane_markers(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> set[str]:
    markers: set[str] = set()
    for decorator in node.decorator_list:
        markers.update(_marker_names(decorator) & LANE_MARKERS)
    return markers


def _module_lane_markers(tree: ast.AST) -> set[str]:
    markers: set[str] = set()
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets):
            continue
        markers.update(_marker_names(node.value) & LANE_MARKERS)
    return markers


def scan_unmarked_test_lanes(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in _test_files(files):
        tree = _parse(path)
        if tree is None:
            continue
        module_markers = _module_lane_markers(tree)
        class_markers: dict[ast.AST, set[str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_markers[node] = _decorator_lane_markers(node)
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                        markers = module_markers | class_markers[node] | _decorator_lane_markers(child)
                        if not markers:
                            findings.append(
                                Finding(
                                    "unmarked_test_lane",
                                    _relative(path),
                                    f"line {child.lineno}: {node.name}.{child.name} has no production test lane marker",
                                    "warn",
                                )
                            )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                # Top-level test functions have Module as parent, but ast has no parent links.
                if any(isinstance(parent, ast.ClassDef) and node in parent.body for parent in ast.walk(tree)):
                    continue
                markers = module_markers | _decorator_lane_markers(node)
                if not markers:
                    findings.append(
                        Finding(
                            "unmarked_test_lane",
                            _relative(path),
                            f"line {node.lineno}: {node.name} has no production test lane marker",
                            "warn",
                        )
                    )
    return findings


def scan_mock_usage(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in _test_files(files):
        tree = _parse(path)
        if tree is None:
            continue
        indicators: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "unittest.mock":
                indicators.add("unittest.mock")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "unittest.mock":
                        indicators.add("unittest.mock")
            elif isinstance(node, ast.Name) and node.id in {"MagicMock", "AsyncMock", "patch", "monkeypatch"}:
                indicators.add(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in {"MagicMock", "AsyncMock", "patch"}:
                indicators.add(node.attr)
        if indicators:
            findings.append(
                Finding(
                    "mocked_test_file",
                    _relative(path),
                    "uses mock/patch tooling: " + ", ".join(sorted(indicators)),
                    "info",
                )
            )
    return findings


def _has_fixture_decorator(node: ast.FunctionDef, *, autouse: bool | None = None) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            names = _marker_names(decorator.func)
            if "fixture" not in names:
                continue
            if autouse is None:
                return True
            for keyword in decorator.keywords:
                if keyword.arg == "autouse" and isinstance(keyword.value, ast.Constant):
                    return bool(keyword.value.value) is autouse
        else:
            names = _marker_names(decorator)
            if "fixture" in names and autouse is None:
                return True
    return False


def _calls_attr(node: ast.AST, attr: str) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == attr
        for child in ast.walk(node)
    )


def _contains_string(node: ast.AST, value: str) -> bool:
    return any(isinstance(child, ast.Constant) and child.value == value for child in ast.walk(node))


def scan_acceptance_boundaries(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    support = REPO_ROOT / "tests" / "support" / "acceptance.py"
    root_conftest = REPO_ROOT / "tests" / "conftest.py"
    e2e_conftest = REPO_ROOT / "tests" / "e2e" / "conftest.py"

    support_tree = _parse(support) if support.exists() else None
    if support_tree is None:
        findings.append(
            Finding(
                "acceptance_boundary_missing",
                _relative(support),
                "tests/support/acceptance.py must define the acceptance boundary manifest contract",
                "error",
            )
        )
    else:
        classes = {node.name: node for node in ast.walk(support_tree) if isinstance(node, ast.ClassDef)}
        manifest = classes.get("AcceptanceBoundaryManifest")
        required_fields = {"real_llm", "real_graph_db", "real_queue_worker", "real_writer_api", "real_http", "fake_components"}
        annotated = {
            node.target.id
            for node in (manifest.body if manifest else [])
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        if manifest is None or not required_fields.issubset(annotated):
            findings.append(
                Finding(
                    "acceptance_boundary_missing",
                    _relative(support),
                    "AcceptanceBoundaryManifest must declare all real/fake production boundaries",
                    "error",
                )
            )

    root_tree = _parse(root_conftest) if root_conftest.exists() else None
    autouse_guard: ast.FunctionDef | None = None
    if root_tree is not None:
        for node in ast.walk(root_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "enforce_acceptance_boundary_manifest":
                autouse_guard = node
                break
    if (
        autouse_guard is None
        or not _has_fixture_decorator(autouse_guard, autouse=True)
        or not _contains_string(autouse_guard, "acceptance")
        or not _calls_attr(autouse_guard, "get_closest_marker")
        or not _calls_attr(autouse_guard, "getfixturevalue")
    ):
        findings.append(
            Finding(
                "acceptance_boundary_missing",
                _relative(root_conftest),
                "global autouse fixture must enforce acceptance_boundary_manifest for every acceptance-marked test",
                "error",
            )
        )

    e2e_tree = _parse(e2e_conftest) if e2e_conftest.exists() else None
    has_e2e_manifest_fixture = False
    if e2e_tree is not None:
        for node in ast.walk(e2e_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "acceptance_boundary_manifest" and _has_fixture_decorator(node):
                has_e2e_manifest_fixture = True
                break
    if not has_e2e_manifest_fixture:
        findings.append(
            Finding(
                "acceptance_boundary_missing",
                _relative(e2e_conftest),
                "e2e tests must declare their local production-boundary substitutions through acceptance_boundary_manifest",
                "error",
            )
        )
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
                findings.append(Finding("stale_doc_link", _relative(path), f"missing target: {target}", "warn"))
    return findings


def scan_dead_code_candidates(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    py_files = [path for path in files if path.suffix == ".py" and "tests" not in path.parts]
    all_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files if path.suffix in {".py", ".md"})
    for path in py_files:
        if path.name == "__init__.py":
            continue
        rel = _relative(path)
        module_name = rel[:-3].replace("/", ".")
        if module_name not in all_text and path.name not in {"main.py", "config.py"}:
            findings.append(Finding("dead_code_candidate", rel, "module path is not referenced by tracked Python/Markdown files"))
        tree = _parse(path)
        if tree is None:
            findings.append(Finding("syntax_error", rel, "could not parse Python file", "error"))
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
        rel = _relative(path)
        if rel.startswith(("frontend/dist/", "logs/runs/", "test-artifacts/")):
            findings.append(Finding("tracked_generated_artifact", rel, "generated/runtime artifact is tracked", "warn"))
    return findings


def build_report() -> dict[str, Any]:
    files = _tracked_files()
    findings = [
        *scan_pytest_contract(files),
        *scan_nested_pytest_configs(files),
        *scan_skipped_tests(files),
        *scan_test_assertion_strength(files),
        *scan_unmarked_test_lanes(files),
        *scan_mock_usage(files),
        *scan_acceptance_boundaries(files),
        *scan_markdown_links(files),
        *scan_dead_code_candidates(files),
        *scan_generated_artifacts(files),
    ]
    by_kind: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for finding in findings:
        by_kind[finding.kind] = by_kind.get(finding.kind, 0) + 1
        by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tracked_file_count": len(files),
        "finding_count": len(findings),
        "by_kind": dict(sorted(by_kind.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "findings": [finding.to_dict() for finding in findings],
        "finding_keys": sorted(finding.stable_key() for finding in findings),
    }


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"by_kind": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def compare_to_baseline(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    baseline_counts = {str(k): int(v) for k, v in (baseline.get("by_kind") or {}).items()}
    current_counts = {str(k): int(v) for k, v in (report.get("by_kind") or {}).items()}
    for kind, current in sorted(current_counts.items()):
        allowed = baseline_counts.get(kind, 0)
        if current > allowed:
            failures.append(f"{kind}: current={current} exceeds baseline={allowed}")

    accepted_keys = set(str(key) for key in (baseline.get("accepted_findings") or []))
    if accepted_keys:
        current_findings = report.get("findings", [])
        current_keys = {str(finding.get("key")) for finding in current_findings}
        new_keys = sorted(current_keys - accepted_keys)
        if new_keys:
            preview = "; ".join(new_keys[:10])
            failures.append(f"new unbaselined findings: {len(new_keys)} ({preview})")

    for finding in report.get("findings", []):
        if finding.get("severity") == "error":
            failures.append(f"error finding: {finding.get('kind')} {finding.get('path')} {finding.get('detail')}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect real repo health for production-grade test design.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument("--output", type=Path, default=Path("logs/project_health_report.json"))
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--check", action="store_true", help="Fail when report exceeds baseline or has error findings")
    args = parser.parse_args()

    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    failures = compare_to_baseline(report, load_baseline(args.baseline)) if args.check else []
    if args.json:
        print(json.dumps({**report, "baseline_failures": failures}, ensure_ascii=False, indent=2))
    else:
        print(f"tracked files: {report['tracked_file_count']}")
        print(f"findings: {report['finding_count']}")
        print(json.dumps(report["by_kind"], ensure_ascii=False, indent=2))
        print(f"report: {args.output}")
        if failures:
            print("baseline failures:")
            for failure in failures:
                print(f"- {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
