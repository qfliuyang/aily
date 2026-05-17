from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from typing_extensions import TypedDict

WorkflowKind = Literal["source_foundation", "triggered_iwi", "business_planning", "smoke"]
WorkflowStatus = Literal[
    "queued",
    "running",
    "interrupted",
    "completed",
    "failed",
    "cancelled",
]


class WorkflowState(TypedDict, total=False):
    workflow_run_id: str
    langgraph_thread_id: str
    workflow_kind: WorkflowKind
    status: WorkflowStatus
    current_node: str
    steps: list[str]
    motive: str
    source_id: str
    job_id: str
    job_type: str
    upload_id: str
    batch_id: str
    filename: str
    content_type: str
    url: str
    canonical_document_id: str
    canonical_markdown_path: str
    canonical_markdown_sha256: str
    markdown: str
    source_type: str
    processing_method: str
    rain_type: str
    stream_type: str
    pipeline_id: str
    final_stage: str
    stage_count: int
    stage_results: list[dict[str, Any]]
    topic_ids: list[str]
    second_opinion_ids: list[str]
    research_ids: list[str]
    evaluation_ids: list[str]
    business_plan_id: str
    obsidian_document_ids: list[str]
    approvals: dict[str, Any]
    metadata: dict[str, Any]
    error: str


@dataclass(frozen=True)
class WorkflowRunSnapshot:
    workflow_run_id: str
    langgraph_thread_id: str
    workflow_kind: str
    status: str
    current_node: str
    input_summary: str
    metadata: dict[str, Any]
    created_at: str
    updated_at: str
    completed_at: str | None = None
    last_error: str | None = None
