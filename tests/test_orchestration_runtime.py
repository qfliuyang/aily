from __future__ import annotations

from pathlib import Path

import pytest
from langgraph.types import Command

from aily.config import Settings
from aily.processing.processors import ExtractedContent
from aily.orchestration.business_planning_graph import build_business_planning_graph
from aily.orchestration.checkpoint import async_sqlite_checkpointer, sqlite_checkpointer
from aily.orchestration.runs import WorkflowRunStore
from aily.orchestration.source_foundation_graph import (
    SourceFoundationDependencies,
    build_source_foundation_graph,
)
from aily.sessions.dikiwi_mind import DikiwiResult, DikiwiStage, StageResult

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_workflow_run_store_lifecycle(tmp_path: Path) -> None:
    store = WorkflowRunStore(tmp_path / "workflow_runs.db")
    await store.initialize()
    try:
        created = await store.create_run(
            workflow_kind="source_foundation",
            workflow_run_id="wf_test",
            langgraph_thread_id="thread_test",
            input_summary="smoke source",
            metadata={"source_id": "source:test"},
        )

        assert created.workflow_run_id == "wf_test"
        assert created.langgraph_thread_id == "thread_test"
        assert created.status == "queued"
        assert created.metadata["source_id"] == "source:test"

        updated = await store.update_status(
            "wf_test",
            status="running",
            current_node="convert_to_markdown",
            metadata={"canonical_document_id": "canonical:test"},
        )

        assert updated.status == "running"
        assert updated.current_node == "convert_to_markdown"
        assert updated.metadata == {
            "source_id": "source:test",
            "canonical_document_id": "canonical:test",
        }

        by_thread = await store.get_run_by_thread("thread_test")
        assert by_thread is not None
        assert by_thread.workflow_run_id == "wf_test"

        listed = await store.list_runs()
        assert [run.workflow_run_id for run in listed] == ["wf_test"]

        completed = await store.update_status("wf_test", status="completed")
        assert completed.completed_at is not None
    finally:
        await store.close()


def test_orchestration_settings_paths_use_aily_data_dir(tmp_path: Path) -> None:
    settings = Settings(aily_data_dir=tmp_path)

    assert settings.langgraph_checkpoint_db_path == tmp_path / "langgraph_checkpoints.sqlite"
    assert settings.workflow_runs_db_path == tmp_path / "workflow_runs.db"
    assert settings.orchestrator_enabled is False
    assert settings.orchestrator_shadow_mode is True


def test_source_foundation_graph_uses_sqlite_checkpoints(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "langgraph_checkpoints.sqlite"

    with sqlite_checkpointer(checkpoint_path) as checkpointer:
        graph = build_source_foundation_graph(checkpointer)
        config = {"configurable": {"thread_id": "source-thread"}}

        result = graph.invoke(
            {
                "workflow_run_id": "wf_source",
                "langgraph_thread_id": "source-thread",
                "workflow_kind": "source_foundation",
                "status": "queued",
                "steps": [],
            },
            config,
        )

        assert result["status"] == "completed"
        assert result["source_id"] == "source:wf_source"
        assert result["canonical_document_id"] == "canonical:wf_source"
        assert result["steps"] == [
            "register_source",
            "convert_to_markdown",
            "run_data",
            "run_information",
            "run_knowledge",
        ]

        snapshot = graph.get_state(config)
        assert snapshot.values["current_node"] == "run_knowledge"
        assert len(list(graph.get_state_history(config))) >= 5

    assert checkpoint_path.exists()


@pytest.mark.asyncio
async def test_source_foundation_graph_runs_real_dependency_nodes(tmp_path: Path) -> None:
    events: list[tuple[str, dict]] = []

    class FakeSourceStore:
        def __init__(self) -> None:
            self.statuses: list[tuple[str, str, dict]] = []
            self.package: dict | None = None

        async def get_source(self, source_id: str) -> dict:
            return {
                "source_id": source_id,
                "normalized_source": "memo.txt",
                "filename": "memo.txt",
                "content_type": "text/plain",
                "metadata": {},
            }

        async def update_status(self, source_id: str, status: str, metadata: dict | None = None) -> None:
            self.statuses.append((source_id, status, metadata or {}))

        async def read_stored_object(self, source_id: str) -> bytes:
            return b"raw memo"

        async def get_markdown_package(self, source_id: str) -> dict | None:
            return self.package

        async def read_markdown_package(self, source_id: str) -> str:
            return "# Existing"

    class FakeRouter:
        async def process(self, data: bytes, *, filename: str, http_content_type: str) -> ExtractedContent:
            return ExtractedContent(text=data.decode(), title=filename, source_type="text")

    class FakeConverter:
        async def convert_extracted(self, **kwargs):
            return type(
                "MarkdownPackage",
                (),
                {
                    "package_id": "md:test",
                    "markdown": "# Memo\n\nraw memo",
                    "markdown_sha256": "abc123",
                    "package_path": str(tmp_path / "abc123.md"),
                    "title": "memo.txt",
                    "source_type": "text",
                },
            )()

    async def fake_dikiwi(drop):
        assert drop.metadata["processing_method"] == "source_foundation_graph"
        assert drop.rain_type.name == "DOCUMENT"
        assert drop.content == "# Memo\n\nraw memo"
        return DikiwiResult(
            input_id=drop.id,
            pipeline_id="pipeline-foundation",
            stage_results=[
                StageResult(stage=DikiwiStage.DATA, success=True),
                StageResult(stage=DikiwiStage.INFORMATION, success=True),
                StageResult(stage=DikiwiStage.KNOWLEDGE, success=True),
            ],
        )

    async def fake_emit(event_type: str, **payload) -> None:
        events.append((event_type, payload))

    source_store = FakeSourceStore()
    dependencies = SourceFoundationDependencies(
        source_store=source_store,
        processing_router_factory=FakeRouter,
        canonical_markdown_converter_factory=FakeConverter,
        dikiwi_ingestion=fake_dikiwi,
        emit_event=fake_emit,
    )

    async with async_sqlite_checkpointer(tmp_path / "source_graph.sqlite") as checkpointer:
        graph = build_source_foundation_graph(checkpointer, dependencies=dependencies)
        result = await graph.ainvoke(
            {
                "workflow_run_id": "wf_source_runtime",
                "langgraph_thread_id": "source-runtime-thread",
                "workflow_kind": "source_foundation",
                "status": "queued",
                "steps": [],
                "source_id": "source-1",
                "job_id": "job-1",
                "job_type": "process_upload_source",
                "metadata": {
                    "job_payload": {
                        "source_id": "source-1",
                        "job_id": "job-1",
                        "job_type": "process_upload_source",
                        "upload_id": "upload-1",
                    }
                },
            },
            {"configurable": {"thread_id": "source-runtime-thread"}},
        )

    assert result["status"] == "completed"
    assert result["pipeline_id"] == "pipeline-foundation"
    assert result["final_stage"] == "KNOWLEDGE"
    assert result["canonical_document_id"] == "md:test"
    assert result["steps"] == [
        "register_source",
        "convert_to_markdown",
        "run_data",
        "run_information",
        "run_knowledge",
    ]
    assert [status for _, status, _ in source_store.statuses] == [
        "extracting",
        "extracted",
        "processing",
        "completed",
    ]
    assert "canonical_markdown_created" in [event_type for event_type, _ in events]
    assert "source_ingest_completed" in [event_type for event_type, _ in events]


@pytest.mark.asyncio
async def test_source_foundation_graph_reuses_existing_markdown_package(tmp_path: Path) -> None:
    events: list[tuple[str, dict]] = []
    router_calls = 0

    class FakeSourceStore:
        def __init__(self) -> None:
            self.statuses: list[str] = []

        async def get_source(self, source_id: str) -> dict:
            return {
                "source_id": source_id,
                "filename": "memo.txt",
                "content_type": "text/plain",
                "metadata": {},
            }

        async def update_status(self, source_id: str, status: str, metadata: dict | None = None) -> None:
            self.statuses.append(status)

        async def get_markdown_package(self, source_id: str) -> dict:
            return {
                "package_id": "md:existing",
                "markdown_sha256": "existing-sha",
                "package_path": str(tmp_path / "existing.md"),
                "source_type": "text",
            }

        async def read_markdown_package(self, source_id: str) -> str:
            return "# Existing\n\nMemo"

    class FakeRouter:
        async def process(self, *args, **kwargs) -> ExtractedContent:
            nonlocal router_calls
            router_calls += 1
            return ExtractedContent(text="should not run")

    class FakeConverter:
        async def convert_extracted(self, **kwargs):
            raise AssertionError("converter should not run when package exists")

    async def fake_dikiwi(drop):
        assert drop.content == "# Existing\n\nMemo"
        return DikiwiResult(
            input_id=drop.id,
            pipeline_id="pipeline-reused",
            stage_results=[
                StageResult(stage=DikiwiStage.DATA, success=True),
                StageResult(stage=DikiwiStage.INFORMATION, success=True),
                StageResult(stage=DikiwiStage.KNOWLEDGE, success=True),
            ],
        )

    async def fake_emit(event_type: str, **payload) -> None:
        events.append((event_type, payload))

    dependencies = SourceFoundationDependencies(
        source_store=FakeSourceStore(),
        processing_router_factory=FakeRouter,
        canonical_markdown_converter_factory=FakeConverter,
        dikiwi_ingestion=fake_dikiwi,
        emit_event=fake_emit,
    )

    graph = build_source_foundation_graph(dependencies=dependencies)
    result = await graph.ainvoke(
        {
            "workflow_run_id": "wf_existing",
            "langgraph_thread_id": "existing-thread",
            "workflow_kind": "source_foundation",
            "status": "queued",
            "steps": [],
            "source_id": "source-existing",
            "job_id": "job-existing",
            "job_type": "process_upload_source",
        },
        {"configurable": {"thread_id": "existing-thread"}},
    )

    assert result["status"] == "completed"
    assert result["canonical_document_id"] == "md:existing"
    assert router_calls == 0
    assert "canonical_markdown_reused" in [event_type for event_type, _ in events]


@pytest.mark.asyncio
async def test_source_foundation_graph_stops_on_knowledge_failure(tmp_path: Path) -> None:
    events: list[tuple[str, dict]] = []

    class FakeSourceStore:
        def __init__(self) -> None:
            self.statuses: list[tuple[str, dict]] = []

        async def get_source(self, source_id: str) -> dict:
            return {
                "source_id": source_id,
                "filename": "memo.txt",
                "content_type": "text/plain",
                "metadata": {},
            }

        async def update_status(self, source_id: str, status: str, metadata: dict | None = None) -> None:
            self.statuses.append((status, metadata or {}))

        async def read_stored_object(self, source_id: str) -> bytes:
            return b"raw memo"

        async def get_markdown_package(self, source_id: str) -> dict | None:
            return None

    class FakeRouter:
        async def process(self, data: bytes, *, filename: str, http_content_type: str) -> ExtractedContent:
            return ExtractedContent(text=data.decode(), title=filename, source_type="text")

    class FakeConverter:
        async def convert_extracted(self, **kwargs):
            return type(
                "MarkdownPackage",
                (),
                {
                    "package_id": "md:failure",
                    "markdown": "# Memo\n\nraw memo",
                    "markdown_sha256": "failure-sha",
                    "package_path": str(tmp_path / "failure.md"),
                    "title": "memo.txt",
                    "source_type": "text",
                },
            )()

    async def fake_dikiwi(drop):
        return DikiwiResult(
            input_id=drop.id,
            pipeline_id="pipeline-failed",
            stage_results=[
                StageResult(stage=DikiwiStage.DATA, success=True),
                StageResult(stage=DikiwiStage.INFORMATION, success=True),
                StageResult(stage=DikiwiStage.KNOWLEDGE, success=False, error_message="knowledge failed"),
            ],
        )

    async def fake_emit(event_type: str, **payload) -> None:
        events.append((event_type, payload))

    graph = build_source_foundation_graph(
        dependencies=SourceFoundationDependencies(
            source_store=FakeSourceStore(),
            processing_router_factory=FakeRouter,
            canonical_markdown_converter_factory=FakeConverter,
            dikiwi_ingestion=fake_dikiwi,
            emit_event=fake_emit,
        )
    )
    result = await graph.ainvoke(
        {
            "workflow_run_id": "wf_failed",
            "langgraph_thread_id": "failed-thread",
            "workflow_kind": "source_foundation",
            "status": "queued",
            "steps": [],
            "source_id": "source-failed",
            "job_id": "job-failed",
            "job_type": "process_upload_source",
        },
        {"configurable": {"thread_id": "failed-thread"}},
    )

    assert result["status"] == "failed"
    assert result["current_node"] == "run_data"
    assert result["error"] == "knowledge failed"
    assert result["steps"] == ["register_source", "convert_to_markdown", "run_data"]
    assert "pipeline_failed" in [event_type for event_type, _ in events]
    assert "source_ingest_completed" not in [event_type for event_type, _ in events]


@pytest.mark.asyncio
async def test_source_foundation_graph_retry_reuses_markdown_after_failed_run(tmp_path: Path) -> None:
    events: list[tuple[str, dict]] = []
    conversion_calls = 0
    dikiwi_calls = 0

    class FakeSourceStore:
        def __init__(self) -> None:
            self.package: dict | None = None

        async def get_source(self, source_id: str) -> dict:
            return {
                "source_id": source_id,
                "filename": "memo.txt",
                "content_type": "text/plain",
                "metadata": {},
            }

        async def update_status(self, source_id: str, status: str, metadata: dict | None = None) -> None:
            return None

        async def read_stored_object(self, source_id: str) -> bytes:
            return b"raw memo"

        async def get_markdown_package(self, source_id: str) -> dict | None:
            return self.package

        async def read_markdown_package(self, source_id: str) -> str:
            return "# Memo\n\nraw memo"

    source_store = FakeSourceStore()

    class FakeRouter:
        async def process(self, data: bytes, *, filename: str, http_content_type: str) -> ExtractedContent:
            return ExtractedContent(text=data.decode(), title=filename, source_type="text")

    class FakeConverter:
        async def convert_extracted(self, **kwargs):
            nonlocal conversion_calls
            conversion_calls += 1
            source_store.package = {
                "package_id": "md:retry",
                "markdown_sha256": "retry-sha",
                "package_path": str(tmp_path / "retry.md"),
                "source_type": "text",
            }
            return type(
                "MarkdownPackage",
                (),
                {
                    "package_id": "md:retry",
                    "markdown": "# Memo\n\nraw memo",
                    "markdown_sha256": "retry-sha",
                    "package_path": str(tmp_path / "retry.md"),
                    "title": "memo.txt",
                    "source_type": "text",
                },
            )()

    async def fake_dikiwi(drop):
        nonlocal dikiwi_calls
        dikiwi_calls += 1
        if dikiwi_calls == 1:
            return DikiwiResult(
                input_id=drop.id,
                pipeline_id="pipeline-first",
                stage_results=[
                    StageResult(stage=DikiwiStage.DATA, success=True),
                    StageResult(stage=DikiwiStage.INFORMATION, success=True),
                    StageResult(stage=DikiwiStage.KNOWLEDGE, success=False, error_message="temporary graph failure"),
                ],
            )
        return DikiwiResult(
            input_id=drop.id,
            pipeline_id="pipeline-second",
            stage_results=[
                StageResult(stage=DikiwiStage.DATA, success=True),
                StageResult(stage=DikiwiStage.INFORMATION, success=True),
                StageResult(stage=DikiwiStage.KNOWLEDGE, success=True),
            ],
        )

    async def fake_emit(event_type: str, **payload) -> None:
        events.append((event_type, payload))

    dependencies = SourceFoundationDependencies(
        source_store=source_store,
        processing_router_factory=FakeRouter,
        canonical_markdown_converter_factory=FakeConverter,
        dikiwi_ingestion=fake_dikiwi,
        emit_event=fake_emit,
    )
    first = await build_source_foundation_graph(dependencies=dependencies).ainvoke(
        {
            "workflow_run_id": "wf_retry_first",
            "langgraph_thread_id": "retry-first-thread",
            "workflow_kind": "source_foundation",
            "status": "queued",
            "steps": [],
            "source_id": "source-retry",
            "job_id": "job-retry-1",
            "job_type": "process_upload_source",
        },
        {"configurable": {"thread_id": "retry-first-thread"}},
    )
    second = await build_source_foundation_graph(dependencies=dependencies).ainvoke(
        {
            "workflow_run_id": "wf_retry_second",
            "langgraph_thread_id": "retry-second-thread",
            "workflow_kind": "source_foundation",
            "status": "queued",
            "steps": [],
            "source_id": "source-retry",
            "job_id": "job-retry-2",
            "job_type": "process_upload_source",
        },
        {"configurable": {"thread_id": "retry-second-thread"}},
    )

    assert first["status"] == "failed"
    assert second["status"] == "completed"
    assert second["pipeline_id"] == "pipeline-second"
    assert conversion_calls == 1
    assert [event_type for event_type, _ in events].count("canonical_markdown_created") == 1
    assert [event_type for event_type, _ in events].count("canonical_markdown_reused") == 1


def test_business_planning_graph_pauses_and_resumes(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "business_checkpoints.sqlite"

    with sqlite_checkpointer(checkpoint_path) as checkpointer:
        graph = build_business_planning_graph(checkpointer)
        config = {"configurable": {"thread_id": "business-thread"}}

        interrupted = graph.invoke(
            {
                "workflow_run_id": "wf_business",
                "langgraph_thread_id": "business-thread",
                "workflow_kind": "business_planning",
                "status": "queued",
                "motive": "Assess whether this impact summary can become a B2B product.",
                "steps": [],
            },
            config,
        )

        assert "__interrupt__" in interrupted
        snapshot = graph.get_state(config)
        assert snapshot.next == ("await_user_confirmation",)
        assert snapshot.values["steps"] == [
            "receive_motive",
            "extract_topics",
            "draft_workflow_plan",
        ]

        resumed = graph.invoke(Command(resume={"approved": True}), config)

        assert resumed["status"] == "completed"
        assert resumed["business_plan_id"] == "business_plan:wf_business"
        assert resumed["approvals"]["workflow_plan"] == "approved"
        assert resumed["steps"] == [
            "receive_motive",
            "extract_topics",
            "draft_workflow_plan",
            "await_user_confirmation",
            "synthesize_business_plan",
        ]


def test_business_planning_graph_can_reject_confirmation(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "business_reject_checkpoints.sqlite"

    with sqlite_checkpointer(checkpoint_path) as checkpointer:
        graph = build_business_planning_graph(checkpointer)
        config = {"configurable": {"thread_id": "business-reject-thread"}}

        graph.invoke(
            {
                "workflow_run_id": "wf_reject",
                "langgraph_thread_id": "business-reject-thread",
                "workflow_kind": "business_planning",
                "status": "queued",
                "motive": "Do not run this yet.",
                "steps": [],
            },
            config,
        )

        resumed = graph.invoke(Command(resume={"approved": False}), config)

        assert resumed["status"] == "cancelled"
        assert resumed["approvals"]["workflow_plan"] == "rejected"
        assert "business_plan_id" not in resumed
