from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class TranscriptEntry:
    type: str  # user, assistant, tool_use, tool_result, system
    timestamp: datetime
    content: str
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: dict | None = None


@dataclass
class SessionMetadata:
    session_id: str
    project: str | None
    started_at: datetime
    file_path: Path


class ClaudeCodeSessionCapture:
    """Scans and parses Claude Code session transcripts from ~/.claude/transcripts/"""

    def __init__(
        self,
        transcripts_dir: Path | None = None,
        sessions_dir: Path | None = None,
    ) -> None:
        self.transcripts_dir = transcripts_dir or Path.home() / ".claude" / "transcripts"
        self.sessions_dir = sessions_dir or Path.home() / ".claude" / "sessions"

    async def scan_sessions(
        self,
        since: datetime | None = None,
        project_filter: str | None = None,
    ) -> list[SessionMetadata]:
        """Scan for session transcript files modified since the given time."""
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        sessions: list[SessionMetadata] = []

        if not self.transcripts_dir.exists():
            logger.warning("Transcripts directory not found: %s", self.transcripts_dir)
            return sessions

        for transcript_file in self.transcripts_dir.glob("ses_*.jsonl"):
            try:
                stat = transcript_file.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

                if mtime >= since:
                    # Try to extract project info from first entry
                    project = await self._extract_project(transcript_file)

                    if project_filter and project != project_filter:
                        continue

                    session_id = self._extract_session_id(transcript_file.name)
                    sessions.append(
                        SessionMetadata(
                            session_id=session_id,
                            project=project,
                            started_at=mtime,
                            file_path=transcript_file,
                        )
                    )
            except Exception:
                logger.exception("Failed to process transcript: %s", transcript_file)
                continue

        # Sort by started_at descending (newest first)
        sessions.sort(key=lambda s: s.started_at, reverse=True)
        return sessions

    async def parse_session(self, file_path: Path) -> list[TranscriptEntry]:
        """Parse a transcript JSONL file into entries."""
        entries: list[TranscriptEntry] = []

        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            logger.exception("Failed to read transcript: %s", file_path)
            return entries

        for line_num, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                entry = self._parse_entry(data)
                if entry:
                    entries.append(entry)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON at line %d in %s", line_num, file_path)
                continue

        return entries

    async def format_as_markdown(
        self,
        entries: list[TranscriptEntry],
        metadata: SessionMetadata,
    ) -> str:
        """Format transcript entries as a markdown note."""
        lines: list[str] = []

        # Frontmatter
        lines.append("---")
        lines.append(f"aily_generated: true")
        lines.append(f"aily_source: claude_code_session")
        lines.append(f"session_id: {metadata.session_id}")
        if metadata.project:
            lines.append(f"project: {metadata.project}")
        lines.append(f"session_date: {metadata.started_at.strftime('%Y-%m-%d')}")
        lines.append("---")
        lines.append("")

        # Title
        project_name = metadata.project or "Unknown Project"
        date_str = metadata.started_at.strftime("%Y-%m-%d")
        lines.append(f"# Claude Code Session: {project_name} ({date_str})")
        lines.append("")

        # Summary stats
        user_msgs = sum(1 for e in entries if e.type == "user")
        assistant_msgs = sum(1 for e in entries if e.type == "assistant")
        tool_calls = sum(1 for e in entries if e.type == "tool_use")

        lines.append("## Summary")
        lines.append(f"- **User messages**: {user_msgs}")
        lines.append(f"- **Assistant messages**: {assistant_msgs}")
        lines.append(f"- **Tool calls**: {tool_calls}")
        lines.append("")

        # Conversation
        lines.append("## Conversation")
        lines.append("")

        current_tool: TranscriptEntry | None = None

        for entry in entries:
            time_str = entry.timestamp.strftime("%H:%M:%S")

            if entry.type == "user":
                lines.append(f"### User ({time_str})")
                lines.append("")
                lines.append(entry.content)
                lines.append("")

            elif entry.type == "assistant":
                # Skip empty assistant messages or system reminders
                if not entry.content or entry.content.startswith("<system-reminder>"):
                    continue
                lines.append(f"### Claude ({time_str})")
                lines.append("")
                lines.append(entry.content)
                lines.append("")

            elif entry.type == "tool_use":
                current_tool = entry
                tool_name = entry.tool_name or "unknown"
                lines.append(f"**Tool Use**: `{tool_name}`")
                lines.append("")

            elif entry.type == "tool_result":
                if current_tool:
                    tool_name = current_tool.tool_name or "unknown"
                    lines.append(f"**Tool Result** from `{tool_name}`:")
                    # Truncate long outputs
                    output = entry.content[:500]
                    if len(entry.content) > 500:
                        output += "\n... (truncated)"
                    lines.append(f"```\n{output}\n```")
                    lines.append("")
                current_tool = None

        return "\n".join(lines)

    def _extract_session_id(self, filename: str) -> str:
        """Extract session ID from filename like 'ses_xxx.jsonl'."""
        match = re.match(r"ses_(.+)\.jsonl$", filename)
        if match:
            return match.group(1)
        return filename

    async def _extract_project(self, file_path: Path) -> str | None:
        """Extract project path from first entry in transcript."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        # Look for project in various locations
                        if "project" in data:
                            return data["project"]
                        if "cwd" in data:
                            return data["cwd"]
                        # Check in tool_input or tool_output
                        for key in ["tool_input", "tool_output"]:
                            if key in data and isinstance(data[key], dict):
                                nested = data[key]
                                if "project" in nested:
                                    return nested["project"]
                                if "cwd" in nested:
                                    return nested["cwd"]
                    except json.JSONDecodeError:
                        continue
                    break  # Only check first valid entry
        except Exception:
            pass
        return None

    def _parse_entry(self, data: dict) -> TranscriptEntry | None:
        """Parse a single JSON line into a TranscriptEntry."""
        entry_type = data.get("type", "unknown")
        timestamp_str = data.get("timestamp", "")
        content = data.get("content", "")

        # Parse timestamp
        try:
            if timestamp_str:
                # Handle ISO format with Z suffix
                timestamp_str = timestamp_str.replace("Z", "+00:00")
                timestamp = datetime.fromisoformat(timestamp_str)
            else:
                timestamp = datetime.now(timezone.utc)
        except ValueError:
            timestamp = datetime.now(timezone.utc)

        # Map entry types
        if entry_type in ("user", "assistant"):
            return TranscriptEntry(
                type=entry_type,
                timestamp=timestamp,
                content=content,
            )
        elif entry_type == "tool_use":
            return TranscriptEntry(
                type="tool_use",
                timestamp=timestamp,
                content=content,
                tool_name=data.get("tool_name"),
                tool_input=data.get("tool_input"),
            )
        elif entry_type == "tool_result":
            return TranscriptEntry(
                type="tool_result",
                timestamp=timestamp,
                content=content,
                tool_output=data.get("tool_output"),
            )
        elif entry_type == "system":
            return TranscriptEntry(
                type="system",
                timestamp=timestamp,
                content=content,
            )

        return None

    async def get_session_title(self, entries: list[TranscriptEntry]) -> str:
        """Generate a title from the first user message."""
        for entry in entries:
            if entry.type == "user":
                # Truncate and clean
                title = entry.content[:60].replace("\n", " ")
                if len(entry.content) > 60:
                    title += "..."
                return title
        return "Claude Code Session"
