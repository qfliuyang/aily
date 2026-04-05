from __future__ import annotations

from pathlib import Path
from typing import Optional

import aiosqlite


class GraphDB:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type)"
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    source_node_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_node_id) REFERENCES nodes(id) ON DELETE CASCADE
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_source_target ON edges(source_node_id, target_node_id)"
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS occurrences (
                    id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    raw_log_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_occurrences_node ON occurrences(node_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_occurrences_log ON occurrences(raw_log_id)"
            )
            await db.commit()

    async def _execute(self, sql: str, params: tuple | None = None) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(sql, params or ())
            await db.commit()

    async def _fetchall(self, sql: str, params: tuple | None = None) -> list[tuple]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, params or ())
            return await cursor.fetchall()

    async def insert_node(self, node_id: str, node_type: str, label: str, source: str) -> None:
        await self._execute(
            "INSERT OR IGNORE INTO nodes (id, type, label, source) VALUES (?, ?, ?, ?)",
            (node_id, node_type, label, source),
        )

    async def insert_edge(
        self,
        edge_id: str,
        source_node_id: str,
        target_node_id: str,
        relation_type: str,
        weight: float,
        source: str,
    ) -> None:
        await self._execute(
            """
            INSERT OR IGNORE INTO edges
            (id, source_node_id, target_node_id, relation_type, weight, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (edge_id, source_node_id, target_node_id, relation_type, weight, source),
        )

    async def insert_occurrence(self, occurrence_id: str, node_id: str, raw_log_id: str) -> None:
        await self._execute(
            "INSERT INTO occurrences (id, node_id, raw_log_id) VALUES (?, ?, ?)",
            (occurrence_id, node_id, raw_log_id),
        )

    async def get_nodes_by_type(self, node_type: str) -> list[dict]:
        rows = await self._fetchall(
            "SELECT id, type, label, source, created_at FROM nodes WHERE type = ?",
            (node_type,),
        )
        return [
            {
                "id": row[0],
                "type": row[1],
                "label": row[2],
                "source": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    async def get_cooccurring_nodes(self, raw_log_id: str) -> list[dict]:
        rows = await self._fetchall(
            """
            SELECT n.id, n.type, n.label, n.source, n.created_at
            FROM nodes n
            JOIN occurrences o ON n.id = o.node_id
            WHERE o.raw_log_id = ?
            """,
            (raw_log_id,),
        )
        return [
            {
                "id": row[0],
                "type": row[1],
                "label": row[2],
                "source": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]
