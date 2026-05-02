from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aily.verify.evidence import EvidenceRun, graph_snapshot, source_manifest, summarize_ui_events, vault_counts


def test_source_manifest_hashes_real_files(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"real bytes")

    manifest = source_manifest([source])

    assert manifest[0]["name"] == "input.pdf"
    assert manifest[0]["size_bytes"] == len(b"real bytes")
    assert len(manifest[0]["sha256"]) == 64


def test_source_manifest_rejects_missing_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        source_manifest([tmp_path / "missing.pdf"])


def test_vault_counts_and_evidence_manifest(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "00-Chaos").mkdir(parents=True)
    (vault / "00-Chaos" / "note.md").write_text("# Chaos", encoding="utf-8")
    graph_db = vault / ".aily" / "graph.db"
    graph_db.parent.mkdir(parents=True)
    _create_graph_db(graph_db)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")

    run = EvidenceRun(
        root_dir=tmp_path / "runs",
        scenario="unit",
        vault_path=vault,
        graph_db_path=graph_db,
        source_paths=[source],
        source_seed=7,
        run_id="unit-run",
    )
    run.capture_before()
    manifest = run.finalize(exit_code=0, result={"ok": True})

    assert vault_counts(vault)["00-Chaos"] == 1
    assert graph_snapshot(graph_db)["node_counts"]["information"] == 1
    assert manifest["run_id"] == "unit-run"
    assert manifest["acceptance"]["mocked"] is False
    assert (run.path / "manifest.json").exists()
    assert (run.path / "source-manifest.json").exists()
    assert (run.path / "samples" / "chaos" / "note.md").exists()


def test_evidence_finalize_persists_ui_events_and_stderr(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    graph_db = vault / ".aily" / "graph.db"
    graph_db.parent.mkdir(parents=True)
    _create_graph_db(graph_db)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")
    events = [
        {"type": "stage_started", "stage": "DATA"},
        {"type": "stage_completed", "stage": "DATA"},
    ]

    run = EvidenceRun(
        root_dir=tmp_path / "runs",
        scenario="unit",
        vault_path=vault,
        graph_db_path=graph_db,
        source_paths=[source],
        run_id="ui-run",
    )
    run.capture_before()
    manifest = run.finalize(exit_code=1, ui_events=events, stderr_text="traceback")

    assert manifest["ui_event_count"] == 2
    assert "stage_started" in (run.path / "ui-events.jsonl").read_text(encoding="utf-8")
    assert (run.path / "stderr.log").read_text(encoding="utf-8") == "traceback"
    assert summarize_ui_events(events)["stages"]["DATA"] == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"real_files": False},
        {"real_graph_db": False},
        {"real_vault": False},
        {"real_llm": False},
        {"fake_components": ["llm"]},
    ],
)
def test_evidence_rejects_fake_acceptance_claims(tmp_path: Path, kwargs: dict) -> None:
    vault = tmp_path / "vault"
    graph_db = vault / ".aily" / "graph.db"
    graph_db.parent.mkdir(parents=True)

    with pytest.raises(ValueError, match="mocked=False"):
        EvidenceRun(
            root_dir=tmp_path / "runs",
            scenario="unit",
            vault_path=vault,
            graph_db_path=graph_db,
            source_paths=[],
            run_id="bad-run",
            **kwargs,
        )


def test_evidence_allows_explicit_mocked_non_acceptance_runs(tmp_path: Path) -> None:
    run = EvidenceRun(
        root_dir=tmp_path / "runs",
        scenario="unit",
        vault_path=tmp_path / "vault",
        graph_db_path=tmp_path / "graph.db",
        mocked=True,
        fake_components=["llm"],
        real_llm=False,
        run_id="mocked-run",
    )

    assert run.mocked is True


def _create_graph_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                label TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE edges (
                id TEXT PRIMARY KEY,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                source TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO nodes (id, type, label, source) VALUES (?, ?, ?, ?)",
            ("info-1", "information", "Meaningful concept", "unit"),
        )
        conn.commit()
