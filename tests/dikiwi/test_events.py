"""Tests for DIKIWI event bus.

Tests:
- InMemoryEventBus
- RedisStreamsEventBus (mocked)
- Event publishing/subscribing
- Error handling
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aily.dikiwi.events import (
    EventBus,
    InMemoryEventBus,
    RedisStreamsEventBus,
)
from aily.dikiwi.events.models import Event, EventType, StageCompletedEvent


class TestInMemoryEventBus:
    """Test in-memory event bus."""

    async def test_publish_calls_subscribers(self, event_bus):
        """Published events are received by subscribers."""
        received = []

        async def handler(event):
            received.append(event)

        event_bus.subscribe(StageCompletedEvent, handler)

        event = StageCompletedEvent(
            correlation_id="corr-001",
            stage="INFORMATION",
        )
        await event_bus.publish(event)

        # Wait for async handlers
        await asyncio.sleep(0.01)

        assert len(received) == 1
        assert received[0].correlation_id == "corr-001"

    async def test_multiple_subscribers_receive_event(self, event_bus):
        """All subscribers receive the event."""
        received1 = []
        received2 = []

        async def handler1(event):
            received1.append(event)

        async def handler2(event):
            received2.append(event)

        event_bus.subscribe(StageCompletedEvent, handler1)
        event_bus.subscribe(StageCompletedEvent, handler2)

        event = StageCompletedEvent(
            correlation_id="corr-001",
            stage="INFORMATION",
        )
        await event_bus.publish(event)

        await asyncio.sleep(0.01)

        assert len(received1) == 1
        assert len(received2) == 1

    async def test_unsubscribe_removes_handler(self, event_bus):
        """Unsubscribe stops receiving events."""
        received = []

        async def handler(event):
            received.append(event)

        unsubscribe = event_bus.subscribe(StageCompletedEvent, handler)

        event = StageCompletedEvent(
            correlation_id="corr-001",
            stage="INFORMATION",
        )
        await event_bus.publish(event)
        await asyncio.sleep(0.01)

        assert len(received) == 1

        # Unsubscribe
        unsubscribe()

        await event_bus.publish(event)
        await asyncio.sleep(0.01)

        # Should still be 1
        assert len(received) == 1

    async def test_handler_error_doesnt_affect_others(self, event_bus):
        """One handler failing doesn't affect others."""
        received = []

        async def failing_handler(event):
            raise ValueError("Handler error")

        async def good_handler(event):
            received.append(event)

        event_bus.subscribe(StageCompletedEvent, failing_handler)
        event_bus.subscribe(StageCompletedEvent, good_handler)

        event = StageCompletedEvent(
            correlation_id="corr-001",
            stage="INFORMATION",
        )
        await event_bus.publish(event)

        await asyncio.sleep(0.01)

        # Good handler should still receive
        assert len(received) == 1

    async def test_closed_bus_drops_events(self, event_bus):
        """Closed bus drops events."""
        await event_bus.close()

        event = StageCompletedEvent(
            correlation_id="corr-001",
            stage="INFORMATION",
        )
        await event_bus.publish(event)

        # Should not raise, just log warning

    async def test_subscribe_all_receives_all_events(self, event_bus):
        """subscribe_all receives all event types."""
        received = []

        async def handler(event):
            received.append(event)

        event_bus.subscribe_all(handler)

        event1 = StageCompletedEvent(correlation_id="1", stage="INFORMATION")
        await event_bus.publish(event1)

        await asyncio.sleep(0.01)

        assert len(received) == 1


class TestRedisStreamsEventBus:
    """Test Redis Streams event bus (with mocked Redis)."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = MagicMock()
        redis.xadd = AsyncMock(return_value=b"1234567890-0")
        redis.xgroup_create = AsyncMock()
        redis.xreadgroup = AsyncMock(return_value=[])
        redis.xack = AsyncMock()
        redis.close = AsyncMock()
        return redis

    async def test_publish_sends_to_redis(self, mock_redis):
        """Publish sends event to Redis Stream."""
        pytest.importorskip("redis")
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            bus = RedisStreamsEventBus()
            await bus._get_redis()  # Initialize connection

            event = StageCompletedEvent(
                correlation_id="corr-001",
                stage="INFORMATION",
            )
            await bus.publish(event)

            mock_redis.xadd.assert_called_once()
            args, kwargs = mock_redis.xadd.call_args
            assert args[0] == "dikiwi:events"

    async def test_subscribe_starts_listener(self, mock_redis):
        """Subscribe starts background listener."""
        pytest.importorskip("redis")
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            bus = RedisStreamsEventBus()

            received = []

            async def handler(event):
                received.append(event)

            bus.subscribe(StageCompletedEvent, handler)

            # Listener should be running
            assert bus._running
            assert bus._listen_task is not None

            await bus.close()

    async def test_close_cancels_listener(self, mock_redis):
        """Close cancels background listener."""
        pytest.importorskip("redis")
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            bus = RedisStreamsEventBus()

            async def handler(event):
                pass

            bus.subscribe(StageCompletedEvent, handler)

            await bus.close()

            assert bus._listen_task.cancelled() or bus._listen_task.done()

    async def test_missing_redis_raises_import_error(self):
        """Missing redis package raises ImportError."""
        try:
            import redis
        except ImportError:
            # redis is actually not installed
            with pytest.raises(ImportError):
                RedisStreamsEventBus()
            return

        # redis is installed - simulate missing with patch
        with patch.dict("sys.modules", {"redis": None}):
            bus = RedisStreamsEventBus()
            with pytest.raises(ImportError):
                await bus._get_redis()


class TestEventBusFactory:
    """Test create_event_bus factory function."""

    def test_create_in_memory_bus(self):
        """Factory creates InMemoryEventBus by default."""
        from aily.dikiwi.events.bus import create_event_bus

        bus = create_event_bus(use_redis=False)

        assert isinstance(bus, InMemoryEventBus)

    def test_create_redis_bus_falls_back_on_error(self):
        """Factory falls back to in-memory on Redis error."""
        from aily.dikiwi.events.bus import create_event_bus

        # Will fail because Redis is not available
        bus = create_event_bus(use_redis=True)

        # Should fall back to in-memory
        assert isinstance(bus, InMemoryEventBus)


class TestEventModels:
    """Test event dataclasses."""

    def test_event_has_correlation_id(self):
        """All events have correlation_id for lineage."""
        event = StageCompletedEvent(
            correlation_id="corr-001",
            stage="INFORMATION",
        )

        assert event.correlation_id == "corr-001"
        assert event.event_type == EventType.STAGE_COMPLETED

    def test_event_timestamp_auto_set(self):
        """Events auto-set timestamp."""
        event = StageCompletedEvent(
            correlation_id="corr-001",
            stage="INFORMATION",
        )

        assert event.timestamp is not None

    def test_event_to_dict_serialization(self):
        """Events can be serialized to dict."""
        event = StageCompletedEvent(
            correlation_id="corr-001",
            stage="INFORMATION",
        )

        data = event.to_dict()

        assert data["correlation_id"] == "corr-001"
        assert data["stage"] == "INFORMATION"
        assert data["event_type"] == "STAGE_COMPLETED"
