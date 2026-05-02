from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGE_SAMPLE_DIRS: dict[str, str] = {
    "00-Chaos": "chaos",
    "01-Data": "data",
    "02-Information": "information",
    "03-Knowledge": "knowledge",
    "04-Insight": "insight",
    "05-Wisdom": "wisdom",
    "06-Impact": "impact",
    "07-Proposal": "proposal",
    "08-Entrepreneurship": "entrepreneurship",
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id(scenario: str, *, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H-%M-%SZ")
    safe_scenario = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in scenario).strip("_")
    return f"{stamp}_{safe_scenario or 'run'}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_manifest(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"Evidence source does not exist: {resolved}")
        stat = resolved.stat()
        records.append(
            {
                "path": str(resolved),
                "name": resolved.name,
                "size_bytes": stat.st_size,
                "sha256": sha256_file(resolved),
                "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )
    return records


def vault_counts(vault_path: Path) -> dict[str, int]:
    vault = vault_path.expanduser().resolve()
    counts: dict[str, int] = {}
    for stage_dir in STAGE_SAMPLE_DIRS:
        directory = vault / stage_dir
        counts[stage_dir] = len(list(directory.rglob("*.md"))) if directory.exists() else 0
    return counts


def graph_snapshot(graph_db_path: Path, *, limit: int = 200) -> dict[str, Any]:
    db_path = graph_db_path.expanduser().resolve()
    if not db_path.exists():
        return {
            "exists": False,
            "path": str(db_path),
            "node_counts": {},
            "edge_count": 0,
            "recent_nodes": [],
            "recent_edges": [],
        }

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        node_counts = {
            row["type"]: row["count"]
            for row in conn.execute("SELECT type, COUNT(*) AS count FROM nodes GROUP BY type").fetchall()
        }
        edge_count = int(conn.execute("SELECT COUNT(*) AS count FROM edges").fetchone()["count"])
        recent_nodes = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, type, label, source, created_at
                FROM nodes
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
        recent_edges = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, source_node_id, target_node_id, relation_type, weight, source, created_at
                FROM edges
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]

    return {
        "exists": True,
        "path": str(db_path),
        "node_counts": node_counts,
        "edge_count": edge_count,
        "recent_nodes": recent_nodes,
        "recent_edges": recent_edges,
    }


def business_reconciliation(vault_path: Path, graph_db_path: Path, result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reconcile proposal and entrepreneurship output across vault, graph, and run result."""
    counts = vault_counts(vault_path)
    graph = graph_snapshot(graph_db_path)
    graph_counts = graph.get("node_counts", {})
    status_counts: dict[str, int] = {}
    db_path = graph_db_path.expanduser().resolve()
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if "node_properties" in tables:
                rows = conn.execute(
                    """
                    SELECT json_extract(np.properties, '$.status') AS status, COUNT(*) AS count
                    FROM nodes n
                    LEFT JOIN node_properties np ON np.node_id = n.id
                    WHERE n.type IN ('reactor_proposal', 'residual_proposal')
                    GROUP BY status
                    """
                ).fetchall()
                status_counts = {str(row["status"] or "missing"): int(row["count"]) for row in rows}

    payload = result or {}
    vault_proposals = counts.get("07-Proposal", 0)
    vault_entrepreneurship = counts.get("08-Entrepreneurship", 0)
    graph_proposals = int(graph_counts.get("reactor_proposal", 0)) + int(graph_counts.get("residual_proposal", 0))
    evaluated_statuses = {
        "incubating",
        "rejected_business",
        "rejected_innovation",
        "needs_more_validation",
    }
    graph_evaluated = sum(count for status, count in status_counts.items() if status in evaluated_statuses)
    return {
        "vault_proposal_notes": vault_proposals,
        "vault_entrepreneurship_notes": vault_entrepreneurship,
        "graph_proposal_nodes": graph_proposals,
        "graph_proposal_status_counts": dict(sorted(status_counts.items())),
        "graph_evaluated_proposal_nodes": graph_evaluated,
        "run_reactor_proposals": payload.get("reactor_proposals"),
        "run_business_result": payload.get("business_result"),
        "proposal_limit": os.getenv("AILY_PROPOSAL_MAX_PER_SESSION", ""),
        "notes": [
            "08-Entrepreneurship can contain one session summary plus one note per evaluated proposal.",
            "Counts reconcile through documented filters: graph proposal nodes include Reactor/Residual nodes; vault notes include human-readable markdown artifacts.",
        ],
    }


def git_state(repo_root: Path) -> dict[str, Any]:
    def _run(args: list[str]) -> str:
        try:
            return subprocess.check_output(args, cwd=repo_root, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return ""

    status = _run(["git", "status", "--short"])
    return {
        "git_sha": _run(["git", "rev-parse", "HEAD"]),
        "branch": _run(["git", "branch", "--show-current"]),
        "dirty_worktree": bool(status),
        "status_short": status.splitlines(),
    }


def environment_snapshot() -> dict[str, Any]:
    return {
        "cwd": str(Path.cwd()),
        "python": os.sys.version,
        "env_flags": {
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER", ""),
            "AILY_DIKIWI_ENABLED": os.getenv("AILY_DIKIWI_ENABLED", ""),
            "AILY_INNOVATION_ENABLED": os.getenv("AILY_INNOVATION_ENABLED", ""),
            "AILY_ENTREPRENEUR_ENABLED": os.getenv("AILY_ENTREPRENEUR_ENABLED", ""),
        },
    }


@dataclass
class EvidenceRun:
    root_dir: Path
    scenario: str
    vault_path: Path
    graph_db_path: Path
    source_paths: list[Path] = field(default_factory=list)
    source_selector: str = "explicit"
    source_seed: int | None = None
    command: list[str] = field(default_factory=lambda: list(os.sys.argv))
    mocked: bool = False
    fake_components: list[str] = field(default_factory=list)
    real_files: bool = True
    real_graph_db: bool = True
    real_vault: bool = True
    real_llm: bool = True
    run_id: str | None = None

    def __post_init__(self) -> None:
        self.root_dir = self.root_dir.expanduser().resolve()
        self.vault_path = self.vault_path.expanduser().resolve()
        self.graph_db_path = self.graph_db_path.expanduser().resolve()
        self._validate_acceptance_contract()
        self.run_id = self.run_id or make_run_id(self.scenario)
        self.path = self.root_dir / self.run_id
        self.started_at = utc_timestamp()
        self.path.mkdir(parents=True, exist_ok=True)
        for sample_dir in STAGE_SAMPLE_DIRS.values():
            (self.path / "samples" / sample_dir).mkdir(parents=True, exist_ok=True)
        self.write_text("command.txt", " ".join(self.command))
        self.write_json("environment.json", environment_snapshot())

    def _validate_acceptance_contract(self) -> None:
        """Prevent fake runs from being labeled as real acceptance evidence."""
        if self.mocked:
            return

        missing_real_paths = [
            name
            for name, enabled in {
                "real_files": self.real_files,
                "real_graph_db": self.real_graph_db,
                "real_vault": self.real_vault,
                "real_llm": self.real_llm,
            }.items()
            if not enabled
        ]
        if missing_real_paths or self.fake_components:
            details = {
                "missing_real_paths": missing_real_paths,
                "fake_components": self.fake_components,
            }
            raise ValueError(
                "EvidenceRun cannot claim mocked=False with non-real acceptance components: "
                f"{details}"
            )

    def write_json(self, relative_path: str, payload: Any) -> Path:
        target = self.path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return target

    def write_text(self, relative_path: str, text: str) -> Path:
        target = self.path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def capture_before(self) -> None:
        self.write_json("vault-counts-before.json", vault_counts(self.vault_path))
        self.write_json("graph-before.json", graph_snapshot(self.graph_db_path))
        self.write_json("source-manifest.json", source_manifest(self.source_paths))

    def capture_after(self) -> dict[str, Any]:
        vault_after = vault_counts(self.vault_path)
        graph_after = graph_snapshot(self.graph_db_path)
        self.write_json("vault-counts-after.json", vault_after)
        self.write_json("graph-after.json", graph_after)
        self.copy_vault_samples()
        return {"vault_counts": vault_after, "graph": graph_after}

    def copy_vault_samples(self, *, limit_per_stage: int = 3) -> dict[str, list[str]]:
        copied: dict[str, list[str]] = {}
        for stage_dir, sample_dir in STAGE_SAMPLE_DIRS.items():
            source_dir = self.vault_path / stage_dir
            copied[stage_dir] = []
            if not source_dir.exists():
                continue
            files = sorted(source_dir.rglob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
            for source in files[:limit_per_stage]:
                target = self.path / "samples" / sample_dir / source.name
                shutil.copy2(source, target)
                copied[stage_dir].append(str(target))
        self.write_json("samples/index.json", copied)
        return copied

    def finalize(
        self,
        *,
        exit_code: int,
        result: dict[str, Any] | None = None,
        failures: list[dict[str, Any]] | None = None,
        llm_log_file: str | None = None,
        ui_events: list[dict[str, Any]] | None = None,
        stderr_text: str = "",
        repo_root: Path | None = None,
    ) -> dict[str, Any]:
        after = self.capture_after()
        failures = failures or []
        result = result or {}
        reconciliation = business_reconciliation(self.vault_path, self.graph_db_path, result)
        self.write_json("proposal-review-reconciliation.json", reconciliation)
        self.write_json("failures.json", failures)
        if llm_log_file:
            llm_path = Path(llm_log_file)
            if llm_path.exists():
                shutil.copy2(llm_path, self.path / "llm-calls.jsonl")
        else:
            self.write_text("llm-calls.jsonl", "")
        ui_events = ui_events or []
        self.write_text(
            "ui-events.jsonl",
            "".join(json.dumps(event, ensure_ascii=False, default=str) + "\n" for event in ui_events),
        )
        self.write_json("ui-event-summary.json", summarize_ui_events(ui_events))
        self.write_text("stdout.log", "")
        self.write_text("stderr.log", stderr_text)

        git = git_state(repo_root or Path.cwd())
        manifest = {
            "run_id": self.run_id,
            **git,
            "scenario": self.scenario,
            "source_count": len(self.source_paths),
            "source_selector": self.source_selector,
            "source_seed": self.source_seed,
            "vault_path": str(self.vault_path),
            "graph_db_path": str(self.graph_db_path),
            "started_at": self.started_at,
            "completed_at": utc_timestamp(),
            "exit_code": exit_code,
            "acceptance": {
                "mocked": self.mocked,
                "fake_components": self.fake_components,
                "real_files": self.real_files,
                "real_graph_db": self.real_graph_db,
                "real_vault": self.real_vault,
                "real_llm": self.real_llm,
            },
            "vault_counts_after": after["vault_counts"],
            "graph_node_counts_after": after["graph"].get("node_counts", {}),
            "graph_edge_count_after": after["graph"].get("edge_count", 0),
            "business_reconciliation": reconciliation,
            "result": result,
            "failures_count": len(failures),
            "ui_event_count": len(ui_events),
        }
        self.write_json("manifest.json", manifest)
        return manifest


def summarize_ui_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_type = Counter(str(event.get("type", "")) for event in events)
    stage_events = [
        event
        for event in events
        if event.get("type") in {"stage_started", "stage_completed", "stage_failed"}
    ]
    stages = Counter(str(event.get("stage", "")) for event in stage_events)
    return {
        "total": len(events),
        "by_type": dict(sorted(by_type.items())),
        "stages": dict(sorted(stages.items())),
        "last_event": events[-1] if events else None,
    }
