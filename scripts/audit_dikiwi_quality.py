#!/usr/bin/env python3
"""Audit real DIKIWI evidence for minimum quality and completeness."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from statistics import mean
from typing import Any


STAGES = [
    "00-Chaos",
    "01-Data",
    "02-Information",
    "03-Knowledge",
    "04-Insight",
    "05-Wisdom",
    "06-Impact",
]


def _stage_files(vault: Path, stage: str) -> list[Path]:
    directory = vault / stage
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.md"))


def _note_metrics(files: list[Path]) -> dict[str, Any]:
    lengths: list[int] = []
    wikilinks = 0
    frontmatter = 0
    suspicious = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        lengths.append(len(text.strip()))
        wikilinks += text.count("[[")
        if text.startswith("---"):
            frontmatter += 1
        lowered = text.lower()
        if any(marker in lowered for marker in ["lorem ipsum", "mock", "fake component", "todo"]):
            suspicious += 1
    return {
        "count": len(files),
        "avg_chars": round(mean(lengths), 2) if lengths else 0,
        "min_chars": min(lengths) if lengths else 0,
        "wikilinks": wikilinks,
        "frontmatter_notes": frontmatter,
        "suspicious_marker_notes": suspicious,
    }


def _graph_metrics(graph_db: Path) -> dict[str, Any]:
    if not graph_db.exists():
        return {"exists": False, "node_counts": {}, "edge_count": 0, "relation_counts": {}}
    with sqlite3.connect(graph_db) as conn:
        conn.row_factory = sqlite3.Row
        node_counts = {
            str(row["type"]): int(row["count"])
            for row in conn.execute("SELECT type, COUNT(*) AS count FROM nodes GROUP BY type").fetchall()
        }
        edge_count = int(conn.execute("SELECT COUNT(*) AS count FROM edges").fetchone()["count"])
        relation_counts = {
            str(row["relation_type"]): int(row["count"])
            for row in conn.execute(
                "SELECT relation_type, COUNT(*) AS count FROM edges GROUP BY relation_type"
            ).fetchall()
        }
        generic_information_nodes = int(
            conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM nodes
                WHERE type = 'information'
                  AND lower(replace(replace(label, '_', ' '), '-', ' ')) GLOB 'page [0-9]*'
                """
            ).fetchone()["count"]
        )
    tag_edges = int(relation_counts.get("has_tag", 0))
    return {
        "exists": True,
        "node_counts": node_counts,
        "edge_count": edge_count,
        "relation_counts": relation_counts,
        "tag_edge_ratio": round(tag_edges / edge_count, 4) if edge_count else 0,
        "generic_information_nodes": generic_information_nodes,
    }


def _llm_metrics(llm_log: Path | None) -> dict[str, Any]:
    if not llm_log or not llm_log.exists():
        return {
            "exists": False,
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "models": [],
            "provider_verified_successes": 0,
            "unverified_successes": 0,
            "unverified_samples": [],
        }
    calls = 0
    successes = 0
    failures = 0
    provider_verified_successes = 0
    models: set[str] = set()
    unverified_samples: list[dict[str, Any]] = []
    for line in llm_log.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        calls += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            failures += 1
            continue
        if record.get("success") is True:
            successes += 1
            provider_metadata = record.get("provider_metadata") if isinstance(record.get("provider_metadata"), dict) else {}
            provider = record.get("provider") or provider_metadata.get("provider")
            base_url = record.get("base_url") or provider_metadata.get("base_url")
            status_code = record.get("status_code") or provider_metadata.get("status_code")
            duration_ms = record.get("duration_ms") or provider_metadata.get("duration_ms")
            provider_response_id = record.get("provider_response_id") or provider_metadata.get("provider_response_id")
            provider_request_id = record.get("provider_request_id") or provider_metadata.get("provider_request_id")
            if provider and base_url and status_code and duration_ms and (provider_response_id or provider_request_id):
                provider_verified_successes += 1
            elif len(unverified_samples) < 5:
                unverified_samples.append(
                    {
                        "line": calls,
                        "model": record.get("model"),
                        "has_provider": bool(provider),
                        "has_base_url": bool(base_url),
                        "status_code": status_code,
                        "has_duration_ms": bool(duration_ms),
                        "has_provider_response_id": bool(provider_response_id),
                        "has_provider_request_id": bool(provider_request_id),
                    }
                )
        else:
            failures += 1
        if record.get("model"):
            models.add(str(record["model"]))
    return {
        "exists": True,
        "calls": calls,
        "successes": successes,
        "failures": failures,
        "models": sorted(models),
        "provider_verified_successes": provider_verified_successes,
        "unverified_successes": successes - provider_verified_successes,
        "unverified_samples": unverified_samples,
    }


def _unresolved_wikilink_metrics(vault: Path) -> dict[str, Any]:
    note_stems = {path.stem for path in vault.rglob("*.md")}
    total = 0
    unresolved: list[str] = []
    for path in vault.rglob("*.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for target in re.findall(r"\[\[([^\]|#]+)", text):
            total += 1
            cleaned = target.strip()
            if cleaned and cleaned not in note_stems:
                unresolved.append(cleaned)
    return {
        "total_wikilinks": total,
        "unresolved_count": len(unresolved),
        "unresolved_samples": sorted(set(unresolved))[:25],
    }


def audit(
    vault: Path,
    graph_db: Path,
    llm_log: Path | None,
    output: Path,
    *,
    require_business: bool = False,
    strict_graph: bool = False,
    max_unresolved_wikilinks: int | None = None,
) -> int:
    stage_metrics = {stage: _note_metrics(_stage_files(vault, stage)) for stage in STAGES}
    stage_metrics["07-Proposal"] = _note_metrics(_stage_files(vault, "07-Proposal"))
    stage_metrics["08-Entrepreneurship"] = _note_metrics(_stage_files(vault, "08-Entrepreneurship"))
    graph = _graph_metrics(graph_db)
    llm = _llm_metrics(llm_log)
    wikilinks = _unresolved_wikilink_metrics(vault)
    failures: list[str] = []
    warnings: list[str] = []

    for stage in STAGES:
        if stage_metrics[stage]["count"] <= 0:
            failures.append(f"{stage} has no markdown notes")

    if stage_metrics["01-Data"]["avg_chars"] < 120:
        failures.append("01-Data average note length is too thin")
    if stage_metrics["02-Information"]["avg_chars"] < 150:
        failures.append("02-Information average note length is too thin")
    for stage in ["03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]:
        if stage_metrics[stage]["avg_chars"] < 250:
            failures.append(f"{stage} average note length is too thin")
        if stage_metrics[stage]["wikilinks"] <= 0:
            failures.append(f"{stage} has no wikilinks")

    if any(metrics["suspicious_marker_notes"] for metrics in stage_metrics.values()):
        failures.append("Suspicious mock/fake/TODO markers found in generated notes")
    if not graph["exists"]:
        failures.append("Graph DB is missing")
    if int(graph.get("edge_count", 0)) <= 0:
        failures.append("Graph has no edges")
    if llm["calls"] <= 0 or llm["successes"] <= 0:
        failures.append("No successful real LLM calls were recorded")
    elif llm["provider_verified_successes"] != llm["successes"]:
        failures.append(
            "LLM trace has successful calls without provider-verifiable receipt metadata "
            f"({llm['provider_verified_successes']}/{llm['successes']} verified)"
        )
    if llm["failures"] > 0:
        warnings.append(
            f"LLM trace contains {llm['failures']} failed attempt(s); accepted successful calls remain provider-verified"
        )
    if require_business:
        if stage_metrics["07-Proposal"]["count"] <= 0:
            failures.append("07-Proposal has no markdown notes")
        if stage_metrics["08-Entrepreneurship"]["count"] <= 0:
            failures.append("08-Entrepreneurship has no markdown notes")
    if strict_graph:
        if graph.get("tag_edge_ratio", 0) > 0.5:
            failures.append(f"Graph is tag-edge dominated: tag_edge_ratio={graph.get('tag_edge_ratio')}")
        if graph.get("generic_information_nodes", 0) > 0:
            failures.append(f"Graph contains generic page information nodes: {graph.get('generic_information_nodes')}")
    if max_unresolved_wikilinks is not None and wikilinks["unresolved_count"] > max_unresolved_wikilinks:
        failures.append(
            f"Too many unresolved wikilinks: {wikilinks['unresolved_count']} > {max_unresolved_wikilinks}"
        )

    report = {
        "vault": str(vault),
        "graph_db": str(graph_db),
        "llm_log": str(llm_log) if llm_log else "",
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "stage_metrics": stage_metrics,
        "graph": graph,
        "llm": llm,
        "wikilinks": wikilinks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit generated DIKIWI vault evidence.")
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--graph-db", required=True, type=Path)
    parser.add_argument("--llm-log", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-business", action="store_true")
    parser.add_argument("--strict-graph", action="store_true")
    parser.add_argument("--max-unresolved-wikilinks", type=int)
    args = parser.parse_args()
    return audit(
        args.vault,
        args.graph_db,
        args.llm_log,
        args.output,
        require_business=args.require_business,
        strict_graph=args.strict_graph,
        max_unresolved_wikilinks=args.max_unresolved_wikilinks,
    )


if __name__ == "__main__":
    raise SystemExit(main())
