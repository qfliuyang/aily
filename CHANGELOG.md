# Changelog

All notable changes to Aily will be documented in this file.

## [0.2.0.0] - 2026-04-05

### Added
- BrowserUseManager with dedicated subprocess worker for serialized Playwright access via multiprocessing.connection IPC
- BrowserFetcher facade with start/stop lifecycle delegation
- PassiveCaptureScheduler with APScheduler, 0-60s jitter, exponential backoff up to 30 min, and macOS alert after 24h of failures
- SQLite entity graph schema (GraphDB) with nodes, edges, and occurrences tables in WAL mode
- LLMClient wrapper with 60s timeout, 1 retry, and json-repair fallback for malformed JSON
- SHA256 URL dedup hash in raw_ingestion_log with IntegrityError-based duplicate detection
- URL dedup check in Feishu webhook and passive capture enqueue paths
- Comprehensive test coverage for scheduler, browser manager, subprocess worker, graph DB, LLM client, and URL dedup

### Changed
- Aily main process lifecycle now initializes GraphDB and starts/stops the passive capture scheduler
- Exception handling in passive capture broadened to ensure backoff applies to all enqueue failures

### Fixed
- BrowserUseManager.stop() now uses asyncio timeouts to prevent hanging during subprocess shutdown
- Subprocess worker defensively closes Playwright page and browser contexts to prevent resource leaks
- Scheduler jobs limited to max_instances=1 to prevent overlapping executions under backpressure
- Requirements pinned to avoid breaking changes from APScheduler 4.x

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

### Fixed
- Escape `source_url` in Obsidian frontmatter to prevent malformed YAML from URLs containing quotes
- Sanitize note titles to block `..` path traversal in `ObsidianWriter._file_path`
