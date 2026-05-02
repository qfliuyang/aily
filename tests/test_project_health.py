from __future__ import annotations

from scripts.verify_project_health import build_report


def test_project_health_script_inspects_real_repository() -> None:
    report = build_report()

    assert report["tracked_file_count"] > 50
    assert "by_kind" in report
    assert isinstance(report["findings"], list)
