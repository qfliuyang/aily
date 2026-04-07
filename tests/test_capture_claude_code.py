import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from aily.capture.claude_code import (
    ClaudeCodeSessionCapture,
    TranscriptEntry,
    SessionMetadata,
)


@pytest.fixture
def capture(tmp_path):
    return ClaudeCodeSessionCapture(
        transcripts_dir=tmp_path / "transcripts",
        sessions_dir=tmp_path / "sessions",
    )


@pytest.fixture
def sample_transcript(tmp_path):
    """Create a sample transcript file."""
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir()

    transcript_file = transcripts_dir / "ses_test123.jsonl"
    entries = [
        {
            "type": "user",
            "timestamp": "2026-03-16T16:44:55.161Z",
            "content": "Hello, can you help me with this code?",
        },
        {
            "type": "assistant",
            "timestamp": "2026-03-16T16:44:56.161Z",
            "content": "I'd be happy to help! What would you like to know?",
        },
        {
            "type": "tool_use",
            "timestamp": "2026-03-16T16:44:57.161Z",
            "tool_name": "read",
            "tool_input": {"filePath": "/path/to/file.py"},
        },
        {
            "type": "tool_result",
            "timestamp": "2026-03-16T16:44:58.161Z",
            "content": "file content here",
            "tool_output": {"preview": "file content"},
        },
    ]

    with open(transcript_file, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    return transcript_file


@pytest.mark.asyncio
async def test_scan_sessions_finds_new_files(capture, tmp_path, sample_transcript):
    sessions = await capture.scan_sessions(since=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert len(sessions) == 1
    assert sessions[0].session_id == "test123"


@pytest.mark.asyncio
async def test_scan_sessions_respects_since(capture, tmp_path, sample_transcript):
    # Set since to far future to exclude the sample
    future = datetime(2030, 1, 1, tzinfo=timezone.utc)
    sessions = await capture.scan_sessions(since=future)
    assert len(sessions) == 0


@pytest.mark.asyncio
async def test_parse_session(capture, sample_transcript):
    entries = await capture.parse_session(sample_transcript)
    assert len(entries) == 4

    # Check user message
    assert entries[0].type == "user"
    assert entries[0].content == "Hello, can you help me with this code?"

    # Check assistant message
    assert entries[1].type == "assistant"
    assert "happy to help" in entries[1].content

    # Check tool use
    assert entries[2].type == "tool_use"
    assert entries[2].tool_name == "read"

    # Check tool result
    assert entries[3].type == "tool_result"
    assert entries[3].content == "file content here"


@pytest.mark.asyncio
async def test_format_as_markdown(capture, sample_transcript):
    entries = await capture.parse_session(sample_transcript)
    metadata = SessionMetadata(
        session_id="test123",
        project="/Users/luzi/code/test",
        started_at=datetime(2026, 3, 16, 16, 44, 55, tzinfo=timezone.utc),
        file_path=sample_transcript,
    )

    markdown = await capture.format_as_markdown(entries, metadata)

    # Check frontmatter
    assert "aily_generated: true" in markdown
    assert "aily_source: claude_code_session" in markdown
    assert "session_id: test123" in markdown
    assert "project: /Users/luzi/code/test" in markdown

    # Check title
    assert "Claude Code Session: /Users/luzi/code/test" in markdown

    # Check summary
    assert "User messages" in markdown
    assert "Assistant messages" in markdown

    # Check conversation
    assert "### User" in markdown
    assert "### Claude" in markdown
    assert "Hello, can you help me with this code?" in markdown


@pytest.mark.asyncio
async def test_extract_session_id(capture):
    assert capture._extract_session_id("ses_abc123.jsonl") == "abc123"
    # Handles dots in session ID (extracts everything between ses_ and .jsonl)
    assert capture._extract_session_id("ses_abc123.def456.jsonl") == "abc123.def456"
    assert capture._extract_session_id("other.jsonl") == "other.jsonl"


@pytest.mark.asyncio
async def test_get_session_title(capture):
    entries = [
        TranscriptEntry(
            type="user",
            timestamp=datetime.now(timezone.utc),
            content="This is a very long message that should be truncated for the title",
        ),
        TranscriptEntry(
            type="assistant",
            timestamp=datetime.now(timezone.utc),
            content="Response",
        ),
    ]

    title = await capture.get_session_title(entries)
    assert len(title) <= 64  # 60 + "..."
    assert "..." in title


@pytest.mark.asyncio
async def test_parse_entry_skips_system_reminders(capture):
    """System reminders should be handled gracefully."""
    entries = [
        TranscriptEntry(
            type="assistant",
            timestamp=datetime.now(timezone.utc),
            content="<system-reminder>Some system message</system-reminder>",
        ),
    ]

    metadata = SessionMetadata(
        session_id="test",
        project=None,
        started_at=datetime.now(timezone.utc),
        file_path=Path("/tmp/test.jsonl"),
    )

    markdown = await capture.format_as_markdown(entries, metadata)
    # System reminders should not appear in output
    assert "system-reminder" not in markdown


@pytest.mark.asyncio
async def test_parse_session_handles_invalid_json(capture, tmp_path):
    """Should skip invalid JSON lines and continue."""
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir()

    transcript_file = transcripts_dir / "ses_bad.jsonl"
    transcript_file.write_text(
        '{"type": "user", "timestamp": "2026-03-16T16:44:55.161Z", "content": "valid"}\n'
        "not valid json\n"
        '{"type": "assistant", "timestamp": "2026-03-16T16:44:56.161Z", "content": "also valid"}\n'
    )

    entries = await capture.parse_session(transcript_file)
    assert len(entries) == 2
    assert entries[0].content == "valid"
    assert entries[1].content == "also valid"
