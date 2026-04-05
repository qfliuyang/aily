import json
import uuid
from pathlib import Path
from typing import Optional

import aiosqlite


class QueueDB:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','running','completed','failed')),
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at)"
            )
            await db.commit()

    async def enqueue(self, job_type: str, payload: dict) -> str:
        job_id = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO jobs (id, type, payload, status) VALUES (?, ?, ?, ?)",
                (job_id, job_type, json.dumps(payload), "pending"),
            )
            await db.commit()
        return job_id

    async def dequeue(self) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                "SELECT id, type, payload, retry_count FROM jobs WHERE status = ? ORDER BY created_at LIMIT 1",
                ("pending",),
            )
            row = await cursor.fetchone()
            if row is None:
                await db.commit()
                return None
            job_id, job_type, payload, retry_count = row
            await db.execute(
                "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                ("running", job_id),
            )
            await db.commit()
            return {
                "id": job_id,
                "type": job_type,
                "payload": json.loads(payload),
                "status": "running",
                "retry_count": retry_count,
            }

    async def complete_job(self, job_id: str, success: bool, error_message: Optional[str] = None) -> None:
        status = "completed" if success else "failed"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, error_message, job_id),
            )
            await db.commit()

    async def get_job(self, job_id: str) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, type, payload, status, retry_count, error_message FROM jobs WHERE id = ?",
                (job_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "type": row[1],
                "payload": json.loads(row[2]),
                "status": row[3],
                "retry_count": row[4],
                "error_message": row[5],
            }

    async def retry_job(self, job_id: str, max_retries: int = 3) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT retry_count FROM jobs WHERE id = ?", (job_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return False
            retry_count = row[0] + 1
            if retry_count >= max_retries:
                await db.execute(
                    "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    ("failed", job_id),
                )
            else:
                await db.execute(
                    "UPDATE jobs SET retry_count = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (retry_count, "pending", job_id),
                )
            await db.commit()
            return retry_count < max_retries
