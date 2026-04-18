<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# writer

## Purpose

Tests for the Obsidian writer layer. Validates note formatting, frontmatter generation, link resolution, and vault write operations.

## Key Files

| File | Description |
|------|-------------|
| *(tests within sessions/)* | Writer tests are co-located with session tests |

## For AI Agents

### Working In This Directory
- Writer tests verify Obsidian Local REST API integration
- Frontmatter YAML formatting is tested for all DIKIWI levels
- Link resolution tests ensure `[[WikiLinks]]` point to valid notes

### Testing Requirements
- Run with: `pytest tests/writer/ -xvs` (if tests are moved here)
- Currently, writer tests may be in `tests/sessions/`

## Dependencies

### Internal
- `aily/writer/` — Obsidian writer under test

<!-- MANUAL: -->
