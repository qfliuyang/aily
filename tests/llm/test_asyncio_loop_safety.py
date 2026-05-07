from __future__ import annotations

import asyncio

import pytest

from aily.llm.client import LLMClient
from aily.runtime.backpressure import ProviderBackpressure


pytestmark = pytest.mark.contract


def test_llm_client_recreates_asyncio_primitives_per_event_loop() -> None:
    client = LLMClient(api_key="not-used", max_concurrency=1)
    loop_ids: list[int] = []
    semaphore_ids: list[int] = []
    lock_ids: list[int] = []

    async def bind_once() -> None:
        client._ensure_loop_primitives()
        assert client._asyncio_loop is asyncio.get_running_loop()
        assert client._semaphore is not None
        assert client._pace_lock is not None
        loop_ids.append(id(client._asyncio_loop))
        semaphore_ids.append(id(client._semaphore))
        lock_ids.append(id(client._pace_lock))

    asyncio.run(bind_once())
    asyncio.run(bind_once())

    assert loop_ids[0] != loop_ids[1]
    assert semaphore_ids[0] != semaphore_ids[1]
    assert lock_ids[0] != lock_ids[1]


def test_provider_backpressure_recreates_limiter_state_per_event_loop() -> None:
    limiter = ProviderBackpressure()
    state_loop_ids: list[int] = []
    state_semaphore_ids: list[int] = []

    async def bind_once() -> None:
        async with limiter.limit("loop-safety-provider", 1):
            state = limiter._states["loop-safety-provider"]
            state_loop_ids.append(id(state.loop))
            state_semaphore_ids.append(id(state.semaphore))

    asyncio.run(bind_once())
    asyncio.run(bind_once())

    assert state_loop_ids[0] != state_loop_ids[1]
    assert state_semaphore_ids[0] != state_semaphore_ids[1]
