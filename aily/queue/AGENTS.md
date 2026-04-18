<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# queue

## Purpose

SQLite-based job queue with async worker. Enqueues background jobs (file processing, URL fetching, voice transcription) and dispatches them via `JobWorker`.

## Key Files

| File | Description |
|------|-------------|
| `db.py` | `QueueDB` — SQLite job store with pending/running/completed/failed states |
| `worker.py` | `JobWorker` — polls queue and dispatches to handlers |

## For AI Agents

### Working In This Directory
- Jobs have `type`, `payload` (JSON), `status`, `retry_count`
- Worker polls every few seconds, processes one job at a time
- Failed jobs are retried up to a max count, then marked failed

### Common Patterns
- `enqueue(type, payload)` — add job to queue
- `claim_next()` — atomic pick-up of pending job
- Handlers are registered by job type string
- Raw ingestion log tracks all processed items

## Dependencies

### External
- `aiosqlite` — Async SQLite

<!-- MANUAL: -->
