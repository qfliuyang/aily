# Human-Drop Soak Review And Fix List

Generated: 2026-05-05

## Test Scope

Evidence directory:
`logs/runs/2026-05-04T17-19-01Z_studio_human_drop_soak_5h_tmux`

Scenario:
Aily Studio received human-like random PDF drops from `/Users/luzi/aily_chaos`.
Drops were intentionally irregular: single files, small groups, medium groups,
and 25-file bursts. Intake used the real `/api/ui/uploads` endpoint against the
local backend.

At the reviewed snapshot the run was still alive; this review reflects the
available evidence at that point, not a final settled run.

## Summary

The upload path is reliable, but the processing model is not. Every drop returned
HTTP 200, yet most stored sources were converted into permanent failures. The
loss mechanism is downstream of upload: DIKIWI/GStack timeouts and missing
backpressure turn temporary capacity exhaustion into terminal source failure.

The current architecture treats a multi-file human drop as an execution batch.
That is the core mistake. A drop should be intake only. Processing should be
durable, queued, retryable, capacity-aware, and independent of how the human
grouped files in the browser.

## Evidence Snapshot

- Drops submitted: 28
- Submitted files: 157
- Upload endpoint failures: 0
- Source records observed: 151 in samples, 151+ in source store at review time
- Completed sources: 15
- Failed sources in latest sample: 128
- Failed sources in source store at review time: 133
- Processing sources at review time: 1
- Cancelled sources: 2 from earlier exploratory cancellation
- Event query count hit cap: 2000
- Latest graph size: 1632 nodes, 1972 edges

Latest vault counts:

```text
00-Chaos: 100
01-Data: 278
02-Information: 211
03-Knowledge: 218
04-Insight: 46
05-Wisdom: 33
06-Impact: 26
07-Proposal: 4
08-Entrepreneurship: 0
```

Drop size distribution:

```text
1 file: 8 drops
2 files: 7 drops
3 files: 2 drops
5 files: 5 drops
8 files: 2 drops
13 files: 1 drop
25 files: 3 drops
```

## Findings

### P0: Intake Has No Durable Backpressure Queue

Symptom:
Files are accepted by `/api/ui/uploads`, stored, then immediately executed by
`_process_ui_upload_batch`. When runtime capacity is insufficient, they become
`failed`.

Evidence:
All 28 drops returned HTTP 200. The source store later showed 133 failed sources.
The dominant persisted error was `DATA stage timed out after 240.0s`.

Source:
`aily/main.py` starts an in-memory task per batch and calls
`dikiwi_mind.process_inputs_batched(drops)` directly.

Consequence:
Human upload grouping controls execution pressure. A 25-file drop can overload
DIKIWI even though there is no product requirement that all 25 files must start
thinking immediately.

Fix:
Separate intake from execution.

- Upload should only store source records and enqueue work.
- Add durable statuses: `stored`, `queued`, `extracting`, `extracted`,
  `dikiwi_pending`, `processing`, `retry_pending`, `completed`, `failed`.
- Add a source-processing worker that pulls work by capacity.
- Treat timeout as `retry_pending` or `deferred`, not terminal `failed`, unless
  the source is corrupt or extraction is impossible.

### P0: Stage Timeout Is Treated As Data Loss

Symptom:
Sources with valid extracted text are marked failed because an LLM stage exceeds
240 seconds.

Evidence:
Source-store error aggregation:

```text
DATA stage timed out after 240.0s: 119
INSIGHT stage timed out after 240.0s: 5
KNOWLEDGE stage timed out after 240.0s: 3
IMPACT stage timed out after 240.0s: 3
INFORMATION stage timed out after 240.0s: 2
WISDOM stage timed out after 240.0s: 1
```

Source:
`DikiwiMind._execute_batch_stage` wraps every agent execution in
`asyncio.wait_for(..., timeout=dikiwi_stage_timeout_seconds)`. The failed
`StageResult` is later mapped to `source_store.update_status(..., "failed")`.

Consequence:
Temporary LLM slowness permanently fails sources, even though raw PDFs remain
stored and can be retried.

Fix:
Introduce retryable stage state.

- Replace terminal source failure with `retry_pending` for timeout-class errors.
- Track retry count, next retry time, last failed stage, and provider/model.
- Retry with lower concurrency, shorter chunks, fallback model, or local summary
  mode.
- Only terminally fail extraction-corrupt, unsupported-file, or repeated
  retry-exhausted cases.

### P0: Batch Execution Is Concurrent Across Drops, Not Globally Throttled

Symptom:
Several active uploads and many active pipelines accumulate, even though stage
concurrency exists inside each batch.

Evidence:
Latest sample had active uploads:

```text
08f453b1-7e6f-44da-85a1-e340561e0b09
6d7cffd9-7119-4c8a-9ef5-d4ea4ac64261
9ce46c26-cb8d-44e3-be68-880204110f8a
ba992b58-a35f-4295-8e1b-1b9edda66c1f
bb04ec23-077c-4b62-92a2-2e6433f36eb5
```

The source status timeline also showed multiple periods with 20+ processing
sources.

Source:
Each upload request creates an independent asyncio task. There is no global
DIKIWI work queue that serializes or rate-limits batches across requests.

Consequence:
Stage-level concurrency only limits work inside one batch. Multiple batches
still compete for the same LLM capacity, graph DB, writer, and event loop.

Fix:
Add global capacity management.

- One durable DIKIWI worker pool with provider-specific semaphores.
- Queue drops individually, regardless of browser batch size.
- Use batch windows only for graph synthesis, not for immediate execution.
- Enforce global max in-flight LLM calls per provider and per stage.

### P0: 08-Entrepreneurship Did Not Produce Output

Symptom:
`08-Entrepreneurship` remained empty while proposals and GStack activity existed.

Evidence:

```text
07-Proposal: 4 notes
08-Entrepreneurship: 0 notes
graph_business_count: 0
```

Backend log contained:

```text
GStack evaluation timed out after 1800.0s
Fallback GStack evaluation timed out after 90.0s
Failed to write proposal note: Obsidian Local REST API plugin is not running
Failed to write session report: Obsidian Local REST API plugin is not running
```

Source:
Entrepreneur/GStack execution is expensive, runs under heavy DIKIWI load, and
still depends on the Obsidian Local REST API for some writes.

Consequence:
The business pipeline is not reliable in headless/local-server mode. Proposals
can be evaluated partially without durable 08 output.

Fix:

- Make all 07/08 writes use the vault filesystem writer when REST API is absent.
- Split GStack into durable per-proposal jobs with checkpoints.
- Enforce per-proposal timeout budgets and persist partial panel results.
- Decouple Guru appendix generation from the main verdict path.
- Add a recovery job: any proposal without 08 output is retried later.

### P1: Active Pipeline State Is Stale

Symptom:
Studio reported active pipelines that belonged to cancelled or already terminal
sources.

Evidence:
Early sample after cancellation showed two cancelled sources but active pipeline
IDs still present. Later samples still contained old pipeline IDs from prior
drops.

Source:
Active pipeline state is maintained in runtime memory and event-derived frontend
state, but terminal cleanup is incomplete for cancellation, timeout, and batch
failure paths.

Consequence:
Studio cannot be trusted as an operational control room. It overstates active
thinking and hides actual backlog/failed state.

Fix:

- Store pipeline lifecycle in SQLite, not only in memory/events.
- Every terminal transition must write `completed_at` and `terminal_state`.
- `/api/ui/status` should derive active pipelines from non-terminal DB state.
- Add a stale-pipeline janitor that closes pipelines with no heartbeat beyond a
  configured TTL.

### P1: UI/Event Evidence Is Capped And Loses Long-Run History

Symptom:
Event query saturated at 2000 events during the soak.

Evidence:
Every later sample reported:

```text
event_count: 2000
```

Source:
The UI event query and frontend replay use bounded limits.

Consequence:
Long-running tests and real usage lose causality. A later debug session cannot
fully reconstruct what happened.

Fix:

- Add paginated event querying by cursor/time.
- Store run-scoped events with sequence numbers.
- Let the UI load recent events by default but fetch full history on demand.
- Evidence runner should export complete event pages, not one capped query.

### P1: DIKIWI Data Stage Does Too Much Network Work For Local PDFs

Symptom:
The Data stage attempted to markdownize URLs found inside PDFs, including
auth-gated Synopsys/Okta pages.

Evidence:
Backend logs showed static fetches and redirects for Synopsys/Okta URLs, plus
markdownize failures.

Source:
DataAgent markdownizes discovered URLs while processing a local document.

Consequence:
Local PDF ingestion can block on unrelated external websites. Auth gates,
redirect loops, and slow pages steal budget from the actual source.

Fix:

- For uploaded PDFs, classify external URLs as data points/references, not
  fetch targets by default.
- Add a per-source setting: `follow_external_links=false` for document intake.
- Move external URL fetches into a separate low-priority enrichment queue.
- Cache and rate-limit URL enrichment independently.

### P1: Circuit Breakers Trip But Do Not Create A Useful Recovery Path

Symptom:
Circuit breakers repeatedly opened for Reactor/Entrepreneur paths.

Evidence:

```text
Circuit breaker tripped: 16
Reactor evaluate_context skipped: 12
Circuit breaker recovery failed repeatedly
```

Source:
LLM timeouts and writer failures count as scheduler failures, but source/proposal
records are not moved into a durable retry state.

Consequence:
Work silently stops or skips while sources remain failed and proposals remain
unevaluated.

Fix:

- Separate provider failures, writer failures, and business-logic failures.
- Circuit breaker should pause scheduling, not mark domain work terminal.
- Add explicit `blocked_by_provider`, `blocked_by_writer`, and `retry_pending`
  states.

### P2: Obsidian REST API Dependency Is Incorrect For Headless Runs

Symptom:
Proposal/session report writes failed because the Obsidian Local REST API plugin
was not running.

Evidence:
`Obsidian Local REST API plugin is not running` appeared 61 times.

Source:
Some Reactor/Entrepreneur write paths still use REST writer instead of the vault
filesystem writer.

Consequence:
Headless backend execution cannot reliably produce vault output.

Fix:
Standardize all DIKIWI/Reactor/Entrepreneur writes on filesystem-first
`DikiwiObsidianWriter`. REST can be optional for interactive Obsidian integration
only.

### P2: Graph Counts In `/api/ui/status` Are Misleading

Symptom:
`/api/ui/status` showed graph counts like `information: 222` while sample graph
snapshot showed 1632 nodes and 1972 edges.

Source:
Status counts only selected node types and appeared inconsistent with the graph
snapshot/eventual vault counts.

Consequence:
Operations view can mislead debugging.

Fix:

- Make status graph counts match the same graph provider used by the graph view.
- Include total nodes, total edges, and counts by node type.
- Include stale/failed/pending counts separately.

### P2: Soak Runner Needs Stronger Finalization

Symptom:
At review time the run had no `final-summary.json`, because the runner was still
in progress. It also samples after each drop but does not independently poll
often during long processing gaps.

Fix:

- Add periodic sampler independent of drop cadence.
- Add signal handler to write partial summary on interruption.
- Capture complete paginated event history at finalization.
- Store backend process metadata and tmux session metadata in the run directory.

## Prioritized Fix List

### Fix 1: Implement Durable Source Work Queue

Create a SQLite-backed source work queue and stop executing DIKIWI directly from
request handlers.

Acceptance:

- Uploading 25 files creates 25 queued source jobs.
- The request returns quickly after storage.
- Only configured worker capacity is processed at a time.
- Restarting backend resumes queued work.
- No source is marked failed due only to queue wait time.

### Fix 2: Convert Timeout Failures To Retryable States

Timeouts should not mean source failure.

Acceptance:

- DATA timeout results in `retry_pending`, not `failed`.
- Retry metadata includes stage, attempt count, provider, model, and next retry.
- After retry exhaustion, source becomes `failed_retry_exhausted`.
- UI separates retryable backlog from true failures.

### Fix 3: Add Global LLM Backpressure

Add provider and stage semaphores shared across DIKIWI, Reactor, Entrepreneur,
and URL enrichment.

Acceptance:

- Total concurrent Kimi/DeepSeek calls never exceeds configured limits.
- Reactor/GStack cannot starve DIKIWI intake.
- Scheduled jobs are skipped/deferred under pressure rather than competing.

### Fix 4: Decouple Browser Drop Batch From DIKIWI Batch

The user's batch should not become the execution batch.

Acceptance:

- A 25-file drop can be processed over time as individual queued jobs.
- Graph synthesis can form periodic micro-batches from completed information
  nodes.
- The batch ID remains as provenance only.

### Fix 5: Filesystem-First Writer For 07/08

Remove REST-only write dependencies from Reactor and Entrepreneur.

Acceptance:

- `07-Proposal` and `08-Entrepreneurship` are written when Obsidian app is
  closed.
- REST writer failures do not block filesystem output.
- Guru appendix is appended to the plan file or persisted as retryable if the
  plan is not yet available.

### Fix 6: Make Entrepreneur/GStack Durable And Checkpointed

Split GStack into restartable jobs.

Acceptance:

- Each proposal has persistent evaluation state.
- Persona verdicts are saved as they complete.
- Guru generation can fail without losing the accepted/denied business plan.
- A proposal without 08 output is automatically retried.

### Fix 7: Fix Pipeline Lifecycle State

Use persistent pipeline records for active status.

Acceptance:

- Cancelled sources do not appear as active pipelines.
- Timed-out/retry-pending sources appear in backlog, not active.
- Pipeline heartbeat TTL closes orphaned active records.

### Fix 8: Disable Inline External URL Fetching For PDF DATA

External URLs inside PDFs should be references first.

Acceptance:

- Local PDF Data stage does not fetch Synopsys/Okta URLs by default.
- External references are stored as datapoints.
- Optional URL enrichment jobs run separately with their own timeout and cache.

### Fix 9: Paginate And Persist Complete UI Event History

Acceptance:

- UI can load recent events quickly and full run history on demand.
- Evidence runner exports all events for a run.
- No long-run review depends on a capped 2000-event snapshot.

### Fix 10: Improve Soak Test Harness

Acceptance:

- Writes partial summaries every N minutes.
- Samples status on a fixed cadence independent of drop cadence.
- Captures screenshots at start, mid-run, and end.
- Emits machine-readable failure classification.

