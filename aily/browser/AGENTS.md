<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# browser

## Purpose

Browser automation and web content extraction. Uses Playwright or browser-use agent to fetch pages, extract structured content, and run JavaScript for dynamic sites.

## Key Files

| File | Description |
|------|-------------|
| `manager.py` | `BrowserUseManager` — orchestrates browser subprocess/workers |
| `fetcher.py` | `BrowserFetcher` — simple page fetch + text extraction |
| `agent_worker.py` | Agent-based extraction for complex pages |
| `subprocess_worker.py` | Subprocess isolation for browser instances |
| `simple_extractor.py` | Lightweight extraction without full browser |

## For AI Agents

### Working In This Directory
- New extraction strategies: extend `BrowserFetcher` or add worker types
- Subprocess isolation prevents memory leaks from long-running browsers
- `simple_extractor.py` is the fast path for static HTML

### Common Patterns
- Manager spawns subprocess workers with `multiprocessing.connection`
- Auth key shared between parent and child process
- Profile directory for persistent cookies/sessions

## Dependencies

### Internal
- `aily/verify/` — Claim verifier uses fetcher to check sources

### External
- `playwright` — Browser automation
- `browser-use` — AI agent-based browsing

<!-- MANUAL: -->
