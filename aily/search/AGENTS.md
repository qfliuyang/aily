<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# search

## Purpose

Web search integration. Uses Tavily API for AI-optimized search results without browser automation.

## Key Files

| File | Description |
|------|-------------|
| `tavily.py` | `TavilySearch` — search client returning `SearchResult` list |

## For AI Agents

### Working In This Directory
- Tavily returns structured results with title, URL, content snippet, and relevance score
- Used by verification and research pipelines
- Requires `TAVILY_API_KEY` in environment

### Common Patterns
- `search(query, max_results=5)` — simple API
- Results include raw metadata for downstream processing
- Falls back to generic web search if Tavily unavailable

## Dependencies

### External
- `httpx` — HTTP client
- Tavily API key

<!-- MANUAL: -->
