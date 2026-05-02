from __future__ import annotations

import json
from pathlib import Path

import pytest

from aily.verify.run_registry import RunNotFoundError, RunRegistry


def test_run_registry_lists_real_manifest_files(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _write_run(runs_dir, "run-a", completed_at="2026-05-02T10:00:00+00:00")
    _write_run(runs_dir, "run-b", completed_at="2026-05-02T11:00:00+00:00")

    payload = RunRegistry(runs_dir).list_runs()

    assert payload["total"] == 2
    assert [run["run_id"] for run in payload["runs"]] == ["run-b", "run-a"]
    assert payload["runs"][0]["mocked"] is False
    assert payload["runs"][0]["fake_components"] == []


def test_run_registry_reads_detail_events_and_llm_calls(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    run_dir = _write_run(runs_dir, "run-a")
    (run_dir / "ui-events.jsonl").write_text(
        json.dumps({"type": "stage_started", "stage": "DATA"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "llm-calls.jsonl").write_text(
        json.dumps({"provider": "kimi", "model": "kimi-k2.6"}) + "\n",
        encoding="utf-8",
    )

    registry = RunRegistry(runs_dir)
    detail = registry.get_run("run-a")
    events = registry.get_events("run-a")
    calls = registry.get_llm_calls("run-a")

    assert detail["manifest"]["run_id"] == "run-a"
    assert detail["source_manifest"][0]["name"] == "source.pdf"
    assert events["events"][0]["stage"] == "DATA"
    assert calls["llm_calls"][0]["provider"] == "kimi"


def test_run_registry_rejects_path_traversal(tmp_path: Path) -> None:
    registry = RunRegistry(tmp_path / "runs")

    with pytest.raises(RunNotFoundError):
        registry.get_run("../secret")


def _write_run(runs_dir: Path, run_id: str, *, completed_at: str = "2026-05-02T10:00:00+00:00") -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "scenario": "unit",
        "started_at": "2026-05-02T09:59:00+00:00",
        "completed_at": completed_at,
        "exit_code": 0,
        "source_count": 1,
        "acceptance": {
            "mocked": False,
            "fake_components": [],
            "real_files": True,
            "real_graph_db": True,
            "real_vault": True,
            "real_llm": True,
        },
        "vault_counts_after": {"00-Chaos": 1},
        "graph_edge_count_after": 3,
        "failures_count": 0,
        "ui_event_count": 1,
        "result": {},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "source-manifest.json").write_text(
        json.dumps([{"name": "source.pdf", "sha256": "a" * 64}]),
        encoding="utf-8",
    )
    (run_dir / "samples").mkdir()
    (run_dir / "samples" / "index.json").write_text(json.dumps({}), encoding="utf-8")
    return run_dir
