# Human-Drop Comprehensive Fix Plan

Generated: 2026-05-05

Based on:

- `docs/HUMAN_DROP_SOAK_REVIEW_AND_FIX_LIST.md`
- Evidence: `logs/runs/2026-05-04T17-19-01Z_studio_human_drop_soak_5h_tmux`

## Objective

Make Aily behave like a real second-brain service under human usage:

- A human can drop 1 file, 25 files, or repeated random batches.
- Upload/intake is fast and safe.
- Files are stored durably and never lost because the LLM/provider is slow.
- DIKIWI grows incrementally with backpressure.
- Proposal and Entrepreneurship output eventually catches up.
- Studio displays true queue, retry, active, failed, and completed state.
- Tests prove real behavior, not mocked success.

The 5-hour test proved that Aily can accept files but cannot yet operate as a
durable service. The central repair is to separate intake from cognition.

## Target Architecture

```text
Browser / API Drop
  -> SourceStore durable raw object
  -> Intake Job durable queue
  -> Extraction worker
  -> DIKIWI source queue
  -> DATA / INFORMATION workers
  -> graph-change scheduler
  -> KNOWLEDGE micro-batches
  -> INSIGHT / WISDOM / IMPACT affected-subgraph jobs
  -> Reactor proposal jobs
  -> Entrepreneur / Guru checkpointed jobs
  -> Vault filesystem writer
  -> Studio event stream + persistent status
```

Human batch ID is provenance only. It must not force simultaneous DIKIWI
execution.

## Non-Negotiable Acceptance Rules

- A timeout is not data loss.
- A dropped file is not `failed` unless extraction is impossible or retries are
  exhausted.
- A 25-file drop must become queued durable work, not 25 immediate LLM pipelines.
- Aily must work when Obsidian app is closed; vault filesystem writes are the
  default.
- Studio active state must come from durable non-terminal records, not stale
  memory or capped event history.
- Real acceptance must use real PDFs, real provider calls, real graph writes,
  real vault writes, and browser/API exercise of the real backend.

## Phase 0: Stop The Bleeding

Goal:
Prevent new human drops from being converted into permanent failure during
provider slowness.

Files:

- `aily/main.py`
- `aily/sessions/dikiwi_mind.py`
- `aily/source_store/store.py`
- `aily/config.py`
- `tests/test_studio_batch_business_flow.py`
- `tests/test_source_store.py`

Implementation:

1. Add retryable source statuses:
   `queued`, `retry_pending`, `deferred`, `failed_retry_exhausted`.
2. Change Studio batch timeout mapping:
   if a DIKIWI stage returns timeout or provider timeout, update source to
   `retry_pending`, not `failed`.
3. Add retry metadata:
   `last_failed_stage`, `last_error`, `attempt_count`, `next_retry_at`,
   `provider`, `model`, `pipeline_id`, `batch_id`.
4. Add config:
   `source_max_retry_attempts`, `source_retry_base_delay_seconds`,
   `source_retry_max_delay_seconds`.
5. Keep true terminal failure only for unsupported type, unreadable object,
   extraction corruption, or retry exhaustion.

Acceptance:

- Unit test: DATA timeout source becomes `retry_pending`.
- Unit test: unsupported file still becomes `failed`.
- Unit test: retry count increments and next retry is written.
- Real smoke: upload 3 PDFs with deliberately low stage timeout; sources become
  `retry_pending`, not `failed`.

Why first:
This immediately prevents further false loss while the durable queue is built.

## Phase 1: Durable Source Queue

Goal:
Move all Studio upload execution out of request handlers and into a durable
worker model.

Files:

- `aily/source_store/store.py`
- `aily/main.py`
- `aily/queue/db.py` or new `aily/source_store/work_queue.py`
- `aily/ui/router.py`
- `aily/ui/events.py`
- `tests/test_source_store.py`
- `tests/test_ui_router.py`

Implementation:

1. Add `source_jobs` table or extend existing source store:
   `job_id`, `source_id`, `job_type`, `status`, `priority`, `attempt_count`,
   `available_at`, `locked_by`, `locked_at`, `created_at`, `updated_at`,
   `last_error`.
2. Upload handler stores files and enqueues extraction jobs only.
3. Upload handler returns fast with `status=queued`.
4. Add worker loop:
   claim due jobs with transaction/lock, process, update, release.
5. Add job types:
   `extract_source`, `dikiwi_data_info`, `dikiwi_knowledge_batch`,
   `dikiwi_higher_order`, `reactor_evaluate`, `entrepreneur_evaluate`,
   `url_enrich`.
6. Add backend lifecycle startup/shutdown for source workers.

Acceptance:

- Restart backend with queued sources; work resumes.
- 25-file upload creates 25 queued jobs and no immediate DIKIWI burst.
- `/api/ui/status` shows queued count.
- No source stays in `stored` forever unless worker disabled.
- Source jobs are observable through Studio Operations.

## Phase 2: Global Backpressure And Provider Budgets

Goal:
Prevent DIKIWI, Reactor, GStack, URL enrichment, and schedulers from starving
each other.

Files:

- `aily/llm/client.py`
- `aily/llm/provider_routes.py`
- `aily/sessions/dikiwi_mind.py`
- `aily/sessions/reactor_scheduler.py`
- `aily/sessions/entrepreneur_scheduler.py`
- `aily/config.py`
- new `aily/runtime/backpressure.py`

Implementation:

1. Add global semaphores per provider and workload:
   `kimi`, `deepseek`, `dikiwi.data`, `dikiwi.higher_order`,
   `reactor`, `entrepreneur`, `url_enrichment`.
2. Route every LLM call through a shared limiter.
3. Add queue wait timeout separate from execution timeout.
4. Add overload state:
   when LLM budget is exhausted, defer jobs instead of executing.
5. Pause scheduled jobs under pressure:
   passive capture, daily digest, Reactor daily, Entrepreneur daily.
6. Add metrics:
   in-flight calls, queued jobs by type, oldest queued age, provider timeout
   count, circuit state.

Acceptance:

- During a 25-file drop, total Kimi calls never exceeds configured max.
- Reactor/GStack cannot start when DIKIWI backlog exceeds threshold.
- Scheduler missed-run warnings disappear under soak.
- `/api/ui/status` exposes queue pressure and provider in-flight counts.

## Phase 3: Rebuild DIKIWI As Incremental Pipeline Jobs

Goal:
Make DIKIWI stage-latched and graph-driven without treating a browser batch as
one execution unit.

Files:

- `aily/sessions/dikiwi_mind.py`
- `aily/dikiwi/agents/data_agent.py`
- `aily/dikiwi/agents/information_agent.py`
- `aily/dikiwi/network_synthesis.py`
- `aily/graph/db.py`
- `aily/writer/dikiwi_obsidian.py`

Implementation:

1. Split source processing:
   `extract_source` writes 00-Chaos and extracted metadata.
2. DATA/INFORMATION run per source under queue/backpressure.
3. KNOWLEDGE runs in micro-batches over newly completed information nodes.
4. Graph-change scheduler evaluates affected subgraphs periodically.
5. Higher-order stages run only for selected affected subgraphs.
6. Pipeline records attach to source/job/subgraph, not only upload batch.
7. Keep human `batch_id` as provenance metadata only.

Acceptance:

- 25-file drop can take hours to drain without source failure.
- New files added later trigger only affected-node work.
- DATA/INFORMATION output exists for completed sources before KNOWLEDGE starts.
- Higher stages cite subgraph IDs, not source filenames.
- Graph synthesis can be resumed after backend restart.

## Phase 4: Disable Inline External URL Fetching For PDFs

Goal:
Stop local PDF ingestion from blocking on unrelated external websites.

Files:

- `aily/dikiwi/agents/data_agent.py`
- `aily/processing/markdownize.py`
- `aily/config.py`
- tests under `tests/sessions/`

Implementation:

1. Add `follow_external_links_for_uploads=false` default.
2. During PDF DATA, URLs become reference datapoints.
3. Optional URL enrichment jobs are created separately with low priority.
4. URL enrichment has independent timeout/cache/retry.
5. Auth-gated URL failures never fail the source PDF.

Acceptance:

- PDF containing Synopsys/Okta URLs does not fetch those URLs during DATA.
- URLs appear as reference datapoints.
- Optional enrichment job can fail without source failure.

## Phase 5: Filesystem-First Vault Writer

Goal:
Guarantee 07/08 output when Obsidian app is closed.

Files:

- `aily/sessions/reactor_scheduler.py`
- `aily/sessions/entrepreneur_scheduler.py`
- `aily/sessions/gstack_agent.py`
- `aily/writer/dikiwi_obsidian.py`
- `aily/writer/obsidian.py`

Implementation:

1. Audit all Reactor/Entrepreneur/Guru write paths.
2. Replace REST-only writer calls with filesystem writer calls.
3. REST API becomes optional secondary integration.
4. Any write failure creates retryable write job.
5. Add idempotent note-path generation keyed by proposal/review ID.

Acceptance:

- Shut down Obsidian app; run proposal + entrepreneur; files appear in vault.
- No `Obsidian Local REST API plugin is not running` warning blocks output.
- Re-running write jobs does not duplicate plans.

## Phase 6: Durable GStack / Guru Execution

Goal:
Make 08-Entrepreneurship reliable and checkpointed.

Files:

- `aily/sessions/entrepreneur_scheduler.py`
- `aily/sessions/gstack_agent.py`
- `aily/sessions/models.py`
- `aily/graph/db.py`
- `aily/writer/dikiwi_obsidian.py`

Implementation:

1. Add `business_reviews` durable table/nodes:
   proposal ID, persona, action, verdict, confidence, status, attempts.
2. Save each persona/action result immediately.
3. Make Guru appendix a separate retryable job after plan body exists.
4. Per-proposal timeout budget replaces one huge session timeout.
5. If panel partially completes, write partial 08 plan with explicit missing
   sections and retry later.
6. Deduplicate proposal evaluation so daily scheduler and Studio batch do not
   evaluate same proposal repeatedly.

Acceptance:

- A proposal never disappears if GStack times out.
- Partial GStack results are visible in 08 or Operations.
- Guru failure does not block accepted/denied plan file creation.
- `08-Entrepreneurship` eventually catches up for proposals generated in soak.

## Phase 7: Persistent Pipeline Lifecycle

Goal:
Make Studio status truthful.

Files:

- `aily/ui/events.py`
- `aily/main.py`
- `aily/source_store/store.py`
- `aily/ui/router.py`
- `frontend/src/App.tsx`

Implementation:

1. Add persistent `pipeline_runs` table:
   `pipeline_id`, `source_id`, `job_id`, `stage`, `status`, `started_at`,
   `heartbeat_at`, `completed_at`, `terminal_reason`.
2. Every stage start/completion updates the record.
3. Status endpoint derives active pipelines from non-terminal pipeline records.
4. Add stale-pipeline janitor:
   if no heartbeat beyond TTL, mark `stale_retry_pending`.
5. Frontend separates active, queued, retryable, failed, completed.

Acceptance:

- Cancelled sources never show as active pipelines.
- Retry-pending sources show as backlog, not active.
- Status endpoint and graph/operations view agree.

## Phase 8: Complete Event History And Evidence

Goal:
Make long-run failures diagnosable.

Files:

- `aily/ui/events.py`
- `aily/ui/router.py`
- `frontend/src/App.tsx`
- `scripts/run_studio_human_drop_soak.py`
- `scripts/test_framework.py`

Implementation:

1. Add event sequence numbers.
2. Add paginated event query: `after_seq`, `before_seq`, `limit`.
3. Soak runner exports all pages, not only last 2000 events.
4. Soak runner samples on fixed cadence independent of drops.
5. Soak runner writes partial summaries every N minutes.
6. Capture screenshots at start, mid-run, end, and on failure spikes.

Acceptance:

- 5-hour run can reconstruct full event timeline.
- Final summary exists even if interrupted.
- Evidence includes status trend, failure classification, and screenshots.

## Phase 9: Recovery And Migration Tools

Goal:
Repair existing failed-but-retryable sources from the soak run.

Files:

- new `scripts/recover_retryable_sources.py`
- `aily/source_store/store.py`
- `aily/main.py`

Implementation:

1. Detect failed sources whose raw object exists and whose error is timeout.
2. Convert them to `retry_pending`.
3. Enqueue source jobs using new durable queue.
4. Preserve old failure metadata under `previous_failures`.
5. Dry-run mode prints candidate counts.

Acceptance:

- Soak-run failed sources can be recovered without re-uploading PDFs.
- Recovery does not touch truly corrupt/unsupported sources.

## Phase 10: Real Acceptance Gates

Goal:
Prove the fix with real behavior.

Required gates:

### Gate A: Low-Timeout Retry Gate

Run:
3 PDFs with artificially low DIKIWI stage timeout.

Pass:

- Uploads accepted.
- Sources become `retry_pending`, not `failed`.
- Retry metadata is correct.

### Gate B: 25-File Burst Queue Gate

Run:
One browser/API drop with 25 PDFs.

Pass:

- Request returns quickly.
- 25 jobs queued.
- Active processing never exceeds configured capacity.
- No false failures after 30 minutes.

### Gate C: Headless 07/08 Gate

Run:
Generate proposals and entrepreneurship while Obsidian app is closed.

Pass:

- 07 and 08 files appear by filesystem writer.
- Guru appendix is appended or queued retryably.

### Gate D: 2-Hour Human-Drop Gate

Run:
Random drops for 2 hours.

Pass:

- Upload endpoint error rate: 0%.
- True failed sources: 0 unless corrupt/unsupported.
- Retry-pending backlog may exist but must be recoverable.
- Event history complete.
- Studio active state matches durable DB.

### Gate E: 5-Hour Human-Drop Acceptance

Run:
Same scenario as the failed soak.

Pass:

- No timeout is terminal failure.
- Queue drains or remains retryable.
- 08 output exists for all proposals or has explicit retryable review jobs.
- No stale active pipelines.
- Evidence folder has complete manifest, event pages, screenshots, status
  trends, failures, and final summary.

## Implementation Order

1. Phase 0: timeout-to-retry semantics.
2. Phase 1: durable source queue.
3. Phase 2: global backpressure.
4. Phase 4: disable inline external URL fetch for PDFs.
5. Phase 5: filesystem-first 07/08 writer.
6. Phase 7: persistent pipeline lifecycle.
7. Phase 8: evidence runner upgrades.
8. Phase 3: full incremental DIKIWI restructuring.
9. Phase 6: durable GStack/Guru.
10. Phase 9: recovery scripts.
11. Phase 10: full acceptance gates.

Reasoning:
Phases 0-2 stop false loss and overload. Phases 4-5 remove major avoidable
blockers. Phase 7 makes the UI truthful. Phase 3 and Phase 6 are deeper
architecture work and should run after the system stops damaging source state.

## Risks

- Queue migration can strand old in-memory uploads.
  Mitigation: recovery script and idempotent source jobs.

- Backpressure may make Aily feel slower.
  Mitigation: Studio must show honest queue progress and ETA instead of fake
  activity.

- GStack durability may increase storage volume.
  Mitigation: checkpoint compact structured results and write full narrative only
  for final/partial plans.

- Provider instability can still leave backlog.
  Mitigation: retry/defer state is acceptable; terminal data loss is not.

## Definition Of Done

Aily passes the 5-hour human-drop acceptance gate with:

- Upload success rate: 100%.
- Terminal source failures: 0 for timeout/provider overload cases.
- Retryable backlog visible and recoverable.
- 07 and 08 output generated or queued with durable review jobs.
- Studio active state matches durable DB.
- Complete evidence supports every claim.

