<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# writer

## Purpose

Tests for the Obsidian writer layer. Validates note formatting, frontmatter generation, link resolution, and vault write operations.

## Key Files

| File | Description |
|------|-------------|
| `test_dikiwi_obsidian.py` | DikiwiObsidianWriter tests — note formatting, frontmatter, vault writes |

## For AI Agents

### Working In This Directory
- Writer tests verify Obsidian note formatting and vault write operations
- Frontmatter YAML formatting is tested for all DIKIWI levels
- Link resolution tests ensure `[[WikiLinks]]` point to valid notes

### Testing Requirements
- Run with: `pytest tests/writer/ -xvs`

## Dependencies

### Internal
- `aily/writer/` — Obsidian writer under test

<!-- MANUAL: -->
