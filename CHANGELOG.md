# Changelog

All notable changes to Aily will be documented in this file.

## [0.1.0.0] - 2026-04-05

### Added
- Week 1 reactive pipeline: Feishu bot webhook → SQLite queue → Browser Use fetcher → Obsidian writer
- FastAPI webhook endpoint at `/webhook/feishu` with HMAC signature verification and event deduplication
- SQLite job queue (`QueueDB`) with enqueue, dequeue, retry, and completion tracking
- `BrowserFetcher` using Playwright with serialized access via `asyncio.Semaphore(1)`
- `ObsidianWriter` integrating with Obsidian Local REST API, writing to `Aily Drafts/` with `aily_generated` frontmatter
- `FeishuPusher` for sending confirmation messages back to users
- Parser registry with URL-pattern detection for Kimi, Monica, arXiv, GitHub, YouTube, and generic fallback
- `JobWorker` async background worker for processing queued URL fetch jobs
- pytest-asyncio test suite covering webhook handling, queue operations, browser fetching, Obsidian writing, and end-to-end pipeline flow
- Week 2 implementation plan (`.omc/plans/week2.md`) covering BrowserUseManager subprocess queue, passive capture scheduler, entity graph schema, URL dedup hash, and LLM client wrapper
