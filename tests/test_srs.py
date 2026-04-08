import pytest
import aiosqlite
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aily.learning.srs import SRSScheduler


@pytest.fixture
async def scheduler(tmp_path):
    db_path = tmp_path / "test_srs.db"
    srs = SRSScheduler(db_path)
    await srs.initialize()
    return srs


@pytest.mark.asyncio
async def test_initialize_creates_table(scheduler):
    """Test that initialize creates the review_queue table."""
    # Table should exist after initialization - verify by inserting
    await scheduler.schedule_note("test_note")
    stats = await scheduler.get_note_stats("test_note")
    assert stats is not None


@pytest.mark.asyncio
async def test_schedule_note(scheduler):
    """Test scheduling a note for review."""
    await scheduler.schedule_note("note_1")

    stats = await scheduler.get_note_stats("note_1")
    assert stats is not None
    assert stats["current_interval_days"] == 1
    assert stats["review_count"] == 0
    assert stats["next_review_date"] is not None


@pytest.mark.asyncio
async def test_schedule_note_with_custom_interval(scheduler):
    """Test scheduling a note with custom initial interval."""
    await scheduler.schedule_note("note_1", initial_interval=7)

    stats = await scheduler.get_note_stats("note_1")
    assert stats["current_interval_days"] == 7


@pytest.mark.asyncio
async def test_get_due_notes_empty(scheduler):
    """Test getting due notes when none are due."""
    await scheduler.schedule_note("future_note", initial_interval=7)

    due_notes = await scheduler.get_due_notes()
    assert len(due_notes) == 0


@pytest.mark.asyncio
async def test_get_due_notes_with_due_items(scheduler):
    """Test getting due notes when some are due."""
    db_path = scheduler.db_path

    # Schedule a note that was due yesterday
    await scheduler.schedule_note("due_note", initial_interval=0)
    # Manually set next_review_date to past using direct connection
    past_date = datetime.now(timezone.utc) - timedelta(days=1)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE review_queue SET next_review_date = ? WHERE note_id = ?",
            (past_date.isoformat(), "due_note")
        )
        await db.commit()

    due_notes = await scheduler.get_due_notes()
    assert "due_note" in due_notes


@pytest.mark.asyncio
async def test_record_review_success_progression(scheduler):
    """Test interval progression on successful reviews."""
    await scheduler.schedule_note("note_1")

    # First successful review -> 3 days
    await scheduler.record_review("note_1", success=True)
    stats = await scheduler.get_note_stats("note_1")
    assert stats["current_interval_days"] == 3
    assert stats["review_count"] == 1

    # Second successful review -> 7 days
    await scheduler.record_review("note_1", success=True)
    stats = await scheduler.get_note_stats("note_1")
    assert stats["current_interval_days"] == 7
    assert stats["review_count"] == 2

    # Third successful review -> 21 days
    await scheduler.record_review("note_1", success=True)
    stats = await scheduler.get_note_stats("note_1")
    assert stats["current_interval_days"] == 21
    assert stats["review_count"] == 3

    # Fourth successful review -> 60 days
    await scheduler.record_review("note_1", success=True)
    stats = await scheduler.get_note_stats("note_1")
    assert stats["current_interval_days"] == 60
    assert stats["review_count"] == 4

    # Fifth successful review -> stays at 60 days (mature)
    await scheduler.record_review("note_1", success=True)
    stats = await scheduler.get_note_stats("note_1")
    assert stats["current_interval_days"] == 60
    assert stats["review_count"] == 5


@pytest.mark.asyncio
async def test_record_review_failure_reset(scheduler):
    """Test interval reset on failed review."""
    await scheduler.schedule_note("note_1")

    # Progress to 21 days
    await scheduler.record_review("note_1", success=True)  # 3 days
    await scheduler.record_review("note_1", success=True)  # 7 days
    await scheduler.record_review("note_1", success=True)  # 21 days

    stats = await scheduler.get_note_stats("note_1")
    assert stats["current_interval_days"] == 21

    # Failed review resets to 1 day
    await scheduler.record_review("note_1", success=False)
    stats = await scheduler.get_note_stats("note_1")
    assert stats["current_interval_days"] == 1
    assert stats["review_count"] == 0


@pytest.mark.asyncio
async def test_get_next_review(scheduler):
    """Test getting next review date."""
    await scheduler.schedule_note("note_1", initial_interval=3)

    next_review = await scheduler.get_next_review("note_1")
    assert next_review is not None
    assert isinstance(next_review, datetime)

    # Should be approximately 3 days from now
    now = datetime.now(timezone.utc)
    assert next_review > now + timedelta(days=2)
    assert next_review < now + timedelta(days=4)


@pytest.mark.asyncio
async def test_get_next_review_nonexistent(scheduler):
    """Test getting next review for non-existent note."""
    next_review = await scheduler.get_next_review("nonexistent")
    assert next_review is None


@pytest.mark.asyncio
async def test_schedule_from_digest_wiki_links(scheduler, tmp_path):
    """Test scheduling from digest with wiki-style links."""
    digest_path = tmp_path / "digest.md"
    digest_path.write_text("""
# Daily Digest

## Top Entities
- [[AI]] and [[Machine Learning]] are trending
- See also [[Python]]
""")

    await scheduler.schedule_from_digest(str(digest_path))

    assert await scheduler.get_next_review("AI") is not None
    assert await scheduler.get_next_review("Machine Learning") is not None
    assert await scheduler.get_next_review("Python") is not None


@pytest.mark.asyncio
async def test_schedule_from_digest_markdown_links(scheduler, tmp_path):
    """Test scheduling from digest with markdown links."""
    digest_path = tmp_path / "digest.md"
    digest_path.write_text("""
# Daily Digest

## Top Entities
- [Artificial Intelligence](notes/ai.md)
- [Machine Learning](ml_note.md)
""")

    await scheduler.schedule_from_digest(str(digest_path))

    assert await scheduler.get_next_review("ai") is not None
    assert await scheduler.get_next_review("ml_note") is not None


@pytest.mark.asyncio
async def test_schedule_from_digest_nonexistent_file(scheduler):
    """Test scheduling from non-existent digest file."""
    # Should not raise an error
    await scheduler.schedule_from_digest("/nonexistent/path/digest.md")

    due_notes = await scheduler.get_due_notes()
    assert len(due_notes) == 0


@pytest.mark.asyncio
async def test_remove_note(scheduler):
    """Test removing a note from the review queue."""
    await scheduler.schedule_note("note_1")
    assert await scheduler.get_next_review("note_1") is not None

    await scheduler.remove_note("note_1")
    assert await scheduler.get_next_review("note_1") is None


@pytest.mark.asyncio
async def test_multiple_notes_due(scheduler):
    """Test getting multiple due notes."""
    db_path = scheduler.db_path

    # Schedule notes with different review dates
    await scheduler.schedule_note("note_past", initial_interval=0)
    await scheduler.schedule_note("note_future", initial_interval=7)

    # Manually set note_past to be due yesterday
    now = datetime.now(timezone.utc)
    async with aiosqlite.connect(db_path) as db:
        past_date = now - timedelta(days=1)
        await db.execute(
            "UPDATE review_queue SET next_review_date = ? WHERE note_id = ?",
            (past_date.isoformat(), "note_past")
        )
        await db.commit()

    due_notes = await scheduler.get_due_notes()
    assert "note_past" in due_notes
    assert "note_future" not in due_notes


@pytest.mark.asyncio
async def test_note_stats_full(scheduler):
    """Test getting complete note statistics."""
    await scheduler.schedule_note("note_1", initial_interval=1)

    stats = await scheduler.get_note_stats("note_1")
    assert stats is not None
    assert stats["note_id"] == "note_1"
    assert stats["current_interval_days"] == 1
    assert stats["review_count"] == 0
    assert stats["next_review_date"] is not None
    assert stats["created_at"] is not None
