# Changelog

All notable changes to Aily will be documented in this file.

## [0.5.0.0] - 2026-04-07

### Added
- **Week 2**: BrowserUseManager subprocess IPC, SQLite GraphDB schema (nodes/edges/occurrences), LLMClient, passive capture scheduler with backoff
- **Week 3**: GraphDB query engine with time-windowed reads, DigestPipeline for daily markdown digests, DailyDigestScheduler, job dispatcher for url_fetch and daily_digest
- **Week 4**: AgentRegistry and PlannerPipeline with multi-agent dispatch (summarizer, researcher, connector, zettel_suggester)
- **Week 5-6**: Learning Loop with Obsidian vault watching, snapshot tracking, LLM-driven diff extraction, preference persistence
- **Week 7-8**: Claude Code session capture, voice memo transcription (Feishu voice downloader + Whisper), Feishu voice webhook support
- **Week 9**: macOS DMG installer with LaunchAgent auto-start, keychain-based credential storage
- **Week 10**: Tailscale integration for remote access with status endpoint

### Changed
- Refactored job worker to support multiple job types (url_fetch, daily_digest, agent_request, voice_message, claude_session)
- Enhanced ObsidianWriter with draft folder support and aily_generated frontmatter
- Expanded test suite from 5 to 105 tests covering all new modules

### Infrastructure
- Added 16 new test modules covering graph DB, LLM client, voice processing, learning loop, and capture systems
- New modules: aily/network/, aily/learning/, aily/capture/, aily/voice/, aily/security/
- Installer scripts: installer/build-dmg.sh, install.sh, uninstall.sh

## [0.4.0.0] - 2026-04-06

### Added
- `AgentRegistry` for registering and dispatching named agents (`summarizer`, `researcher`, `connector`, `zettel_suggester`)
- `PlannerPipeline` that reads GraphDB context, prompts an LLM for a JSON execution plan, and runs agent steps sequentially
- `agent_request` job type routed through `JobWorker` with `_process_agent_job` in `main.py`
- Feishu webhook extension: non-URL text messages now enqueue `agent_request` jobs
- `aily/agent/` package with `registry.py`, `agents.py`, `pipeline.py`
- Comprehensive test coverage for agent registry, planner pipeline, dispatcher routing, and webhook text handling (77 tests total)

### Fixed
- SQL injection in `GraphDB` and `QueueDB` time-window queries replaced with Python-computed cutoff timestamps and parameterized queries

## [0.3.0.0] - 2026-04-05

### Added
- GraphDB query engine with time-windowed reads: `get_nodes_within_hours`, `get_edges_within_hours`, `get_top_nodes_by_edge_count`, `get_collisions_within_hours`, `get_source_logs_for_node`
- `created_at` indexes on nodes, edges, occurrences, and raw_ingestion_log for efficient time-range queries
- `DigestPipeline` that curates a daily markdown digest from 24h of graph activity using LLMClient, writes to Obsidian, and sends a Feishu summary
- `DailyDigestScheduler` with APScheduler `CronTrigger` for configurable daily digest enqueueing
- Job dispatcher in `main.py` supporting both `url_fetch` and `daily_digest` job types via `JobWorker`
- New settings: `llm_api_key`, `llm_base_url`, `llm_model`, `aily_digest_enabled`, `aily_digest_hour`, `aily_digest_minute`, `aily_digest_feishu_open_id`
- Comprehensive test coverage for graph queries, queue helpers, digest pipeline, daily scheduler, and job dispatcher (66 tests total)

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
- Week 1 reactive pipeline: Feishu bot webhook -> SQLite queue -> Browser Use fetcher -> Obsidian writer
- FastAPI webhook endpoint at `/webhook/feishu` with HMAC signature verification and event deduplication
- SQLite job queue (`QueueDB`) with enqueue, dequeue, retry, and completion tracking
- `BrowserFetcher` using Playwright with serialized access via `asyncio.Semaphore(1)`
- `ObsidianWriter` integrating with Obsidian Local REST API, writing to `Aily Drafts/` with `aily_generated` frontmatter
- `FeishuPusher` for sending confirmation messages back to users
- Parser registry with URL-pattern detection for Kimi, Monica, arXiv, GitHub, YouTube, and generic fallback
- `JobWorker` async background worker for processing queued URL fetch jobs
- pytest-asyncio test suite covering webhook handling, queue operations, browser fetching, Obsidian writing, and end-to-end pipeline flow
- Week 2 implementation plan (`.omc/plans/week2.md`) covering BrowserUseManager subprocess queue, passive capture scheduler, entity graph schema, URL dup hash, and LLM client wrapper

### Fixed
- Escape `source_url` in Obsidian frontmatter to prevent malformed YAML from URLs containing quotes
- Sanitize note titles to block `..` path traversal in `ObsidianWriter._file_path`
