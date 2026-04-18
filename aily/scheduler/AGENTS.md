<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# scheduler

## Purpose

APScheduler-based job scheduling. Runs periodic tasks: passive content capture, daily digests, and Claude session capture.

## Key Files

| File | Description |
|------|-------------|
| `jobs.py` | `PassiveCaptureScheduler`, digest scheduler, and job definitions |

## For AI Agents

### Working In This Directory
- Schedulers are started in `main.py` lifespan
- `PassiveCaptureScheduler` polls for new content with backoff on failure
- Digest scheduler runs daily at a configurable time
- All schedulers use `AsyncIOScheduler`

### Common Patterns
- Exponential backoff for failed capture attempts
- Jitter added to intervals to avoid thundering herd
- Cron triggers for daily tasks, interval triggers for polling

## Dependencies

### Internal
- `aily/queue/` — Enqueues capture jobs
- `aily/digest/` — Runs digest pipeline
- `aily/capture/` — Claude session capture

### External
- `apscheduler` — Scheduling framework

<!-- MANUAL: -->
