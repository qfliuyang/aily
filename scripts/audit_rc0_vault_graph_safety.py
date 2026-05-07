#!/usr/bin/env python3
"""Audit RC0 Obsidian/Zettelkasten vault safety evidence.

This verifier is intentionally filesystem-based: RC0 graph-safety claims must be
backed by real vault files, not in-memory note objects. It checks the target
requirements from AILY-RC0-007:

- generated notes are written under documented DIKIWI vault paths;
- wikilinks in generated release notes resolve to real vault notes/files; and
- duplicate generated note identities are rejected unless explicitly versioned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STAGE_DIRS = {
    "00-Chaos",
    "01-Data",
    "02-Information",
    "03-Knowledge",
    "04-Insight",
    "05-Wisdom",
    "06-Impact",
    "07-Proposal",
    "08-Entrepreneurship",
}
AUXILIARY_DIRS = {"99-MOC"}
TYPE_TO_STAGE = {
    "chaos": "00-Chaos",
    "data": "01-Data",
    "information": "02-Information",
    "knowledge": "03-Knowledge",
    "insight": "04-Insight",
    "wisdom": "05-Wisdom",
    "impact": "06-Impact",
    "proposal": "07-Proposal",
    "entrepreneurship": "08-Entrepreneurship",
}
WIKILINK_RE = re.compile(r"!?(?<!`)\[\[([^\]]+)\]\]")
UUIDISH_RE = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)


@dataclass(frozen=True)
class VaultNote:
    path: Path
    rel_path: str
    top_dir: str
    stem: str
    frontmatter: dict[str, Any]
    body: str
    heading: str
    sha256: str

    @property
    def generated(self) -> bool:
        return bool(self.frontmatter.get("dikiwi_id") or self.frontmatter.get("type") or self.frontmatter.get("dikiwi_level"))


def _read_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        import yaml

        parsed = yaml.safe_load(parts[1]) or {}
        return (parsed if isinstance(parsed, dict) else {}), parts[2]
    except Exception:
        # Keep the audit deterministic even in minimal environments. The writer's
        # YAML is simple enough for the path/link checks to continue without
        # accepting malformed frontmatter as good metadata.
        return {}, parts[2]


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _load_notes(vault: Path) -> list[VaultNote]:
    notes: list[VaultNote] = []
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = _read_frontmatter(text)
        parts = Path(rel).parts
        notes.append(
            VaultNote(
                path=path,
                rel_path=rel,
                top_dir=parts[0] if parts else "",
                stem=path.stem,
                frontmatter=fm,
                body=body,
                heading=_first_heading(text),
                sha256=_sha256(text),
            )
        )
    return notes


def _link_target_names(notes: list[VaultNote], vault: Path) -> set[str]:
    targets: set[str] = set()
    for note in notes:
        rel_without_suffix = str(Path(note.rel_path).with_suffix(""))
        targets.add(note.stem)
        targets.add(rel_without_suffix)
        targets.add(note.rel_path)
        dikiwi_id = note.frontmatter.get("dikiwi_id")
        if dikiwi_id:
            targets.add(str(dikiwi_id))
        aliases = note.frontmatter.get("aliases")
        if isinstance(aliases, list):
            targets.update(str(alias) for alias in aliases if str(alias).strip())
    for path in vault.rglob("*"):
        if path.is_file():
            rel = path.relative_to(vault).as_posix()
            targets.add(rel)
            targets.add(str(Path(rel).with_suffix("")))
    return targets


def _normalize_link(raw: str) -> str:
    target = raw.split("|", 1)[0].strip()
    target = target.split("#", 1)[0].strip()
    return target


def _wikilink_failures(notes: list[VaultNote], targets: set[str]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for note in notes:
        if not note.generated:
            continue
        text = note.path.read_text(encoding="utf-8", errors="replace")
        for match in WIKILINK_RE.finditer(text):
            target = _normalize_link(match.group(1))
            if not target or target.startswith("#"):
                continue
            if target not in targets:
                failures.append({"note": note.rel_path, "target": target})
    return failures


def _canonical_source(frontmatter: dict[str, Any]) -> tuple[str, ...]:
    raw = frontmatter.get("source_paths")
    if isinstance(raw, list) and raw:
        return tuple(str(item) for item in raw)
    source = frontmatter.get("source")
    return (str(source),) if source else ()


def _note_title(note: VaultNote) -> str:
    return note.heading or str(note.frontmatter.get("title") or note.stem)


def _normalized_title(title: str) -> str:
    return re.sub(r"\W+", " ", title).strip().lower()


def _is_versioned(note: VaultNote) -> bool:
    fm = note.frontmatter
    if fm.get("version") or fm.get("revision") or fm.get("supersedes"):
        return True
    return "version" in note.stem.lower() or "revision" in note.stem.lower()


def _duplicate_failures(notes: list[VaultNote]) -> dict[str, Any]:
    by_dikiwi_id: dict[str, list[str]] = {}
    by_identity: dict[tuple[Any, ...], list[str]] = {}
    by_content: dict[tuple[Any, ...], list[str]] = {}

    for note in notes:
        if not note.generated or _is_versioned(note):
            continue
        dikiwi_id = note.frontmatter.get("dikiwi_id")
        if dikiwi_id:
            by_dikiwi_id.setdefault(str(dikiwi_id), []).append(note.rel_path)
        note_type = str(note.frontmatter.get("type") or note.frontmatter.get("dikiwi_level") or "")
        identity = (
            note.top_dir,
            note_type,
            _canonical_source(note.frontmatter),
            _normalized_title(_note_title(note)),
        )
        if identity[1] and identity[2] and identity[3]:
            by_identity.setdefault(identity, []).append(note.rel_path)
        content_key = (note.top_dir, note_type, _canonical_source(note.frontmatter), note.sha256)
        if content_key[1] and content_key[2]:
            by_content.setdefault(content_key, []).append(note.rel_path)

    return {
        "duplicate_dikiwi_ids": {key: paths for key, paths in by_dikiwi_id.items() if len(paths) > 1},
        "duplicate_identities": {" | ".join(map(str, key)): paths for key, paths in by_identity.items() if len(paths) > 1},
        "duplicate_content": {" | ".join(map(str, key)): paths for key, paths in by_content.items() if len(paths) > 1},
    }


def _path_failures(notes: list[VaultNote]) -> list[str]:
    failures: list[str] = []
    allowed = STAGE_DIRS | AUXILIARY_DIRS
    for note in notes:
        if note.top_dir not in allowed:
            failures.append(f"{note.rel_path}: outside documented vault directories")
            continue
        if not note.generated:
            continue
        note_type = str(note.frontmatter.get("type") or note.frontmatter.get("dikiwi_level") or "").strip()
        expected = TYPE_TO_STAGE.get(note_type)
        if expected and note.top_dir != expected:
            failures.append(f"{note.rel_path}: type {note_type!r} belongs in {expected}, not {note.top_dir}")
        dikiwi_id = str(note.frontmatter.get("dikiwi_id") or "")
        if dikiwi_id and UUIDISH_RE.match(note.stem):
            failures.append(f"{note.rel_path}: UUID-like raw title/stem is not graph-friendly")
    return failures


def audit(vault: Path, output: Path, *, require_stage_notes: bool = True) -> int:
    vault = vault.expanduser().resolve()
    notes = _load_notes(vault)
    generated = [note for note in notes if note.generated]
    stage_listing: dict[str, list[str]] = {stage: [] for stage in sorted(STAGE_DIRS)}
    for note in generated:
        if note.top_dir in stage_listing:
            stage_listing[note.top_dir].append(note.rel_path)

    path_failures = _path_failures(notes)
    link_failures = _wikilink_failures(notes, _link_target_names(notes, vault))
    duplicate_failures = _duplicate_failures(notes)
    failures: list[str] = []
    if not notes:
        failures.append("Vault contains no markdown notes")
    if require_stage_notes:
        for stage in ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]:
            if not stage_listing.get(stage):
                failures.append(f"{stage} has no generated markdown notes")
    if path_failures:
        failures.append(f"Vault path contract failures: {len(path_failures)}")
    if link_failures:
        failures.append(f"Broken wikilinks in generated notes: {len(link_failures)}")
    if any(duplicate_failures.values()):
        failures.append("Duplicate generated note identities found")

    report = {
        "vault": str(vault),
        "passed": not failures,
        "failures": failures,
        "counts": {
            "markdown_notes": len(notes),
            "generated_notes": len(generated),
            "broken_wikilinks": len(link_failures),
            "path_failures": len(path_failures),
            "duplicate_dikiwi_ids": len(duplicate_failures["duplicate_dikiwi_ids"]),
            "duplicate_identities": len(duplicate_failures["duplicate_identities"]),
            "duplicate_content": len(duplicate_failures["duplicate_content"]),
        },
        "stage_listing": stage_listing,
        "path_failures": path_failures[:50],
        "broken_wikilinks": link_failures[:50],
        "duplicates": duplicate_failures,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit RC0 vault graph-safety evidence.")
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--no-require-stage-notes", action="store_true")
    args = parser.parse_args()
    return audit(args.vault, args.output, require_stage_notes=not args.no_require_stage_notes)


if __name__ == "__main__":
    raise SystemExit(main())
