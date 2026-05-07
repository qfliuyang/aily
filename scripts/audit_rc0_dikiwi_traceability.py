#!/usr/bin/env python3
"""Audit RC0 DIKIWI stage traceability evidence.

The gate verifies that successful real runs reached all six DIKIWI stages with
persisted vault artifacts, real LLM trace evidence, and source traceability on
generated notes. It can also validate a target-specific sample ledger for the
required URL/text/PDF/malformed/duplicate sample mix.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIRED_STAGE_NAMES = ["DATA", "INFORMATION", "KNOWLEDGE", "INSIGHT", "WISDOM", "IMPACT"]
REQUIRED_STAGE_DIRS = ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]
REQUIRED_SAMPLE_TYPES = {"url", "text", "pdf", "malformed", "duplicate"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    body = text[end + 4 :]
    parsed: dict[str, Any] = {}
    current_key = ""
    for line in raw.splitlines():
        if line.startswith("  - ") and current_key:
            parsed.setdefault(current_key, []).append(line[4:].strip().strip('"'))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        if value:
            parsed[current_key] = value.strip('"')
        else:
            parsed[current_key] = []
    return parsed, body


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
    calls = successes = failures = 0
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
            provider_response_id = record.get("provider_response_id") or provider_metadata.get("provider_response_id")
            provider_request_id = record.get("provider_request_id") or provider_metadata.get("provider_request_id")
            duration_ms = record.get("duration_ms") or provider_metadata.get("duration_ms")
            has_http_receipt = bool(provider and base_url and status_code and duration_ms)
            has_provider_receipt_id = bool(provider_response_id or provider_request_id)
            if has_http_receipt and has_provider_receipt_id:
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


def _stage_counts(vault: Path) -> dict[str, int]:
    return {stage: len(list((vault / stage).rglob("*.md"))) if (vault / stage).exists() else 0 for stage in REQUIRED_STAGE_DIRS}


def _has_source_trace(fm: dict[str, Any], body: str) -> bool:
    fields = ["source", "source_path", "source_paths", "source_url", "grounded_in", "from_knowledge", "based_on", "nodes"]
    if any(fm.get(field) for field in fields):
        return True
    lower = body.lower()
    return any(marker in lower for marker in ["## source", "## source trace", "## data basis", "## grounded in", "## based on"])


def _generated_notes(vault: Path) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for stage in REQUIRED_STAGE_DIRS:
        for path in sorted((vault / stage).rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            fm, body = _parse_frontmatter(text)
            notes.append(
                {
                    "path": str(path.relative_to(vault)),
                    "stage": stage,
                    "dikiwi_id": fm.get("dikiwi_id", ""),
                    "has_source_trace": _has_source_trace(fm, body),
                    "has_timestamp": bool(fm.get("date_created") or fm.get("created_at") or fm.get("timestamp")),
                    "has_stage_metadata": bool(fm.get("type") or fm.get("dikiwi_level") or fm.get("dikiwi_stage")),
                }
            )
    return notes


def _pipeline_stage_summaries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for item in manifest.get("result", {}).get("results", []):
        bridge = item.get("bridge_result", {}) if isinstance(item, dict) else {}
        summaries.append(
            {
                "source": item.get("pdf") or bridge.get("source_path") or bridge.get("drop_id", ""),
                "pipeline_id": bridge.get("pipeline_id", ""),
                "final_stage": bridge.get("stage", ""),
                "error": bridge.get("error", ""),
                "stage_results": bridge.get("stage_results", []),
            }
        )
    return summaries


def _audit_sample_ledger(path: Path | None) -> tuple[dict[str, Any], list[str]]:
    if path is None:
        return {"exists": False, "samples": []}, ["Sample ledger is required for RC0 traceability closure"]
    if not path.exists():
        return {"exists": False, "samples": []}, [f"Sample ledger missing: {path}"]
    payload = _load_json(path)
    samples = list(payload.get("samples", []))
    failures: list[str] = []
    if len(samples) < 10:
        failures.append(f"Sample ledger has {len(samples)} samples; need at least 10")
    sample_types = {str(sample.get("sample_type") or sample.get("type") or "") for sample in samples}
    missing_types = sorted(REQUIRED_SAMPLE_TYPES - sample_types)
    if missing_types:
        failures.append(f"Sample ledger missing required sample types: {missing_types}")
    for sample in samples:
        if sample.get("manual_state_mutation"):
            failures.append(f"Sample {sample.get('id')} declares manual state mutation")
        if sample.get("mocked"):
            failures.append(f"Sample {sample.get('id')} declares mocked evidence")
        status = str(sample.get("status") or "")
        if sample.get("successful") and status not in {"queued", "completed", "duplicate"}:
            failures.append(f"Successful sample {sample.get('id')} has non-terminal status {status!r}")
        if str(sample.get("sample_type")) == "malformed" and status not in {"failed", "rejected", "terminal_failure"}:
            failures.append(f"Malformed sample {sample.get('id')} did not reach visible failure/rejection")
    return {"exists": True, **payload}, failures


def audit(manifest_path: Path, vault: Path, output: Path, *, llm_log: Path | None, sample_ledger: Path | None) -> int:
    manifest = _load_json(manifest_path)
    failures: list[str] = []
    warnings: list[str] = []

    acceptance = manifest.get("acceptance", {})
    if acceptance.get("mocked") is not False:
        failures.append("Manifest does not declare mocked=false")
    for key in ["real_files", "real_graph_db", "real_vault", "real_llm"]:
        if acceptance.get(key) is not True:
            failures.append(f"Manifest acceptance.{key} is not true")

    pipelines = _pipeline_stage_summaries(manifest)
    if not pipelines:
        failures.append("Manifest contains no processed DIKIWI pipeline results")
    for pipe in pipelines:
        if pipe.get("error"):
            failures.append(f"Pipeline {pipe.get('pipeline_id')} has error: {pipe.get('error')}")
        if pipe.get("final_stage") != "IMPACT":
            failures.append(f"Pipeline {pipe.get('pipeline_id')} final stage is {pipe.get('final_stage')!r}, expected IMPACT")
        stage_results = pipe.get("stage_results") or []
        if stage_results:
            by_stage = {str(item.get("stage")): item for item in stage_results}
            for stage in REQUIRED_STAGE_NAMES:
                item = by_stage.get(stage)
                if not item:
                    failures.append(f"Pipeline {pipe.get('pipeline_id')} missing stage result {stage}")
                elif item.get("success") is not True:
                    failures.append(f"Pipeline {pipe.get('pipeline_id')} stage {stage} did not succeed")
                elif int(item.get("items_output") or 0) <= 0 and stage != "WISDOM":
                    failures.append(f"Pipeline {pipe.get('pipeline_id')} stage {stage} has no output count")
        else:
            failures.append(f"Pipeline {pipe.get('pipeline_id')} lacks per-stage result summary")

    counts = _stage_counts(vault)
    for stage, count in counts.items():
        if count <= 0:
            failures.append(f"Vault has no persisted notes for {stage}")

    notes = _generated_notes(vault)
    missing_trace = [note for note in notes if not note["has_source_trace"]]
    missing_timestamp = [note for note in notes if not note["has_timestamp"]]
    missing_stage_metadata = [note for note in notes if not note["has_stage_metadata"]]
    if missing_trace:
        failures.append(f"{len(missing_trace)} generated notes lack source traceability")
    if missing_timestamp:
        failures.append(f"{len(missing_timestamp)} generated notes lack timestamp metadata")
    if missing_stage_metadata:
        failures.append(f"{len(missing_stage_metadata)} generated notes lack DIKIWI stage/type metadata")

    llm = _llm_metrics(llm_log)
    if not llm["exists"] or llm["successes"] <= 0:
        failures.append("No successful real LLM trace was recorded")
    elif llm["provider_verified_successes"] != llm["successes"]:
        failures.append(
            "LLM trace has successful calls without provider-verifiable receipt metadata "
            f"({llm['provider_verified_successes']}/{llm['successes']} verified)"
        )
    if llm["failures"] > 0:
        warnings.append(
            f"LLM trace contains {llm['failures']} failed attempt(s); accepted successful calls remain provider-verified"
        )

    sample_payload, sample_failures = _audit_sample_ledger(sample_ledger)
    failures.extend(sample_failures)

    report = {
        "manifest": str(manifest_path),
        "vault": str(vault),
        "llm_log": str(llm_log) if llm_log else "",
        "sample_ledger": str(sample_ledger) if sample_ledger else "",
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "stage_counts": counts,
        "pipelines": pipelines,
        "notes_summary": {
            "generated_notes": len(notes),
            "missing_source_traceability": len(missing_trace),
            "missing_timestamp": len(missing_timestamp),
            "missing_stage_metadata": len(missing_stage_metadata),
            "missing_trace_samples": missing_trace[:20],
        },
        "llm": llm,
        "sample_ledger_summary": {
            "exists": sample_payload.get("exists"),
            "sample_count": len(sample_payload.get("samples", [])),
            "sample_types": sorted({str(sample.get("sample_type") or sample.get("type") or "") for sample in sample_payload.get("samples", [])}),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit RC0 DIKIWI stage traceability evidence.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--llm-log", type=Path)
    parser.add_argument("--sample-ledger", type=Path)
    args = parser.parse_args()
    return audit(args.manifest, args.vault, args.output, llm_log=args.llm_log, sample_ledger=args.sample_ledger)


if __name__ == "__main__":
    raise SystemExit(main())
