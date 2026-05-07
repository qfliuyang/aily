from __future__ import annotations

import pytest

from tests.support.acceptance import AcceptanceBoundaryManifest, assert_acceptance_boundary_ready

pytestmark = pytest.mark.contract


def test_acceptance_manifest_rejects_substituted_components_when_claiming_acceptance() -> None:
    manifest = AcceptanceBoundaryManifest(
        real_llm=True,
        real_graph_db=True,
        real_queue_worker=True,
        real_writer_api=False,
        real_http=True,
        fake_components=["obsidian_writer"],
    )

    with pytest.raises(AssertionError, match="obsidian_writer"):
        manifest.assert_acceptance_ready()


def test_acceptance_manifest_accepts_all_required_real_boundaries() -> None:
    manifest = AcceptanceBoundaryManifest(
        real_llm=True,
        real_graph_db=True,
        real_queue_worker=True,
        real_writer_api=True,
        real_http=True,
        fake_components=[],
    )

    assert manifest.acceptance_ready is True
    manifest.assert_acceptance_ready()


def test_acceptance_marker_requires_ready_manifest() -> None:
    manifest = AcceptanceBoundaryManifest(
        real_llm=True,
        real_graph_db=True,
        real_queue_worker=True,
        real_writer_api=False,
        real_http=True,
        fake_components=["obsidian_writer"],
    )
    with pytest.raises(AssertionError, match="obsidian_writer"):
        assert_acceptance_boundary_ready(manifest)
