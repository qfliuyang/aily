#!/usr/bin/env python3
"""Audit RC0 DIKIWI note quality against the release contract.

This gate is intentionally deterministic. It does not claim semantic brilliance;
it enforces the non-negotiable production hygiene that lets generated notes serve
as a trustworthy second-brain substrate: readable titles, source traceability,
timestamps, DIKIWI metadata, tags, and resolvable graph-friendly links.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import mean
from typing import Any

GENERATED_STAGE_DIRS = [
    "01-Data",
    "02-Information",
    "03-Knowledge",
    "04-Insight",
    "05-Wisdom",
    "06-Impact",
]

UUIDISH_RE = re.compile(
    r"^(?:[0-9a-f]{8,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|"
    r"(?:data|information|knowledge|insight|wisdom|impact)[_-][0-9a-f]{6,})(?:$|[-_])",
    re.IGNORECASE,
)
GENERIC_TITLE_RE = re.compile(r"^(untitled|data chunk \d+|data point \d+|source data|action item)$", re.IGNORECASE)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")


@dataclass
class NoteQuality:
    path: str
    stage: str
    title: str
    score: float
    has_readable_title: bool
    has_source_reference: bool
    has_timestamp: bool
    has_dikiwi_metadata: bool
    has_tags: bool
    has_resolving_wikilink: bool
    has_useful_body: bool
    failures: list[str]


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
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            parsed.setdefault(current_key, []).append(line[4:].strip().strip('"'))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        if value == "":
            parsed[current_key] = []
        else:
            parsed[current_key] = value.strip('"')
    return parsed, body


def _title_from_text(path: Path, body: str, fm: dict[str, Any]) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return str(fm.get("title") or path.stem)


def _note_index(vault: Path) -> set[str]:
    aliases: set[str] = set()
    for path in vault.rglob("*.md"):
        aliases.add(path.stem)
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _ = _parse_frontmatter(text)
        for alias in fm.get("aliases", []) if isinstance(fm.get("aliases"), list) else []:
            aliases.add(str(alias))
        dikiwi_id = fm.get("dikiwi_id")
        if dikiwi_id:
            aliases.add(str(dikiwi_id))
    return aliases


def _has_source_reference(fm: dict[str, Any], body: str) -> bool:
    source_fields = [
        "source",
        "source_path",
        "source_paths",
        "source_url",
        "grounded_in",
        "from_knowledge",
        "based_on",
        "nodes",
    ]
    if any(fm.get(key) for key in source_fields):
        return True
    lowered = body.lower()
    return "## source" in lowered or "## grounded in" in lowered or "## based on" in lowered or "## data basis" in lowered


def _has_dikiwi_metadata(fm: dict[str, Any], stage: str) -> bool:
    return bool(fm.get("dikiwi_id")) and bool(
        fm.get("type") or fm.get("dikiwi_level") or fm.get("dikiwi_stage") or stage
    )


def _resolving_links(text: str, known_targets: set[str]) -> list[str]:
    resolved: list[str] = []
    for raw in WIKILINK_RE.findall(text):
        target = raw.strip().split("/", 1)[-1]
        if target in known_targets:
            resolved.append(target)
    return resolved


def _score_note(path: Path, vault: Path, known_targets: set[str]) -> NoteQuality:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _parse_frontmatter(text)
    stage = path.relative_to(vault).parts[0]
    title = _title_from_text(path, body, fm)
    body_words = re.findall(r"\w+", body)
    has_readable_title = bool(title) and not UUIDISH_RE.match(title) and not GENERIC_TITLE_RE.match(title.strip())
    has_source_reference = _has_source_reference(fm, body)
    has_timestamp = bool(fm.get("date_created") or fm.get("created_at") or fm.get("timestamp"))
    has_dikiwi_metadata = _has_dikiwi_metadata(fm, stage)
    tags = fm.get("tags")
    has_tags = bool(tags) if isinstance(tags, list) else bool(str(tags or "").strip())
    has_resolving_wikilink = bool(_resolving_links(text, known_targets))
    has_useful_body = len(body_words) >= 35 and len(body.strip()) >= 220

    checks = {
        "readable_title": has_readable_title,
        "source_reference": has_source_reference,
        "timestamp": has_timestamp,
        "dikiwi_metadata": has_dikiwi_metadata,
        "tags": has_tags,
        "resolving_wikilink": has_resolving_wikilink,
        "useful_body": has_useful_body,
    }
    weights = {
        "readable_title": 0.75,
        "source_reference": 0.75,
        "timestamp": 0.5,
        "dikiwi_metadata": 0.75,
        "tags": 0.5,
        "resolving_wikilink": 0.75,
        "useful_body": 1.0,
    }
    score = round(sum(weights[key] for key, ok in checks.items() if ok), 2)
    failures = [key for key, ok in checks.items() if not ok]
    return NoteQuality(
        path=str(path.relative_to(vault)),
        stage=stage,
        title=title,
        score=score,
        has_readable_title=has_readable_title,
        has_source_reference=has_source_reference,
        has_timestamp=has_timestamp,
        has_dikiwi_metadata=has_dikiwi_metadata,
        has_tags=has_tags,
        has_resolving_wikilink=has_resolving_wikilink,
        has_useful_body=has_useful_body,
        failures=failures,
    )


def audit(vault: Path, output: Path, *, min_eval_notes: int = 10, min_score: float = 4.0) -> int:
    known_targets = _note_index(vault)
    note_paths = [
        path
        for stage in GENERATED_STAGE_DIRS
        for path in sorted((vault / stage).rglob("*.md"))
        if path.name != "00 Zettelkasten Index.md"
    ]
    qualities = [_score_note(path, vault, known_targets) for path in note_paths]

    failures: list[str] = []
    if len(qualities) < min_eval_notes:
        failures.append(f"Only {len(qualities)} generated notes found; need at least {min_eval_notes}")

    low_scores = [q for q in qualities if q.score < min_score]
    if low_scores:
        failures.append(f"{len(low_scores)} generated notes scored below {min_score}/5")

    missing_by_field: dict[str, int] = {}
    for q in qualities:
        for failure in q.failures:
            missing_by_field[failure] = missing_by_field.get(failure, 0) + 1
    hard_required = [
        "readable_title",
        "source_reference",
        "timestamp",
        "dikiwi_metadata",
        "tags",
        "resolving_wikilink",
    ]
    for field in hard_required:
        count = missing_by_field.get(field, 0)
        if count:
            failures.append(f"{count} generated notes missing required field: {field}")

    stage_counts: dict[str, int] = {}
    for q in qualities:
        stage_counts[q.stage] = stage_counts.get(q.stage, 0) + 1
    for stage in GENERATED_STAGE_DIRS:
        if stage_counts.get(stage, 0) <= 0:
            failures.append(f"No generated notes found for {stage}")

    eval_set = sorted(qualities, key=lambda q: (q.score, q.stage, q.path))[: max(min_eval_notes, min(len(qualities), 25))]
    report = {
        "vault": str(vault),
        "passed": not failures,
        "failures": failures,
        "rubric": {
            "max_score": 5.0,
            "minimum_passing_score": min_score,
            "criteria": {
                "readable_title": "0.75: H1/title is meaningful and not raw UUID-like",
                "source_reference": "0.75: frontmatter/body records source or upstream grounding",
                "timestamp": "0.5: date_created/created_at/timestamp exists",
                "dikiwi_metadata": "0.75: dikiwi_id plus stage/type metadata exists",
                "tags": "0.5: tags exist",
                "resolving_wikilink": "0.75: at least one wikilink resolves inside the vault",
                "useful_body": "1.0: body has enough explanatory content for second-brain use",
            },
        },
        "summary": {
            "generated_notes": len(qualities),
            "stage_counts": stage_counts,
            "average_score": round(mean([q.score for q in qualities]), 2) if qualities else 0,
            "minimum_score": min([q.score for q in qualities], default=0),
            "notes_below_threshold": len(low_scores),
            "missing_by_field": missing_by_field,
            "eval_notes_count": len(eval_set),
        },
        "eval_notes": [asdict(q) for q in eval_set],
        "low_score_samples": [asdict(q) for q in low_scores[:20]],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit RC0 generated-note quality.")
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-eval-notes", default=10, type=int)
    parser.add_argument("--min-score", default=4.0, type=float)
    args = parser.parse_args()
    return audit(args.vault, args.output, min_eval_notes=args.min_eval_notes, min_score=args.min_score)


if __name__ == "__main__":
    raise SystemExit(main())
