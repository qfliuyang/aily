from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from aily.graph.db import GraphDB
from aily.llm.client import LLMClient
from aily.push.feishu import FeishuPusher
from aily.queue.db import QueueDB
from aily.writer.obsidian import ObsidianWriter

logger = logging.getLogger(__name__)


class DigestPipeline:
    def __init__(
        self,
        graph_db: GraphDB,
        queue_db: QueueDB,
        llm: LLMClient,
        writer: ObsidianWriter,
        pusher: FeishuPusher | None = None,
    ) -> None:
        self.graph_db = graph_db
        self.queue_db = queue_db
        self.llm = llm
        self.writer = writer
        self.pusher = pusher

    async def run(self, open_id: str = "") -> str:
        logger.info("DigestPipeline started")

        top_nodes = await self.graph_db.get_top_nodes_by_edge_count(hours=24, limit=10)
        collisions = await self.graph_db.get_collisions_within_hours(24, min_occurrences=2)
        nodes = await self.graph_db.get_nodes_within_hours(24)
        edges = await self.graph_db.get_edges_within_hours(24)
        nodes_count = len(nodes)
        edges_count = len(edges)
        logger.info(
            "Fetched graph data: %s nodes, %s edges, %s top nodes, %s collisions",
            nodes_count,
            edges_count,
            len(top_nodes),
            len(collisions),
        )

        collisions_with_urls: list[dict[str, Any]] = []
        for collision in collisions:
            node_id = collision["node_id"]
            source_logs = await self.graph_db.get_source_logs_for_node(node_id, hours=24)
            raw_log_ids = [log["raw_log_id"] for log in source_logs]
            url_map = await self.queue_db.get_urls_for_raw_logs(raw_log_ids)
            source_urls = list(url_map.values())
            collision_data = dict(collision)
            collision_data["source_urls"] = source_urls
            collisions_with_urls.append(collision_data)
        logger.info("Resolved source URLs for %s collisions", len(collisions_with_urls))

        payload = {
            "overview": {
                "nodes_count": nodes_count,
                "edges_count": edges_count,
            },
            "top_nodes": top_nodes,
            "collisions": collisions_with_urls,
        }

        system_prompt = (
            "You are Aily, a personal knowledge assistant. Curate a concise daily digest "
            "markdown note from the past 24h of activity. Use sections: ## Overview, "
            "## Top Entities, ## Collisions / Connections, ## Raw Activity. Be concise "
            "but insightful. Link to source URLs where available."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        logger.info("Calling LLM to generate digest markdown")
        markdown = await self.llm.chat(messages, temperature=0.7)
        logger.info("LLM returned markdown (%s chars)", len(markdown))

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        title = f"Aily Daily Digest {today}"

        note_path = await self.writer.write_note(title, markdown, source_url="")
        logger.info("Obsidian note written: %s", note_path)

        if open_id and self.pusher is not None:
            summary = (
                f"Your daily digest is ready with {nodes_count} entities and "
                f"{len(collisions)} collisions."
            )
            try:
                success = await self.pusher.send_message(open_id, summary)
                logger.info("Feishu push sent: %s", success)
            except Exception:
                logger.exception("Feishu push failed, continuing pipeline")

        logger.info("DigestPipeline finished")
        return note_path
