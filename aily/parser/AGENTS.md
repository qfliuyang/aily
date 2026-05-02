<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# parser

## Purpose

URL content parsers. Detects URL patterns and applies domain-specific extraction logic for sites like Kimi, Monica, arXiv, GitHub, and YouTube.

## Key Files

| File | Description |
|------|-------------|
| `registry.py` | `register()`, `parse()` — pattern-matched parser dispatch |
| `parsers.py` | Domain-specific parsers: `parse_generic`, `parse_kimi`, `parse_arxiv`, etc. |

## For AI Agents

### Working In This Directory
- Add new parsers: `register(r'pattern', my_parser)` in `parsers.py`
- `ParseResult` is a dataclass with `title`, `content`, `metadata`
- Generic parser is the fallback for unmatched URLs

### Common Patterns
- Regex-based URL pattern matching
- Each parser receives `(url, raw_text)` and returns `ParseResult`
- Parsers may call external APIs (arXiv, GitHub) for enrichment

## Dependencies

### Internal
- `aily/browser/` — For pages requiring browser automation

### External
- `httpx` — HTTP requests for API-based parsers

<!-- MANUAL: -->
