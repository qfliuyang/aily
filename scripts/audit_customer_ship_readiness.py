#!/usr/bin/env python3
"""Audit whether Aily has evidence for customer-shipping readiness.

This is intentionally stricter than the RC0 private-second-brain gate. It does
not run product scenarios itself; it inspects recorded evidence and fails closed
when evidence is stale, split across incompatible runs, dirty, or scoped to a
control plane instead of customer product behavior.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
LOG_ROOT = ROOT / "logs" / "runs"
STAGES = ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]


@dataclass(frozen=True)
class Criterion:
    id: str
    deliverable: str
    required: str
    passed: bool
    evidence: list[str]
    blockers: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "deliverable": self.deliverable,
            "required": self.required,
            "passed": self.passed,
            "evidence": self.evidence,
            "blockers": self.blockers,
        }


def _git_sha(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    ).stdout.strip()


def _dirty_worktree(root: Path) -> bool:
    return bool(
        subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        ).stdout.strip()
    )


def _load_manifests(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    manifests: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((root / "logs" / "runs").glob("*/manifest.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        manifests.append((path, data))
    return manifests


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _is_current_clean_success(data: dict[str, Any], head_sha: str) -> bool:
    return (
        data.get("git_sha") == head_sha
        and data.get("dirty_worktree") is False
        and int(data.get("exit_code", 1)) == 0
    )


def _acceptance(data: dict[str, Any]) -> dict[str, Any]:
    value = data.get("acceptance")
    return value if isinstance(value, dict) else {}


def _latest_matching(
    manifests: list[tuple[Path, dict[str, Any]]],
    predicate,
) -> tuple[Path, dict[str, Any]] | None:
    matches = [(path, data) for path, data in manifests if predicate(data)]
    return matches[-1] if matches else None


def _latest_any(manifests: list[tuple[Path, dict[str, Any]]], predicate) -> tuple[Path, dict[str, Any]] | None:
    matches = [(path, data) for path, data in manifests if predicate(data)]
    return matches[-1] if matches else None


def _vault_counts(data: dict[str, Any]) -> dict[str, int]:
    raw = data.get("vault_counts_after") or data.get("vault_counts") or {}
    return raw if isinstance(raw, dict) else {}


def _full_dikiwi(data: dict[str, Any]) -> bool:
    counts = _vault_counts(data)
    return all(int(counts.get(stage, 0) or 0) > 0 for stage in STAGES)


def _provider_verified(data: dict[str, Any]) -> bool:
    acceptance = _acceptance(data)
    if acceptance.get("provider_verified_dikiwi") is True:
        return True
    receipts = data.get("llm_receipts") or data.get("llm_call_receipts") or {}
    if isinstance(receipts, dict):
        provider_successes = int(receipts.get("provider_verified_successes", 0) or 0)
        unverified_successes = int(receipts.get("unverified_successes", 1) or 0)
        return provider_successes > 0 and unverified_successes == 0
    return False


def audit(root: Path = ROOT, *, head_sha: str | None = None) -> dict[str, Any]:
    head = head_sha or _git_sha(root)
    manifests = _load_manifests(root)
    criteria: list[Criterion] = []

    docker = _latest_matching(
        manifests,
        lambda data: _is_current_clean_success(data, head)
        and _acceptance(data).get("real_docker") is True
        and _acceptance(data).get("real_browser") is True
        and _acceptance(data).get("real_fastapi") is True,
    )
    latest_docker = _latest_any(manifests, lambda data: _acceptance(data).get("real_docker") is True)
    criteria.append(
        Criterion(
            id="CSHIP-001",
            deliverable="Docker deployment",
            required="A clean current-HEAD Docker Compose evidence run with real Docker, FastAPI, browser, persisted vault, and graph DB.",
            passed=docker is not None,
            evidence=[_rel(root, docker[0])] if docker else ([_rel(root, latest_docker[0])] if latest_docker else []),
            blockers=[] if docker else ["No current clean Docker evidence covers the customer deployment boundary."],
        )
    )

    studio = _latest_matching(
        manifests,
        lambda data: _is_current_clean_success(data, head)
        and _acceptance(data).get("real_browser") is True
        and _acceptance(data).get("real_fastapi") is True
        and _acceptance(data).get("real_vault") is True
        and _acceptance(data).get("real_graph_db") is True
        and _acceptance(data).get("mocked") is False,
    )
    latest_studio = _latest_any(
        manifests,
        lambda data: str(data.get("scenario", "")).startswith("studio") and _acceptance(data).get("real_browser") is True,
    )
    criteria.append(
        Criterion(
            id="CSHIP-002",
            deliverable="Interactive web UI",
            required="A clean current-HEAD real-browser Studio run against FastAPI with real persisted backend state.",
            passed=studio is not None,
            evidence=[_rel(root, studio[0])] if studio else ([_rel(root, latest_studio[0])] if latest_studio else []),
            blockers=[] if studio else ["No current clean Studio evidence covers the interactive UI/backend boundary."],
        )
    )

    provider = _latest_matching(
        manifests,
        lambda data: _is_current_clean_success(data, head)
        and _acceptance(data).get("real_llm") is True
        and _acceptance(data).get("real_vault") is True
        and _acceptance(data).get("real_graph_db") is True
        and _full_dikiwi(data),
    )
    latest_provider = _latest_any(
        manifests,
        lambda data: _acceptance(data).get("real_llm") is True and _full_dikiwi(data),
    )
    criteria.append(
        Criterion(
            id="CSHIP-003",
            deliverable="Full-function DIKIWI second-brain pipeline",
            required="A clean current-HEAD provider-verified run that writes real 01-Data through 06-Impact notes, graph rows, and vault files.",
            passed=provider is not None,
            evidence=[_rel(root, provider[0])] if provider else ([_rel(root, latest_provider[0])] if latest_provider else []),
            blockers=[] if provider else ["Latest provider DIKIWI evidence is missing, stale, dirty, partial, or not tied to current HEAD."],
        )
    )

    combined = _latest_matching(
        manifests,
        lambda data: _is_current_clean_success(data, head)
        and _acceptance(data).get("real_docker") is True
        and _acceptance(data).get("real_browser") is True
        and _acceptance(data).get("real_llm") is True
        and _provider_verified(data)
        and _full_dikiwi(data),
    )
    latest_combined = _latest_any(
        manifests,
        lambda data: _acceptance(data).get("real_docker") is True and _acceptance(data).get("real_llm") is True,
    )
    criteria.append(
        Criterion(
            id="CSHIP-004",
            deliverable="No split-brain customer proof",
            required="One clean current-HEAD customer scenario must combine Docker + real browser + provider-verified real LLM + real DIKIWI outputs, not separate control-plane and backend-only proofs.",
            passed=combined is not None,
            evidence=[_rel(root, combined[0])] if combined else ([_rel(root, latest_combined[0])] if latest_combined else []),
            blockers=[] if combined else ["Customer acceptance is split across separate Docker/UI and provider runs; no single run proves the shipped customer path end to end."],
        )
    )

    runbook = root / "docs" / "CUSTOMER_SHIP_READINESS_AUDIT.md"
    runbook_text = runbook.read_text(encoding="utf-8") if runbook.exists() else ""
    required_phrases = [
        "Customer-ready status: Not achieved",
        "CSHIP-001",
        "CSHIP-002",
        "CSHIP-003",
        "CSHIP-004",
        "Blocking gaps",
        "Next verification checkpoint",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in runbook_text]
    criteria.append(
        Criterion(
            id="CSHIP-005",
            deliverable="Traceable customer-readiness contract",
            required="A durable audit document must state customer-ready status, map evidence to customer criteria, and list blocking gaps before any customer-ready claim.",
            passed=runbook.exists() and not missing,
            evidence=[_rel(root, runbook)] if runbook.exists() else [],
            blockers=[] if runbook.exists() and not missing else [f"Missing audit contract phrases: {missing}"],
        )
    )

    ready = all(criterion.passed for criterion in criteria)
    return {
        "audit": "aily_customer_ship_readiness",
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": head,
        "dirty_worktree": _dirty_worktree(root) if head_sha is None else None,
        "ready_to_ship_customers": ready,
        "criteria": [criterion.as_dict() for criterion in criteria],
        "blocking_gaps": [
            {"id": criterion.id, "blockers": criterion.blockers}
            for criterion in criteria
            if not criterion.passed
        ],
        "anti_cheat_note": (
            "This audit fails closed. RC0/private-control evidence does not prove customer shipping unless it is current, clean, real-boundary, and covers the named customer path."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Aily customer-shipping readiness evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a concise text summary.")
    parser.add_argument("--output", type=Path, help="Write the audit JSON to this path.")
    args = parser.parse_args()

    result = audit(ROOT)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "READY" if result["ready_to_ship_customers"] else "NOT READY"
        print(f"Aily customer ship readiness: {status}")
        for criterion in result["criteria"]:
            mark = "PASS" if criterion["passed"] else "BLOCKED"
            print(f"[{mark}] {criterion['id']} {criterion['deliverable']}")
            for evidence in criterion["evidence"]:
                print(f"  evidence: {evidence}")
            for blocker in criterion["blockers"]:
                print(f"  blocker: {blocker}")
    return 0 if result["ready_to_ship_customers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
