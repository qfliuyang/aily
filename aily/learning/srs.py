from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)


class SRSScheduler:
    """Spaced Repetition Scheduler based on Ebbinghaus forgetting curve.

    Review schedule:
    - Initial review: 1 day after creation
    - If successful: next review at 3 days
    - If successful: next review at 7 days
    - If successful: next review at 21 days
    - If successful: next review at 60 days (mature)
    - If failed: reset to 1 day
    """

    # Ebbinghaus-based review intervals in days
    INTERVALS = [1, 3, 7, 21, 60]

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    async def initialize(self) -> None:
        """Create the review queue table."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS review_queue (
                    note_id TEXT PRIMARY KEY,
                    current_interval_days INTEGER DEFAULT 1,
                    next_review_date TIMESTAMP,
                    review_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_queue_next_review ON review_queue(next_review_date)"
            )
            await db.commit()

    async def schedule_note(self, note_id: str, initial_interval: int = 1) -> None:
        """Add a note to the review queue.

        Args:
            note_id: Unique identifier for the note
            initial_interval: Days until first review (default: 1)
        """
        next_review = datetime.now(timezone.utc) + timedelta(days=initial_interval)
        logger.info("Scheduling note %s for review in %d days", note_id, initial_interval)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO review_queue
                (note_id, current_interval_days, next_review_date, review_count)
                VALUES (?, ?, ?, 0)
                """,
                (note_id, initial_interval, next_review.isoformat()),
            )
            await db.commit()

    async def get_due_notes(self) -> list[str]:
        """Return note_ids where next_review_date <= now."""
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT note_id FROM review_queue WHERE next_review_date <= ?",
                (now,),
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def record_review(self, note_id: str, success: bool) -> None:
        """Update interval based on review success.

        Args:
            note_id: The note being reviewed
            success: Whether the user successfully recalled the content
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT current_interval_days, review_count FROM review_queue WHERE note_id = ?",
                (note_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return

            current_interval, review_count = row

            if success:
                # Find next interval in the sequence
                try:
                    current_index = self.INTERVALS.index(current_interval)
                    next_index = min(current_index + 1, len(self.INTERVALS) - 1)
                    new_interval = self.INTERVALS[next_index]
                except ValueError:
                    # Interval not in standard list, default to 1
                    new_interval = self.INTERVALS[0]
                new_review_count = review_count + 1
            else:
                # Reset to first interval on failure
                new_interval = self.INTERVALS[0]
                new_review_count = 0

            next_review = datetime.now(timezone.utc) + timedelta(days=new_interval)

            await db.execute(
                """
                UPDATE review_queue
                SET current_interval_days = ?,
                    next_review_date = ?,
                    review_count = ?
                WHERE note_id = ?
                """,
                (new_interval, next_review.isoformat(), new_review_count, note_id),
            )
            await db.commit()
            logger.info(
                "Review recorded for %s: success=%s, new_interval=%d days, count=%d",
                note_id, success, new_interval, new_review_count
            )

    async def get_next_review(self, note_id: str) -> datetime | None:
        """Get the next scheduled review date for a note."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT next_review_date FROM review_queue WHERE note_id = ?",
                (note_id,),
            )
            row = await cursor.fetchone()
            if row is None or row[0] is None:
                return None
            return datetime.fromisoformat(row[0])

    async def schedule_from_digest(self, digest_note_path: str) -> None:
        """Read a digest note and schedule all atomic notes for review.

        Args:
            digest_note_path: Path to the digest markdown file
        """
        path = Path(digest_note_path)
        if not path.exists():
            return

        content = path.read_text(encoding="utf-8")

        # Extract atomic note references from the digest
        # Look for patterns like [[note_id]] or note links
        import re

        # Match [[note_name]] or [label](path) patterns
        wiki_links = re.findall(r"\[\[([^\]]+)\]\]", content)
        md_links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)

        # Schedule unique note references
        scheduled = set()

        for link in wiki_links:
            note_id = link.strip()
            if note_id and note_id not in scheduled:
                await self.schedule_note(note_id)
                scheduled.add(note_id)

        for label, link_path in md_links:
            # Extract note_id from path (e.g., "notes/my_note.md" -> "my_note")
            note_id = Path(link_path).stem
            if note_id and note_id not in scheduled:
                await self.schedule_note(note_id)
                scheduled.add(note_id)

    async def get_note_stats(self, note_id: str) -> dict | None:
        """Get review statistics for a note."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT current_interval_days, next_review_date, review_count, created_at
                FROM review_queue WHERE note_id = ?
                """,
                (note_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return {
                "note_id": note_id,
                "current_interval_days": row[0],
                "next_review_date": datetime.fromisoformat(row[1]) if row[1] else None,
                "review_count": row[2],
                "created_at": datetime.fromisoformat(row[3]) if row[3] else None,
            }

    async def remove_note(self, note_id: str) -> None:
        """Remove a note from the review queue."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM review_queue WHERE note_id = ?", (note_id,))
            await db.commit()
            logger.info("Removed note %s from review queue", note_id)
