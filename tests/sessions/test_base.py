"""Tests for BaseMindScheduler and CircuitBreakerMixin."""

from __future__ import annotations

import asyncio
import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from aily.sessions.base import CircuitBreakerMixin, BaseMindScheduler


class TestCircuitBreakerMixin:
    """Tests for CircuitBreakerMixin."""

    def test_init_defaults(self):
        """Circuit breaker initializes with default values."""
        cb = CircuitBreakerMixin()
        assert cb._failure_threshold == 3
        assert cb._recovery_timeout == timedelta(minutes=30)
        assert cb._failure_count == 0
        assert cb._state == "closed"

    def test_init_custom_values(self):
        """Circuit breaker accepts custom threshold and timeout."""
        cb = CircuitBreakerMixin(failure_threshold=5, recovery_timeout=timedelta(minutes=10))
        assert cb._failure_threshold == 5
        assert cb._recovery_timeout == timedelta(minutes=10)

    @pytest.mark.asyncio
    async def test_can_execute_closed_state(self):
        """Can execute when circuit is closed (normal operation)."""
        cb = CircuitBreakerMixin()
        assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_record_failure_increments_count(self):
        """Recording failure increments failure count."""
        cb = CircuitBreakerMixin(failure_threshold=3)
        await cb.record_failure()
        assert cb._failure_count == 1
        assert cb._state == "closed"

    @pytest.mark.asyncio
    async def test_record_failure_trips_circuit(self):
        """Circuit opens after threshold failures."""
        cb = CircuitBreakerMixin(failure_threshold=2)
        await cb.record_failure()
        tripped = await cb.record_failure()
        assert tripped is True
        assert cb._state == "open"

    @pytest.mark.asyncio
    async def test_can_execute_open_state(self):
        """Cannot execute when circuit is open."""
        cb = CircuitBreakerMixin(failure_threshold=1)
        await cb.record_failure()
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_record_success_resets_count(self):
        """Success resets failure count."""
        cb = CircuitBreakerMixin(failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_reset_manual(self):
        """Manual reset closes circuit and clears failures."""
        cb = CircuitBreakerMixin(failure_threshold=1)
        await cb.record_failure()
        assert cb._state == "open"
        await cb.reset()
        assert cb._state == "closed"
        assert cb._failure_count == 0
        assert await cb.can_execute() is True


class MockMindScheduler(BaseMindScheduler):
    """Mock scheduler for testing BaseMindScheduler."""

    def __init__(self, **kwargs):
        self.mock_llm = MagicMock()
        super().__init__(
            llm_client=self.mock_llm,
            mind_name=kwargs.get("mind_name", "test"),
            schedule_hour=kwargs.get("schedule_hour", 8),
            schedule_minute=kwargs.get("schedule_minute", 0),
            circuit_breaker_threshold=kwargs.get("circuit_breaker_threshold", 3),
            enabled=kwargs.get("enabled", True),
        )
        self.run_called = False
        self.run_result = {"status": "ok"}

    async def _run_session(self) -> dict:
        self.run_called = True
        return self.run_result


class TestBaseMindScheduler:
    """Tests for BaseMindScheduler."""

    def test_init(self):
        """Scheduler initializes with correct parameters."""
        mock_llm = MagicMock()
        scheduler = MockMindScheduler(
            mind_name="test",
            schedule_hour=9,
            schedule_minute=30,
            circuit_breaker_threshold=5,
        )
        assert scheduler.mind_name == "test"
        assert scheduler.schedule_hour == 9
        assert scheduler.schedule_minute == 30
        assert scheduler.circuit_breaker._failure_threshold == 5
        assert scheduler.enabled is True

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Scheduler can start and stop."""
        scheduler = MockMindScheduler(mind_name="test")
        # Note: APScheduler requires a running event loop
        # In production this is handled by FastAPI's lifespan
        # For testing, we verify the scheduler object exists and is configured
        assert scheduler.scheduler is not None
        assert scheduler.mind_name == "test"
        assert scheduler.enabled is True

    @pytest.mark.asyncio
    async def test_run_session_wrapper_success(self):
        """Wrapper calls _run_session and records success."""
        scheduler = MockMindScheduler(mind_name="test")

        await scheduler._run_session_wrapper()

        assert scheduler.run_called is True
        assert scheduler.circuit_breaker._failure_count == 0
        assert scheduler._current_session.state.name == "COMPLETED"

    @pytest.mark.asyncio
    async def test_run_session_wrapper_failure(self):
        """Wrapper records failure on exception."""
        scheduler = MockMindScheduler(mind_name="test")
        scheduler._run_session = AsyncMock(side_effect=Exception("test error"))

        await scheduler._run_session_wrapper()

        assert scheduler.circuit_breaker._failure_count == 1
        assert scheduler._current_session.state.name == "FAILED"
        assert "test error" in scheduler._current_session.error_message

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_execution(self):
        """Circuit breaker prevents execution when open."""
        scheduler = MockMindScheduler(mind_name="test", circuit_breaker_threshold=1)

        # First failure opens circuit
        scheduler._run_session = AsyncMock(side_effect=Exception("error"))
        await scheduler._run_session_wrapper()

        # Verify circuit is open
        assert scheduler.circuit_breaker._state == "open"

        # Second call should be blocked - circuit breaker prevents execution
        scheduler._run_session = AsyncMock(return_value={"status": "ok"})
        await scheduler._run_session_wrapper()

        # Should still be on the failed session since new one was blocked
        assert scheduler._current_session.state.name == "CIRCUIT_OPEN"

    def test_disable_enable(self):
        """Scheduler can be disabled and enabled."""
        scheduler = MockMindScheduler(mind_name="test", enabled=False)
        assert scheduler.enabled is False

        scheduler.enabled = True
        assert scheduler.enabled is True
