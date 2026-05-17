from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from aily.orchestration.state import WorkflowState


def _append_step(state: WorkflowState, step: str, **updates: Any) -> WorkflowState:
    steps = [*state.get("steps", []), step]
    return {
        **updates,
        "steps": steps,
        "current_node": step,
        "status": updates.get("status", "running"),
    }


def receive_motive(state: WorkflowState) -> WorkflowState:
    return _append_step(state, "receive_motive")


def extract_topics(state: WorkflowState) -> WorkflowState:
    motive = state.get("motive", "").strip()
    topic = motive[:80] if motive else state["workflow_run_id"]
    return _append_step(state, "extract_topics", topic_ids=[f"topic:{topic}"])


def draft_workflow_plan(state: WorkflowState) -> WorkflowState:
    return _append_step(
        state,
        "draft_workflow_plan",
        approvals={
            **state.get("approvals", {}),
            "workflow_plan": "pending",
        },
    )


def await_user_confirmation(state: WorkflowState) -> WorkflowState:
    response = interrupt(
        {
            "action": "confirm_workflow_plan",
            "workflow_run_id": state["workflow_run_id"],
            "message": "Approve this Aily workflow plan?",
        }
    )
    approved = isinstance(response, dict) and response.get("approved") is True
    return _append_step(
        state,
        "await_user_confirmation",
        status="running" if approved else "cancelled",
        approvals={
            **state.get("approvals", {}),
            "workflow_plan": "approved" if approved else "rejected",
        },
    )


def synthesize_placeholder_plan(state: WorkflowState) -> WorkflowState:
    if state.get("status") == "cancelled":
        return _append_step(state, "cancelled", status="cancelled")
    return _append_step(
        state,
        "synthesize_business_plan",
        business_plan_id=f"business_plan:{state['workflow_run_id']}",
        status="completed",
    )


def build_business_planning_graph(checkpointer: Any | None = None) -> Any:
    graph = StateGraph(WorkflowState)
    graph.add_node("receive_motive", receive_motive)
    graph.add_node("extract_topics", extract_topics)
    graph.add_node("draft_workflow_plan", draft_workflow_plan)
    graph.add_node("await_user_confirmation", await_user_confirmation)
    graph.add_node("synthesize_business_plan", synthesize_placeholder_plan)
    graph.add_edge(START, "receive_motive")
    graph.add_edge("receive_motive", "extract_topics")
    graph.add_edge("extract_topics", "draft_workflow_plan")
    graph.add_edge("draft_workflow_plan", "await_user_confirmation")
    graph.add_edge("await_user_confirmation", "synthesize_business_plan")
    graph.add_edge("synthesize_business_plan", END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())
