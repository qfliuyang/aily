<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# writer

## Purpose

Obsidian vault output layer. Writes DIKIWI stage notes, generic notes, and Zettelkasten hub notes to the Obsidian vault via the Local REST API or direct filesystem. All vault file naming, frontmatter, and linking logic lives here.

## Key Files

| File | Description |
|------|-------------|
| `dikiwi_obsidian.py` | `DikiwiObsidianWriter` — writes all 6 DIKIWI stage notes with proper frontmatter and wikilinks |
| `obsidian.py` | `ObsidianWriter` — generic REST API wrapper for Obsidian vault |
| `zettelkasten.py` | Zettelkasten index and hub note management |

## For AI Agents

### Working In This Directory
- All DIKIWI notes go through `DikiwiObsidianWriter`
- Notes are written to numbered folders: `01-Data/` through `06-Impact/`
- Filename format: `{dikiwi_id}-{slugified_title}.md`
- Wikilinks use full filename: `[[id-title]]` not `[[title]]`
- Frontmatter is YAML with `dikiwi_id`, `aliases`, `tags`, type-specific fields

### Testing Requirements
- `tests/writer/` covers obsidian integration
- `tests/e2e/` validates vault output quality

### Common Patterns
- `_write_dikiwi_note()` is the core write method
- `_make_link(note_id, display)` builds wikilinks
- `_extract_chunk_title()` extracts meaningful titles from raw chunks
- HTML entities decoded via `html.unescape()` before writing

## Dependencies

### Internal
- `aily/config.py` — vault path from SETTINGS

### External
- `python-frontmatter` — YAML frontmatter handling

<!-- MANUAL: -->
