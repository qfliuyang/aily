"""Graph-triggered subgraph selection for DIKIWI synthesis stages."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from aily.config import SETTINGS
from aily.sessions.dikiwi_mind import InformationNode, KnowledgeLink

if TYPE_CHECKING:
    from aily.dikiwi.agents.context import AgentContext

logger = logging.getLogger(__name__)


@dataclass
class SubgraphCandidate:
    """A meaningful graph neighborhood that may deserve DIKIWI synthesis."""

    id: str
    anchor_id: str
    anchor_label: str
    anchor_type: str
    reason: str
    score: float
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    changed_node_ids: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_prompt_context(self, max_nodes: int = 18, max_edges: int = 24) -> str:
        lines = [
            f"Subgraph {self.id}",
            f"Anchor: {self.anchor_label} ({self.anchor_type})",
            f"Trigger: {self.reason}",
            f"Score: {self.score:.2f}",
            "Nodes:",
        ]
        for idx, node in enumerate(self.nodes[:max_nodes], start=1):
            marker = "*" if node.get("id") in set(self.changed_node_ids) else "-"
            source = _source_label(node)
            lines.append(
                f"{marker} E{idx}: [{node.get('type', 'node')}] "
                f"{node.get('label', '')[:220]} | source={source}"
            )
        if self.edges:
            lines.append("Edges:")
            node_labels = {node.get("id"): node.get("label", "")[:60] for node in self.nodes}
            for edge in self.edges[:max_edges]:
                src = node_labels.get(edge.get("source_node_id"), edge.get("source_node_id", ""))
                tgt = node_labels.get(edge.get("target_node_id"), edge.get("target_node_id", ""))
                lines.append(
                    f"- {src} --{edge.get('relation_type')}({float(edge.get('weight', 0.0)):.2f})--> {tgt}"
                )
        return "\n".join(lines)


@dataclass
class GraphChangeAssessment:
    """Decision about whether graph changes justify higher-order generation."""

    triggered: bool
    reason: str
    score: float = 0.0
    candidates: list[SubgraphCandidate] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_prompt_context(self) -> str:
        if not self.candidates:
            return f"No synthesis-grade subgraph found. Reason: {self.reason}"
        return "\n\n".join(candidate.to_prompt_context() for candidate in self.candidates)


class NetworkSynthesisSelector:
    """Select graph neighborhoods where new information changes the corpus network.

    This is intentionally lightweight: it uses tag bridges and local graph expansion
    already present in GraphDB. The selector favors changed nodes that attach to
    existing neighborhoods, dense new edges, and source diversity.
    """

    def __init__(
        self,
        min_nodes: int | None = None,
        trigger_score: float | None = None,
        max_candidate_nodes: int | None = None,
    ) -> None:
        self.min_nodes = min_nodes if min_nodes is not None else SETTINGS.dikiwi_network_min_nodes
        self.trigger_score = (
            trigger_score if trigger_score is not None else SETTINGS.dikiwi_network_trigger_score
        )
        self.max_candidate_nodes = (
            max_candidate_nodes
            if max_candidate_nodes is not None
            else SETTINGS.dikiwi_network_max_candidate_nodes
        )

    async def assess(
        self,
        ctx: "AgentContext",
        current_nodes: list[InformationNode],
        current_links: list[KnowledgeLink],
    ) -> GraphChangeAssessment:
        if not ctx.graph_db:
            return self._fallback_local_assessment(current_nodes, current_links, "GraphDB unavailable")

        if not current_nodes:
            return GraphChangeAssessment(False, "No current information nodes to attach to graph")

        current_node_ids = {node.id for node in current_nodes}
        candidates: list[SubgraphCandidate] = []
        seen_candidate_ids: set[str] = set()

        for tag in sorted({tag for node in current_nodes for tag in node.tags if tag}):
            tag_id = f"tag_{tag}"
            try:
                tag_neighbors = await ctx.graph_db.get_neighbors(
                    tag_id,
                    relation_type="has_tag",
                    direction="in",
                    limit=max(self.max_candidate_nodes * 3, 30),
                )
            except Exception as exc:
                logger.warning("[DIKIWI] Failed to inspect tag neighborhood %s: %s", tag, exc)
                continue

            info_neighbors = [node for node in tag_neighbors if node.get("type") == "information"]
            if not info_neighbors:
                continue
            await self._attach_properties(ctx, info_neighbors)

            ordered_nodes = self._rank_nodes(info_neighbors, current_node_ids)
            node_ids = [node["id"] for node in ordered_nodes[: self.max_candidate_nodes]]
            if tag_id not in node_ids:
                tag_node = {
                    "id": tag_id,
                    "type": "tag",
                    "label": tag,
                    "source": "dikiwi",
                    "created_at": "",
                }
                subgraph_nodes = [tag_node, *ordered_nodes[: self.max_candidate_nodes - 1]]
            else:
                subgraph_nodes = ordered_nodes[: self.max_candidate_nodes]
            node_ids = [node["id"] for node in subgraph_nodes]

            try:
                edges = await ctx.graph_db.get_edges_for_nodes(node_ids, limit=100)
            except Exception as exc:
                logger.warning("[DIKIWI] Failed to load subgraph edges for %s: %s", tag, exc)
                edges = [node["edge"] for node in tag_neighbors if node.get("edge")]

            candidate = self._build_candidate(
                anchor_id=tag_id,
                anchor_label=tag,
                anchor_type="tag",
                nodes=subgraph_nodes,
                edges=edges,
                changed_node_ids=current_node_ids,
                current_links=current_links,
            )
            if candidate.id in seen_candidate_ids:
                continue
            seen_candidate_ids.add(candidate.id)
            if len([n for n in candidate.nodes if n.get("type") == "information"]) >= self.min_nodes:
                candidates.append(candidate)

        if not candidates:
            return GraphChangeAssessment(
                False,
                "No tag neighborhood reached the minimum subgraph size",
                metrics={"requires_existing_information_neighbor": True},
            )

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        best_score = candidates[0].score
        has_existing_information = any(
            candidate.metrics.get("existing_information_neighbors", 0) > 0
            for candidate in candidates
        )
        triggered = best_score >= self.trigger_score and has_existing_information
        reason = (
            "Graph change crossed synthesis threshold"
            if triggered
            else (
                f"Best subgraph score {best_score:.2f} below threshold {self.trigger_score:.2f}"
                if best_score < self.trigger_score
                else "Subgraph has no existing information neighbor yet"
            )
        )
        return GraphChangeAssessment(
            triggered=triggered,
            reason=reason,
            score=best_score,
            candidates=candidates[:3],
            metrics={
                "candidate_count": len(candidates),
                "trigger_score": self.trigger_score,
                "min_nodes": self.min_nodes,
                "requires_existing_information_neighbor": True,
            },
        )

    def _fallback_local_assessment(
        self,
        current_nodes: list[InformationNode],
        current_links: list[KnowledgeLink],
        reason: str,
    ) -> GraphChangeAssessment:
        if len(current_nodes) < self.min_nodes:
            return GraphChangeAssessment(False, reason)

        node_dicts = [
            {
                "id": node.id,
                "type": "information",
                "label": node.content,
                "source": "current_drop",
                "properties": {
                    "tags": node.tags,
                    "domain": node.domain,
                    "concept": node.concept,
                },
            }
            for node in current_nodes[: self.max_candidate_nodes]
        ]
        edge_dicts = [
            {
                "id": f"local_{idx}",
                "source_node_id": link.source_id,
                "target_node_id": link.target_id,
                "relation_type": link.relation_type,
                "weight": link.strength,
                "source": "current_drop",
            }
            for idx, link in enumerate(current_links)
        ]
        score = len(current_nodes) + sum(link.strength for link in current_links)
        candidate = self._build_candidate(
            anchor_id="current_drop",
            anchor_label="current drop local subgraph",
            anchor_type="local",
            nodes=node_dicts,
            edges=edge_dicts,
            changed_node_ids={node.id for node in current_nodes},
            current_links=current_links,
        )
        candidate.score = score
        candidate.reason = f"{reason}; using current-drop bootstrap subgraph"
        return GraphChangeAssessment(
            triggered=score >= self.trigger_score,
            reason=(
                "Bootstrap local subgraph crossed synthesis threshold"
                if score >= self.trigger_score
                else f"{reason}; local score {score:.2f} below threshold {self.trigger_score:.2f}"
            ),
            score=score,
            candidates=[candidate],
            metrics={"fallback": True, "trigger_score": self.trigger_score},
        )

    def _build_candidate(
        self,
        *,
        anchor_id: str,
        anchor_label: str,
        anchor_type: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        changed_node_ids: set[str],
        current_links: list[KnowledgeLink],
    ) -> SubgraphCandidate:
        node_ids = {node.get("id") for node in nodes}
        changed_count = len(node_ids & changed_node_ids)
        existing_count = len([node for node in nodes if node.get("id") not in changed_node_ids])
        existing_information_count = len(
            [
                node
                for node in nodes
                if node.get("id") not in changed_node_ids and node.get("type") == "information"
            ]
        )
        source_count = len({_source_label(node) for node in nodes if node.get("type") == "information"})
        edge_count = len(edges)
        density = edge_count / max(len(nodes), 1)
        score = (
            changed_count * 2.0
            + min(existing_count, 10) * 0.45
            + source_count * 0.75
            + min(edge_count, 20) * 0.25
            + sum(link.strength for link in current_links) * 0.5
        )
        candidate_hash = hashlib.sha1(
            "|".join([anchor_id, *sorted(str(node_id) for node_id in node_ids)]).encode("utf-8")
        ).hexdigest()[:10]
        reason = (
            f"{changed_count} changed node(s), {existing_count} existing neighbor(s), "
            f"{edge_count} edge(s), {source_count} source cluster(s)"
        )
        return SubgraphCandidate(
            id=f"subgraph_{candidate_hash}",
            anchor_id=anchor_id,
            anchor_label=anchor_label,
            anchor_type=anchor_type,
            reason=reason,
            score=score,
            nodes=nodes,
            edges=edges,
            changed_node_ids=sorted(changed_node_ids),
            metrics={
                "changed_nodes": changed_count,
                "existing_neighbors": existing_count,
                "existing_information_neighbors": existing_information_count,
                "edge_count": edge_count,
                "source_count": source_count,
                "density": round(density, 3),
            },
        )

    @staticmethod
    def _rank_nodes(nodes: list[dict[str, Any]], current_node_ids: set[str]) -> list[dict[str, Any]]:
        return sorted(
            nodes,
            key=lambda node: (
                0 if node.get("id") in current_node_ids else 1,
                str(node.get("created_at") or ""),
            ),
        )

    async def _attach_properties(self, ctx: "AgentContext", nodes: list[dict[str, Any]]) -> None:
        if not ctx.graph_db:
            return
        for node in nodes:
            try:
                node["properties"] = await ctx.graph_db.get_node_properties(str(node.get("id", "")))
            except Exception:
                node["properties"] = {}


def candidate_nodes_to_information(candidates: list[SubgraphCandidate]) -> list[InformationNode]:
    """Convert selected information graph nodes into InformationNode objects."""
    converted: list[InformationNode] = []
    seen: set[str] = set()
    for candidate in candidates:
        for node in candidate.nodes:
            node_id = str(node.get("id", ""))
            if not node_id or node_id in seen or node.get("type") != "information":
                continue
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            converted.append(
                InformationNode(
                    id=node_id,
                    data_point_id=str(props.get("data_point_id", "")),
                    content=str(node.get("label", "")),
                    tags=list(props.get("tags", [])) if isinstance(props.get("tags"), list) else [],
                    info_type=str(props.get("info_type", "")),
                    domain=str(props.get("domain", "")),
                    concept=str(props.get("concept", "")),
                )
            )
            seen.add(node_id)
    return converted


def _source_label(node: dict[str, Any]) -> str:
    props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
    source_paths = props.get("source_paths") if isinstance(props, dict) else None
    if isinstance(source_paths, list) and source_paths:
        return str(source_paths[0])
    return str(node.get("source") or "unknown")
