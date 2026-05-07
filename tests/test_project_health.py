from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_project_health import (
    build_report,
    compare_to_baseline,
    load_baseline,
    scan_nested_pytest_configs,
    scan_unmarked_test_lanes,
)

pytestmark = pytest.mark.contract


def test_project_health_script_inspects_real_repository() -> None:
    report = build_report()

    assert report["tracked_file_count"] > 50
    assert "by_kind" in report
    assert isinstance(report["findings"], list)


def test_project_health_does_not_regress_beyond_baseline() -> None:
    report = build_report()
    failures = compare_to_baseline(report, load_baseline())

    assert failures == []


def test_project_health_detects_unmarked_test_lanes(tmp_path: Path) -> None:
    unmarked = tmp_path / "test_unmarked.py"
    unmarked.write_text("def test_missing_lane():\n    assert True\n", encoding="utf-8")
    marked = tmp_path / "test_marked.py"
    marked.write_text(
        "import pytest\n\npytestmark = pytest.mark.contract\n\ndef test_has_lane():\n    assert True\n",
        encoding="utf-8",
    )

    findings = scan_unmarked_test_lanes([unmarked, marked])

    assert len(findings) == 1
    assert findings[0].kind == "unmarked_test_lane"
    assert "test_missing_lane" in findings[0].detail


def test_project_health_treats_slow_as_modifier_not_lane(tmp_path: Path) -> None:
    slow_only = tmp_path / "test_slow_only.py"
    slow_only.write_text(
        "import pytest\n\n@pytest.mark.slow\ndef test_slow_without_semantic_lane():\n    assert True\n",
        encoding="utf-8",
    )

    findings = scan_unmarked_test_lanes([slow_only])

    assert len(findings) == 1
    assert "test_slow_without_semantic_lane" in findings[0].detail


def test_project_health_baseline_rejects_new_finding_identity() -> None:
    report = {
        "by_kind": {"unmarked_test_lane": 1},
        "findings": [
            {
                "kind": "unmarked_test_lane",
                "path": "tests/test_new.py",
                "detail": "line 1: test_new has no production test lane marker",
                "severity": "warn",
                "key": "unmarked_test_lane|tests/test_new.py|line 1: test_new has no production test lane marker",
            }
        ],
    }
    baseline = {
        "by_kind": {"unmarked_test_lane": 1},
        "accepted_findings": [
            "unmarked_test_lane|tests/test_old.py|line 1: test_old has no production test lane marker"
        ],
    }

    failures = compare_to_baseline(report, baseline)

    assert any("new unbaselined findings" in failure for failure in failures)


def test_project_health_rejects_nested_pytest_configs(tmp_path: Path) -> None:
    nested = tmp_path / "tests" / "e2e" / "pytest.ini"
    nested.parent.mkdir(parents=True)
    nested.write_text("[pytest]\n", encoding="utf-8")

    findings = scan_nested_pytest_configs([nested])

    assert len(findings) == 1
    assert findings[0].kind == "nested_pytest_config"
