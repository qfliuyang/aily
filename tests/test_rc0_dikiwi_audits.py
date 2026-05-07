from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_rc0_dikiwi_traceability import audit as audit_traceability
from scripts.audit_rc0_note_quality import audit as audit_note_quality

pytestmark = pytest.mark.contract


def _write_note(path: Path, *, title: str, source: str = "source.md", link: str = "00 Zettelkasten Index") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
dikiwi_id: "{path.stem.split('-', 1)[0]}"
date_created: "2026-05-06T00:00:00Z"
type: "{path.parts[-3] if len(path.parts) > 2 else 'data'}"
source: "{source}"
tags:
  - "dikiwi"
  - "rc0"
---

# {title}

This note has enough useful body content to be inspected as a second-brain artifact. It records source grounding,
links to related vault material, and avoids raw identifier-only titles that would make Obsidian navigation useless.

## Source Trace
- Source: `{source}`
- Vault Index: [[{link}|Zettelkasten Index]]
""",
        encoding="utf-8",
    )


def test_note_quality_audit_rejects_missing_resolving_links(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "00-Chaos").mkdir(parents=True)
    (vault / "00-Chaos" / "00 Zettelkasten Index.md").write_text("# Index\n", encoding="utf-8")
    for stage in ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]:
        _write_note(vault / stage / "2026-05-06" / f"{stage.lower()}-good.md", title=f"Good {stage} Note")
    # Add enough notes but intentionally omit a wikilink on one generated note.
    for idx in range(4):
        _write_note(vault / "05-Wisdom" / "2026-05-06" / f"wisdom-extra-{idx}.md", title=f"Extra Wisdom {idx}")
    bad = vault / "01-Data" / "2026-05-06" / "data-bad.md"
    _write_note(bad, title="Bad Linkless Data Note")
    bad.write_text(bad.read_text(encoding="utf-8").replace("[[00 Zettelkasten Index|Zettelkasten Index]]", "Zettelkasten Index"), encoding="utf-8")

    output = tmp_path / "quality.json"
    assert audit_note_quality(vault, output, min_eval_notes=10) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert any("resolving_wikilink" in failure for failure in report["failures"])


def test_note_quality_audit_accepts_complete_synthetic_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "00-Chaos").mkdir(parents=True)
    (vault / "00-Chaos" / "00 Zettelkasten Index.md").write_text("# Index\n", encoding="utf-8")
    for stage in ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]:
        for idx in range(2):
            _write_note(vault / stage / "2026-05-06" / f"{stage.lower()}-{idx}.md", title=f"Useful {stage} Note {idx}")

    output = tmp_path / "quality.json"
    assert audit_note_quality(vault, output, min_eval_notes=10) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["summary"]["generated_notes"] == 12
    assert report["summary"]["notes_below_threshold"] == 0


def test_traceability_audit_rejects_manual_sample_mutation(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "00-Chaos").mkdir(parents=True)
    (vault / "00-Chaos" / "00 Zettelkasten Index.md").write_text("# Index\n", encoding="utf-8")
    for stage in ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]:
        _write_note(vault / stage / "2026-05-06" / f"{stage.lower()}-good.md", title=f"Good {stage} Note")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "acceptance": {"mocked": False, "real_files": True, "real_graph_db": True, "real_vault": True, "real_llm": True},
                "result": {
                    "results": [
                        {
                            "pdf": "sample.pdf",
                            "bridge_result": {
                                "pipeline_id": "pipe-1",
                                "stage": "IMPACT",
                                "stage_results": [
                                    {"stage": stage, "success": True, "items_output": 1}
                                    for stage in ["DATA", "INFORMATION", "KNOWLEDGE", "INSIGHT", "WISDOM", "IMPACT"]
                                ],
                            },
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    llm_log = tmp_path / "llm.jsonl"
    llm_log.write_text(json.dumps({"success": True, "model": "real-model"}) + "\n", encoding="utf-8")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "samples": [
                    {"id": f"sample-{idx}", "sample_type": kind, "status": "completed", "successful": True, "mocked": False, "manual_state_mutation": idx == 0}
                    for idx, kind in enumerate(["url", "text", "pdf", "malformed", "duplicate", "url", "text", "pdf", "url", "text"])
                ]
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "traceability.json"
    assert audit_traceability(manifest, vault, output, llm_log=llm_log, sample_ledger=ledger) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert any("manual state mutation" in failure for failure in report["failures"])


def test_traceability_audit_rejects_local_only_llm_success_trace(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "00-Chaos").mkdir(parents=True)
    (vault / "00-Chaos" / "00 Zettelkasten Index.md").write_text("# Index\n", encoding="utf-8")
    for stage in ["01-Data", "02-Information", "03-Knowledge", "04-Insight", "05-Wisdom", "06-Impact"]:
        _write_note(vault / stage / "2026-05-06" / f"{stage.lower()}-good.md", title=f"Good {stage} Note")

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "acceptance": {"mocked": False, "real_files": True, "real_graph_db": True, "real_vault": True, "real_llm": True},
                "result": {
                    "results": [
                        {
                            "pdf": "sample.pdf",
                            "bridge_result": {
                                "pipeline_id": "pipe-1",
                                "stage": "IMPACT",
                                "stage_results": [
                                    {"stage": stage, "success": True, "items_output": 1}
                                    for stage in ["DATA", "INFORMATION", "KNOWLEDGE", "INSIGHT", "WISDOM", "IMPACT"]
                                ],
                            },
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    llm_log = tmp_path / "llm.jsonl"
    llm_log.write_text(json.dumps({"success": True, "model": "kimi-k2.6", "response": "looks real but has no provider receipt"}) + "\n", encoding="utf-8")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "samples": [
                    {"id": "sample-0", "sample_type": "url", "status": "completed", "successful": True, "mocked": False, "manual_state_mutation": False},
                    {"id": "sample-1", "sample_type": "text", "status": "completed", "successful": True, "mocked": False, "manual_state_mutation": False},
                    {"id": "sample-2", "sample_type": "pdf", "status": "completed", "successful": True, "mocked": False, "manual_state_mutation": False},
                    {"id": "sample-3", "sample_type": "malformed", "status": "failed", "successful": False, "mocked": False, "manual_state_mutation": False},
                    {"id": "sample-4", "sample_type": "duplicate", "status": "duplicate", "successful": True, "mocked": False, "manual_state_mutation": False},
                    {"id": "sample-5", "sample_type": "url", "status": "completed", "successful": True, "mocked": False, "manual_state_mutation": False},
                    {"id": "sample-6", "sample_type": "text", "status": "completed", "successful": True, "mocked": False, "manual_state_mutation": False},
                    {"id": "sample-7", "sample_type": "pdf", "status": "completed", "successful": True, "mocked": False, "manual_state_mutation": False},
                    {"id": "sample-8", "sample_type": "url", "status": "completed", "successful": True, "mocked": False, "manual_state_mutation": False},
                    {"id": "sample-9", "sample_type": "text", "status": "completed", "successful": True, "mocked": False, "manual_state_mutation": False},
                ]
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "traceability.json"
    assert audit_traceability(manifest, vault, output, llm_log=llm_log, sample_ledger=ledger) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert any("without provider-verifiable receipt metadata" in failure for failure in report["failures"])
    assert report["llm"]["provider_verified_successes"] == 0
