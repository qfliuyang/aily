from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def ensure_default_event_loop() -> Generator[None, None, None]:
    """Keep legacy sync tests compatible with asyncio objects.

    Several older tests instantiate classes or `asyncio.Future()` from regular
    synchronous fixtures. Python 3.11 no longer guarantees a default event loop
    after pytest-asyncio has torn one down, so provide one when absent.
    """
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    yield
