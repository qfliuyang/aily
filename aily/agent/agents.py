from __future__ import annotations

import json
from typing import Any

from aily.graph.db import GraphDB


async def summarizer_agent(context: dict[str, Any], text: str) -> str:
    return f"- {text.strip()[:200]}..." if len(text) > 200 else f"- {text.strip()}"


async def researcher_agent(context: dict[str, Any], query: str) -> str:
    return f"Research note for: {query.strip()}"


async def connector_agent(context: dict[str, Any], node_id: str) -> str:
    graph_db: GraphDB = context["graph_db"]
    logs = await graph_db.get_source_logs_for_node(node_id)
    cooccurring = await graph_db.get_cooccurring_nodes(
        logs[0]["raw_log_id"] if logs else ""
    )
    labels = [node["label"] for node in cooccurring if node["id"] != node_id]
    return f"Connected to: {', '.join(labels)}" if labels else "No connections found."


async def zettel_suggester_agent(context: dict[str, Any], note_title: str) -> str:
    graph_db: GraphDB = context["graph_db"]
    nodes = await graph_db.get_nodes_by_type("concept")
    suggestions = [node["label"] for node in nodes if note_title.lower() not in node["label"].lower()][:5]
    return f"Suggested links: {', '.join(suggestions)}" if suggestions else "No related notes found."
