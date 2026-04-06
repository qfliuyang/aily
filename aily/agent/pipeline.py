from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from aily.agent.registry import AgentRegistry
from aily.graph.db import GraphDB
from aily.llm.client import LLMClient
from aily.push.feishu import FeishuPusher
from aily.writer.obsidian import ObsidianWriter

logger = logging.getLogger(__name__)


class PlannerPipeline:
    def __init__(
        self,
        graph_db: GraphDB,
        llm: LLMClient,
        registry: AgentRegistry,
        writer: ObsidianWriter,
        pusher: FeishuPusher | None = None,
    ) -> None:
        self.graph_db = graph_db
        self.llm = llm
        self.registry = registry
        self.writer = writer
        self.pusher = pusher

    async def run(self, request: str, open_id: str = "") -> str:
        logger.info("PlannerPipeline started for request: %s", request[:50])

        top_nodes = await self.graph_db.get_top_nodes_by_edge_count(hours=24, limit=10)
        collisions = await self.graph_db.get_collisions_within_hours(24, min_occurrences=2)

        graph_context = {
            "top_nodes": [
                {"label": n["label"], "type": n["type"], "edge_count": n["edge_count"]}
                for n in top_nodes
            ],
            "collisions": [
                {"label": c["label"], "type": c["type"], "occurrence_count": c["occurrence_count"]}
                for c in collisions
            ],
        }

        agents = self.registry.list_agents()
        agent_descriptions = "\n".join(
            f"- {a['name']}: {a['description']}" for a in agents
        )

        system_prompt = (
            "You are Aily's planner. The user has made a request. "
            "Choose from the available agents and produce a JSON plan.\n\n"
            f"Available agents:\n{agent_descriptions}\n\n"
            "Output a JSON object with this exact schema:\n"
            '{"steps": [{"agent": "name", "args": {"key": "value"}}]}\n'
            "Only use agents from the list above. If the request is unclear, "
            'return a single summarizer step with the request text.'
        )

        user_content = f"Request: {request}\n\nGraph context (last 24h):\n{json.dumps(graph_context, ensure_ascii=False)}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        plan: dict[str, Any] = {"steps": []}
        try:
            plan = await self.llm.chat_json(messages, temperature=0.3)
        except Exception:
            logger.exception("LLM plan generation failed, falling back")
            plan = {"steps": [{"agent": "summarizer", "args": {"text": request}}]}

        steps = plan.get("steps", [])
        if not isinstance(steps, list):
            logger.warning("Invalid plan steps format, falling back")
            steps = [{"agent": "summarizer", "args": {"text": request}}]

        context: dict[str, Any] = {
            "graph_db": self.graph_db,
            "request": request,
            "results": [],
        }

        for idx, step in enumerate(steps):
            agent_name = step.get("agent", "")
            args = step.get("args", {})
            if not isinstance(args, dict):
                args = {}
            try:
                agent_fn = self.registry.get(agent_name)
                result = await agent_fn(context, **args)
                context["results"].append({"agent": agent_name, "result": result, "status": "ok"})
                logger.info("Step %s (%s) succeeded", idx + 1, agent_name)
            except Exception:
                logger.exception("Step %s (%s) failed", idx + 1, agent_name)
                context["results"].append({"agent": agent_name, "result": "", "status": "failed"})

        markdown = self._render_markdown(context)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        title = f"Aily Agent Result {today}"

        note_path = await self.writer.write_note(title, markdown, source_url="")
        logger.info("Obsidian note written: %s", note_path)

        if open_id and self.pusher is not None:
            summary = (
                f"Agent pipeline finished with {len(steps)} steps. "
                f"Saved to Obsidian: {note_path}"
            )
            try:
                await self.pusher.send_message(open_id, summary)
                logger.info("Feishu push sent")
            except Exception:
                logger.exception("Feishu push failed, continuing pipeline")

        return note_path

    @staticmethod
    def _render_markdown(context: dict[str, Any]) -> str:
        lines = [
            f"## Request\n\n{context['request']}",
            "## Steps",
        ]
        for r in context["results"]:
            status = "✅" if r["status"] == "ok" else "❌"
            lines.append(f"\n### {status} {r['agent']}\n\n{r['result']}")
        return "\n".join(lines)
