from __future__ import annotations

import pytest

from tests.integration.conftest import ProblemExposure

pytestmark = pytest.mark.contract


def test_problem_exposure_fails_closed_for_unknown_production_category() -> None:
    exposure = ProblemExposure(fail_on_exposure=True)

    exposure.expose_problem("NEW_FAILURE_CATEGORY", "new production failure surfaced")

    with pytest.raises(pytest.fail.Exception, match="NEW_FAILURE_CATEGORY"):
        exposure.assert_no_blocking_problems()


def test_problem_exposure_allows_non_blocking_configuration_notes() -> None:
    exposure = ProblemExposure(fail_on_exposure=True)

    exposure.record_observation("CONFIGURATION_NOTICE", "credentialed service unavailable in local lane")

    assert exposure.blocking_problems() == []
    exposure.assert_no_blocking_problems()


def test_legacy_expose_fails_closed_for_failure_shaped_categories() -> None:
    exposure = ProblemExposure(fail_on_exposure=True)

    exposure.expose("DEDUP_FAILURE", "duplicate URLs were enqueued")

    with pytest.raises(pytest.fail.Exception, match="DEDUP_FAILURE"):
        exposure.assert_no_blocking_problems()


def test_legacy_expose_rejects_non_blocking_failure_categories() -> None:
    exposure = ProblemExposure(fail_on_exposure=True)

    with pytest.raises(ValueError, match="AUTH_FAILURE"):
        exposure.expose("AUTH_FAILURE", "wrong credentials rejected as expected", blocking=False)


def test_expected_diagnostics_use_non_failure_observation_categories() -> None:
    exposure = ProblemExposure(fail_on_exposure=True)

    exposure.record_observation("AUTH_REJECTION_EXPECTED", "wrong credentials rejected as expected")

    assert exposure.blocking_problems() == []
    exposure.assert_no_blocking_problems()


def test_legacy_expose_fails_closed_for_data_integrity() -> None:
    exposure = ProblemExposure(fail_on_exposure=True)

    exposure.expose("DATA_INTEGRITY", "expected 30 rows, got 29")

    with pytest.raises(pytest.fail.Exception, match="DATA_INTEGRITY"):
        exposure.assert_no_blocking_problems()


def test_problem_exposure_cannot_suppress_blocking_problems() -> None:
    exposure = ProblemExposure(fail_on_exposure=False)

    exposure.expose("DATA_INTEGRITY", "expected 30 rows, got 29")

    with pytest.raises(pytest.fail.Exception, match="DATA_INTEGRITY"):
        exposure.assert_no_blocking_problems()


def test_legacy_expose_rejects_blocking_false_for_data_integrity() -> None:
    exposure = ProblemExposure(fail_on_exposure=True)

    with pytest.raises(ValueError, match="DATA_INTEGRITY"):
        exposure.expose("DATA_INTEGRITY", "expected 30 rows, got 29", blocking=False)


def test_record_observation_rejects_failure_shaped_categories() -> None:
    exposure = ProblemExposure(fail_on_exposure=True)

    with pytest.raises(ValueError, match="DATA_INTEGRITY"):
        exposure.record_observation("DATA_INTEGRITY", "expected 30 rows, got 29")


def test_legacy_expose_fails_closed_for_slow_performance_categories() -> None:
    exposure = ProblemExposure(fail_on_exposure=True)

    exposure.expose("SLOW_TRANSACTION", "large transaction took too long")

    with pytest.raises(pytest.fail.Exception, match="SLOW_TRANSACTION"):
        exposure.assert_no_blocking_problems()


def test_record_observation_rejects_slow_performance_categories() -> None:
    exposure = ProblemExposure(fail_on_exposure=True)

    with pytest.raises(ValueError, match="SLOW_WRITE"):
        exposure.record_observation("SLOW_WRITE", "write took too long")
