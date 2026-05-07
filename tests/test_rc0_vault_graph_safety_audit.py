from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_rc0_vault_graph_safety.py"
spec = importlib.util.spec_from_file_location("audit_rc0_vault_graph_safety", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.contract
def test_vault_graph_safety_audit_accepts_resolved_links_paths_and_unique_notes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    for stage in [
        "01-Data",
        "02-Information",
        "03-Knowledge",
        "04-Insight",
        "05-Wisdom",
        "06-Impact",
    ]:
        note_type = stage.split("-", 1)[1].lower()
        note_id = f"{note_type}_001"
        write(
            vault / stage / "2026-05-06" / f"{note_id}-Meaningful_Title.md",
            f'''---
dikiwi_id: "{note_id}"
type: "{note_type}"
aliases:
  - "{note_id}"
date_created: "2026-05-06T00:00:00Z"
source_paths:
  - "/tmp/source.pdf"
tags:
  - "{note_type}"
---

# Meaningful {note_type.title()} Title

Links resolve by stem [[data_001-Meaningful_Title]], alias [[{note_id}]], and path [[{stage}/2026-05-06/{note_id}-Meaningful_Title]].
''',
        )
    output = tmp_path / "report.json"

    assert module.audit(vault, output) == 0
    report = json.loads(output.read_text())
    assert report["passed"] is True
    assert report["counts"]["broken_wikilinks"] == 0
    assert report["counts"]["duplicate_identities"] == 0


@pytest.mark.contract
def test_vault_graph_safety_audit_rejects_broken_links_duplicates_and_bad_paths(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    base_frontmatter = '''---
dikiwi_id: "data_dup"
type: "data"
date_created: "2026-05-06T00:00:00Z"
source_paths:
  - "/tmp/source.pdf"
tags:
  - "data"
---

# Duplicate Data Title
'''
    write(vault / "01-Data" / "2026-05-06" / "data_dup-Duplicate_Data_Title.md", base_frontmatter + "Broken [[missing-target]].")
    write(vault / "01-Data" / "2026-05-06" / "data_dup-Duplicate_Data_Title_Copy.md", base_frontmatter)
    write(
        vault / "03-Knowledge" / "knowledge_in_wrong_place.md",
        '''---
dikiwi_id: "info_wrong"
type: "information"
source_paths:
  - "/tmp/source.pdf"
---

# Wrong path
''',
    )
    output = tmp_path / "report.json"

    assert module.audit(vault, output, require_stage_notes=False) == 1
    report = json.loads(output.read_text())
    assert report["passed"] is False
    assert report["counts"]["broken_wikilinks"] == 1
    assert report["counts"]["duplicate_dikiwi_ids"] == 1
    assert report["counts"]["path_failures"] == 1
