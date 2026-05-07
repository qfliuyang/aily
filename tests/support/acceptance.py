from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AcceptanceBoundaryManifest:
    """Machine-readable declaration of which production boundaries are real.

    Local integration/e2e suites may substitute components for speed and
    determinism. Tests marked ``acceptance`` are release-evidence tests: they
    must prove every required production boundary is real and must not carry
    undeclared fakes.
    """

    real_llm: bool
    real_graph_db: bool
    real_queue_worker: bool
    real_writer_api: bool
    real_http: bool
    fake_components: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "real_llm": self.real_llm,
            "real_graph_db": self.real_graph_db,
            "real_queue_worker": self.real_queue_worker,
            "real_writer_api": self.real_writer_api,
            "real_http": self.real_http,
            "fake_components": list(self.fake_components),
            "acceptance_ready": self.acceptance_ready,
        }

    @property
    def acceptance_ready(self) -> bool:
        return (
            self.real_llm
            and self.real_graph_db
            and self.real_queue_worker
            and self.real_writer_api
            and self.real_http
            and not self.fake_components
        )

    def assert_acceptance_ready(self) -> None:
        assert self.acceptance_ready, (
            "Acceptance evidence requires all production boundaries to be real; "
            f"manifest={self.as_dict()}"
        )


def assert_acceptance_boundary_ready(manifest: AcceptanceBoundaryManifest) -> None:
    manifest.assert_acceptance_ready()
