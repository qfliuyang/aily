<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# capture

## Purpose

Captures Claude Code session transcripts and ingests them into the knowledge system. Monitors Claude Code's JSONL output files and converts conversation history into Obsidian notes.

## Key Files

| File | Description |
|------|-------------|
| `claude_code.py` | `ClaudeCodeCapture` — reads `.jsonl` session files, writes to vault |

## For AI Agents

### Working In This Directory
- Session files are typically at `~/.claude/projects/*/timeline.jsonl`
- Each session is converted to a dated note with metadata
- Captured sessions feed into the DIKIWI pipeline as raw inputs

### Common Patterns
- JSONL parsing: one JSON object per line
- File watcher for new session files
- Deduplication by session ID

## Dependencies

### Internal
- `aily/writer/` — Obsidian writer for output
- `aily/graph/` — GraphDB for session metadata

<!-- MANUAL: -->
