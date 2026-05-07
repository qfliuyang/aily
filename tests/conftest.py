from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest

from tests.support.acceptance import AcceptanceBoundaryManifest, assert_acceptance_boundary_ready


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


@pytest.fixture
def acceptance_boundary_manifest() -> AcceptanceBoundaryManifest:
    """Fail-closed default for globally marked acceptance tests.

    Real acceptance suites must override this fixture with a manifest whose
    required boundaries are all production-real. Without an override, an
    accidental @pytest.mark.acceptance test cannot pass by locality.
    """

    return AcceptanceBoundaryManifest(
        real_llm=False,
        real_graph_db=False,
        real_queue_worker=False,
        real_writer_api=False,
        real_http=False,
        fake_components=["missing_acceptance_boundary_manifest"],
    )


@pytest.fixture(autouse=True)
def enforce_acceptance_boundary_manifest(request) -> None:
    """Globally guard every test marked `acceptance`, regardless of directory."""

    if request.node.get_closest_marker("acceptance") is None:
        return
    manifest = request.getfixturevalue("acceptance_boundary_manifest")
    assert_acceptance_boundary_ready(manifest)
