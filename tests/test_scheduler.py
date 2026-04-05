import asyncio
import random
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from aily.scheduler.jobs import PassiveCaptureScheduler, BASE_INTERVAL, MAX_INTERVAL, JITTER_MAX


@pytest.fixture
def scheduler():
    mock_enqueue = MagicMock()
    mock_enqueue.return_value = asyncio.Future()
    mock_enqueue.return_value.set_result(None)
    sched = PassiveCaptureScheduler(enqueue_fn=mock_enqueue)
    yield sched
    sched.stop()


@pytest.mark.asyncio
async def test_jitter_within_bounds(scheduler):
    with patch("aily.scheduler.jobs.random.randint", return_value=30):
        scheduler.start()
        job = scheduler.scheduler.get_job("passive_capture")
        assert job is not None
        trigger = job.trigger
        assert trigger.interval.total_seconds() == BASE_INTERVAL + 30
    scheduler.stop()


def test_on_failure_doubles_interval(scheduler):
    assert scheduler._current_interval == BASE_INTERVAL
    scheduler._on_failure()
    assert scheduler._consecutive_failures == 1
    assert scheduler._current_interval == BASE_INTERVAL * 2
    scheduler._on_failure()
    assert scheduler._consecutive_failures == 2
    assert scheduler._current_interval == BASE_INTERVAL * 4


def test_on_failure_caps_at_max_interval(scheduler):
    for _ in range(10):
        scheduler._on_failure()
    assert scheduler._current_interval == MAX_INTERVAL


def test_on_success_resets_interval_and_failures(scheduler):
    scheduler._on_failure()
    scheduler._on_failure()
    assert scheduler._current_interval > BASE_INTERVAL
    scheduler._on_success()
    assert scheduler._consecutive_failures == 0
    assert scheduler._current_interval == BASE_INTERVAL
    assert scheduler._first_failure_at is None


def test_should_alert_after_24h(scheduler):
    scheduler._first_failure_at = datetime.now(timezone.utc) - timedelta(hours=25)
    assert scheduler._should_alert() is True


def test_should_not_alert_before_24h(scheduler):
    scheduler._first_failure_at = datetime.now(timezone.utc) - timedelta(hours=23)
    assert scheduler._should_alert() is False


def test_should_not_alert_when_no_failures(scheduler):
    assert scheduler._first_failure_at is None
    assert scheduler._should_alert() is False


@pytest.mark.asyncio
async def test_alert_sent_and_stops_after_24h_failures():
    mock_enqueue = MagicMock(return_value=asyncio.Future())
    mock_enqueue.return_value.set_result(None)
    sched = PassiveCaptureScheduler(enqueue_fn=mock_enqueue)

    sched._first_failure_at = datetime.now(timezone.utc) - timedelta(hours=25)
    sched._consecutive_failures = 5
    sched._current_interval = 0.05

    with patch.object(sched, "_send_alert") as mock_alert:
        with patch.object(sched, "_detect_urls", side_effect=OSError("boom")):
            with patch("aily.scheduler.jobs.random.randint", return_value=0):
                sched.start()
                await asyncio.sleep(0.15)
                mock_alert.assert_called_once()
                assert not sched.scheduler.running
    sched.stop()


@pytest.mark.asyncio
async def test_success_resets_and_reschedules():
    mock_enqueue = MagicMock(return_value=asyncio.Future())
    mock_enqueue.return_value.set_result(None)
    sched = PassiveCaptureScheduler(enqueue_fn=mock_enqueue)

    sched._consecutive_failures = 2
    sched._current_interval = 0.05

    with patch.object(sched, "_detect_urls", return_value=["https://example.com"]):
        with patch("aily.scheduler.jobs.random.randint", return_value=0):
            sched.start()
            await asyncio.sleep(0.15)
            assert sched._consecutive_failures == 0
            assert sched._current_interval == BASE_INTERVAL
    sched.stop()


@pytest.mark.asyncio
async def test_reschedule_exception_logged():
    mock_enqueue = MagicMock(return_value=asyncio.Future())
    mock_enqueue.return_value.set_result(None)
    sched = PassiveCaptureScheduler(enqueue_fn=mock_enqueue)

    sched._consecutive_failures = 0
    sched._current_interval = 0.05

    with patch.object(sched, "_detect_urls", return_value=[]):
        with patch.object(sched.scheduler, "reschedule_job", side_effect=RuntimeError("reschedule boom")):
            with patch("aily.scheduler.jobs.random.randint", return_value=0):
                with patch("aily.scheduler.jobs.logger") as mock_logger:
                    sched.start()
                    await asyncio.sleep(0.15)
                    mock_logger.exception.assert_called()
                    messages = [call.args[0] for call in mock_logger.exception.call_args_list]
                    assert any("Failed to reschedule" in m for m in messages)
    sched.stop()
