from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SourceStore:
    """Persistent raw source store for uploads, links, and future media inputs."""

    def __init__(self, db_path: Path, object_dir: Path) -> None:
        self.db_path = db_path.expanduser()
        self.object_dir = object_dir.expanduser()
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.object_dir.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                sha256 TEXT UNIQUE,
                normalized_source TEXT NOT NULL,
                storage_path TEXT,
                filename TEXT,
                content_type TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS source_uploads (
                upload_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                filename TEXT,
                content_type TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES sources(source_id)
            )
            """
        )
        await self._db.execute("CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status)")
        await self._db.execute("CREATE INDEX IF NOT EXISTS idx_sources_updated ON sources(updated_at)")
        await self._db.execute("CREATE INDEX IF NOT EXISTS idx_uploads_source ON source_uploads(source_id)")
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    def _check_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SourceStore not initialized")
        return self._db

    async def store_upload(
        self,
        *,
        upload_id: str,
        filename: str,
        content_type: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        db = self._check_db()
        digest = _sha256_bytes(data)
        source_id = f"sha256:{digest}"
        object_path = self.object_dir / digest[:2] / digest
        object_path.parent.mkdir(parents=True, exist_ok=True)
        if not object_path.exists():
            object_path.write_bytes(data)

        existing = await self.get_source(source_id)
        now = _utc_now()
        if existing is None:
            await db.execute(
                """
                INSERT INTO sources (
                    source_id, kind, sha256, normalized_source, storage_path,
                    filename, content_type, size_bytes, status, metadata,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    "upload",
                    digest,
                    filename,
                    str(object_path),
                    filename,
                    content_type,
                    len(data),
                    "stored",
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            duplicate = False
            status = "stored"
        else:
            duplicate = True
            status = str(existing["status"])

        await db.execute(
            """
            INSERT OR REPLACE INTO source_uploads (
                upload_id, source_id, filename, content_type, size_bytes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (upload_id, source_id, filename, content_type, len(data), now),
        )
        await db.commit()

        return {
            "source_id": source_id,
            "upload_id": upload_id,
            "sha256": digest,
            "storage_path": str(object_path),
            "filename": filename,
            "content_type": content_type,
            "size_bytes": len(data),
            "status": status,
            "duplicate": duplicate,
        }

    async def store_url(
        self,
        *,
        url: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        db = self._check_db()
        normalized_url = url.strip()
        digest = _sha256_bytes(normalized_url.encode("utf-8"))
        source_id = f"url:{digest}"
        now = _utc_now()
        existing = await self.get_source(source_id)
        if existing is None:
            await db.execute(
                """
                INSERT INTO sources (
                    source_id, kind, sha256, normalized_source, storage_path,
                    filename, content_type, size_bytes, status, metadata,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    "url",
                    digest,
                    normalized_url,
                    None,
                    None,
                    "text/uri-list",
                    len(normalized_url),
                    "stored",
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            await db.commit()
            duplicate = False
            status = "stored"
        else:
            duplicate = True
            status = str(existing["status"])
        return {
            "source_id": source_id,
            "url": normalized_url,
            "sha256": digest,
            "status": status,
            "duplicate": duplicate,
        }

    async def update_status(self, source_id: str, status: str, metadata: dict[str, Any] | None = None) -> None:
        db = self._check_db()
        existing = await self.get_source(source_id)
        if existing is None:
            return
        merged = dict(existing.get("metadata") or {})
        if metadata:
            merged.update(metadata)
        await db.execute(
            "UPDATE sources SET status = ?, metadata = ?, updated_at = ? WHERE source_id = ?",
            (status, json.dumps(merged, ensure_ascii=False), _utc_now(), source_id),
        )
        await db.commit()

    async def get_source(self, source_id: str) -> dict[str, Any] | None:
        db = self._check_db()
        cursor = await db.execute("SELECT * FROM sources WHERE source_id = ?", (source_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    async def get_source_for_upload(self, upload_id: str) -> dict[str, Any] | None:
        db = self._check_db()
        cursor = await db.execute(
            """
            SELECT s.*
            FROM source_uploads u
            JOIN sources s ON s.source_id = u.source_id
            WHERE u.upload_id = ?
            """,
            (upload_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    async def list_sources(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        db = self._check_db()
        safe_limit = min(max(1, limit), 500)
        safe_offset = max(0, offset)
        total_cursor = await db.execute("SELECT COUNT(*) AS count FROM sources")
        total = int((await total_cursor.fetchone())["count"])
        cursor = await db.execute(
            "SELECT * FROM sources ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (safe_limit, safe_offset),
        )
        rows = await cursor.fetchall()
        return {
            "total": total,
            "sources": [self._row_to_dict(row) for row in rows],
        }

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
        payload = dict(row)
        try:
            payload["metadata"] = json.loads(payload.get("metadata") or "{}")
        except json.JSONDecodeError:
            payload["metadata"] = {}
        return payload
