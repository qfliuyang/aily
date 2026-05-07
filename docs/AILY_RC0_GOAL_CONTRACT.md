# Aily RC0 Goal Contract

Date: 2026-05-06

This document is the durable goal contract for a long-running Codex `/goal`
session. It turns Aily's private second-brain vision into quantified release
targets with anti-mock and anti-cheat constraints.

Use this document as the source of truth for Codex goal work. Do not replace it
with a vague "improve Aily" prompt.

## How To Start The Codex Goal

Open Codex TUI in the Aily repo and run `/goal`. Paste the goal prompt below.
If Codex asks for a token budget, prefer a milestone-sized budget and resume at
checkpoint boundaries rather than letting one unbounded run mix unrelated work.

```text
Goal: Ship Aily RC0 as a production-grade private personal second-brain release candidate.

Aily RC0 is complete only when every target in docs/AILY_RC0_GOAL_CONTRACT.md is checked off with fresh automated evidence in docs/release-rc0-evidence.md.

Primary outcome:
I can run Aily with Docker, submit URLs/text/files through documented interfaces, watch processing in Aily Studio, and trust that successful inputs become traceable, high-quality Obsidian/Zettelkasten notes through the DIKIWI pipeline. Failures must be visible, retryable where appropriate, and never silently lose input.

Mandatory artifacts:
1. Maintain docs/production-rc0-plan.md.
2. Maintain docs/release-rc0-evidence.md.
3. Track targets AILY-RC0-001 through AILY-RC0-012 from docs/AILY_RC0_GOAL_CONTRACT.md.
4. For every completed target, record changed files, commands run, fresh output summary, evidence paths, and remaining risks.

Anti-cheat rule:
Do not mark any target complete from mocked, skipped, fabricated, manually
mutated, or unverifiable evidence. Every test, script, or manual verification
cited as RC0 evidence must exercise the real production boundary named by the
target: real files, real source store, real queue/worker path, real vault
writes, real graph/database writes, real provider LLM calls, real FastAPI
runtime, real browser execution when Studio behavior is claimed, and real Docker
Compose when deployment is claimed.
For LLM-dependent targets, real provider calls are mandatory. A local JSONL
response trace, fake client, replayed response, monkeypatch, fixture answer, or
"mock model" is not acceptable. Each successful accepted LLM call must include
provider/base URL, HTTP status, duration, token usage, and a provider response
ID or provider request ID, plus a separate provider smoke or billing-console
reconciliation for release acceptance.

Execution rules:
1. Start each checkpoint by updating docs/production-rc0-plan.md with scope, risks, target IDs, expected tests, and rollback notes.
2. Before changing production behavior, add or strengthen the test or verification that would fail without the capability.
3. Prefer vertical slices that prove one user-visible capability end to end.
4. Do not broaden scope into unrelated rewrites unless required by a target.
5. Use Kimi/DeepSeek real provider paths for all DIKIWI, note-quality,
   provider, proposal, and output-quality evidence. If credentials are missing,
   stop and record a blocker; do not substitute mocks or local fake responses.
6. Use aily_chaos or tests/chaos as a required failure-readiness lane.
7. If a target cannot be completed, stop at the checkpoint boundary and write a continuation plan. Do not claim RC0 is complete.

Final stop condition:
All 12 RC0 targets are complete with fresh evidence, and Aily can be credibly run from Docker as my private second brain with capture, processing, note generation, Studio operation, failure visibility, and chaos-tested reliability.
```

## Anti-Mock And Anti-Cheat Rules

These rules are release blockers. They apply to any test, script, manual run, or
document used as RC0 evidence.

### AC-000: Real-Test Mandate For Goal Evidence

RC0 is a production-readiness goal, not a unit-test score. Every verification
used to close a target must run real Aily code against the real boundary under
test.

Forbidden as target-closure evidence:

- Mocked LLMs, fake provider clients, monkeypatched provider transports,
  replayed JSONL, fixture answers, or local "LLM-like" strings.
- In-memory vaults, fake graph databases, fake source stores, synthetic queue
  state, fake browser events, fake Docker output, or direct database mutation
  that bypasses production behavior.
- Tests whose main success condition is "the mock was called" rather than "the
  production path produced durable user-visible evidence."
- Any evidence path whose command cannot be rerun to touch the real system
  boundary it claims to certify.

Required:

- DIKIWI, note quality, provider, proposal, and business-output checks must make
  real Kimi/DeepSeek provider calls and record provider receipts.
- Pipeline checks must read/write real files, source-store records, queue jobs,
  graph DB rows, and Obsidian vault notes.
- Studio checks must use a real browser against a running app and real backend
  state.
- Docker checks must run real `docker compose` build/up/health/restart behavior.
- Chaos checks must induce real failure modes and observe production recovery or
  visible terminal failure.

Mock-based unit tests may exist only as local development guards for pure
mechanics. They must be marked as non-acceptance, must never appear in
`docs/release-rc0-evidence.md` as closure evidence, and must never be used to
claim RC0 progress. If the only available test for a target is mocked, the
target is blocked.

### AC-001: Product Claims Need Real Boundaries

Mocked tests can prove local mechanics only. They cannot certify product
behavior and do not count toward RC0 completion.

Forbidden as RC0 acceptance evidence:

- Mocked LLM responses for DIKIWI, proposal, provider, or note-quality claims.
- Stubbed provider SDKs, fake HTTP transports, replayed provider responses, or
  local transcripts for any LLM-dependent target.
- Mocked graph/database writes for graph growth, links, or lineage claims.
- Mocked vault paths or in-memory notes for Obsidian/Zettelkasten claims.
- Fake browser events for Aily Studio behavior.
- Fake queue transitions for worker reliability.
- Fake Docker commands, screenshots, or copied old output for deployment claims.

Required replacement:

- Use real provider calls for provider or output-quality claims.
- Capture provider receipt metadata for every accepted LLM call: provider, base
  URL, HTTP status, duration, token usage, and provider response ID or provider
  request ID. A local response transcript without those fields is
  unverifiable.
- Use real source-store, queue, graph DB, and vault writes for pipeline claims.
- Use a real browser against the running FastAPI app for Studio claims.
- Use `docker compose` for Docker deployment claims.

### AC-002: No Manual State Mutation In Acceptance Tests

Acceptance, e2e, real-service, and chaos tests must observe production code doing
the work. They must not perform the success or failure transition themselves.

Forbidden examples:

- Calling `db.complete_job(..., success=False)` inside a test that claims worker
  failure handling.
- Inserting final DIKIWI stage rows directly instead of running the pipeline.
- Writing final Obsidian notes from the test instead of the writer path.
- Emitting frontend "completed" events from fixtures when claiming real Studio
  operation.

Required replacement:

- Start the actual worker, API, router, pipeline, browser, or Docker service.
- Poll or query durable state until the production path reaches a terminal state.
- Assert on persisted status, errors, notes, graph nodes, events, and evidence
  manifests.

### AC-003: Evidence Must Be Fresh And Reproducible

Every completed target must include fresh command evidence in
`docs/release-rc0-evidence.md`.

Minimum evidence fields:

- Date/time.
- Git SHA and dirty-worktree status.
- Exact command.
- Exit code.
- Short output summary.
- Evidence artifact path, usually under `logs/runs/<run_id>/`.
- Whether the run used real files, real vault, real graph DB, real provider,
  real browser, and real Docker.

Old evidence can explain history, but it cannot close a new RC0 target unless
the command is rerun or the target explicitly says historical evidence is enough.

### AC-004: Negative Controls Are Required For New Gates

Any new release gate must prove it can fail.

For each new gate, add at least one of:

- A regression test that fails before the fix and passes after the fix.
- A fixture or contract test showing the gate rejects mocked acceptance evidence.
- A controlled failure scenario proving errors become visible rather than hidden.
- A documented pre-fix failure output captured in the plan/evidence file.

### AC-005: Skips Are Not Success

Skipped tests never count as RC0 acceptance.

Allowed skips:

- Credential-gated real-service tests when credentials are absent.
- Slow/e2e tests excluded from a fast local gate but run in the release gate.
- Platform-specific tests with documented platform constraints.

Required for every skip:

- Clear reason.
- Marker or environment gate.
- Entry in the evidence file if the skipped test affects an RC0 target.
- A command showing how to run it when prerequisites exist.
- If a real provider credential or budget prerequisite is missing, mark the
  target blocked. Do not replace the skipped real-provider run with a mocked run.

### AC-006: Health Baseline Cannot Hide New Debt

`tests/quality_baseline.json` may track known debt, but it must not absorb new
RC0 regressions without a dated rationale.

Forbidden:

- Regenerating the baseline just to make the health gate pass.
- Accepting new skipped tests, weak assertions, unmarked lanes, mock acceptance,
  or stale docs without explaining why the debt remains.

Required:

- Health gate must report `baseline_failures=[]`.
- Any accepted new debt must cite target ID, date, owner rationale, and removal
  condition in the plan or evidence file.

### AC-007: Aily Studio Must Animate Reality

Studio UI acceptance must be tied to backend state.

Forbidden:

- Showing DIKIWI stage completion without corresponding backend event or
  persisted stage artifact.
- Showing proposal cards without proposal note or graph node evidence.
- Showing graph growth without backend graph/threshold evidence.
- Treating component-only tests as browser acceptance.

Required:

- Browser tests against FastAPI static serving or dev server backed by real API.
- Assertions against API state, websocket/durable UI events, and visible UI.
- Screenshots/traces when available.

### AC-008: Docker Claims Require Clean-Room Behavior

Docker acceptance must start from a clean or explicitly isolated environment.

Required:

- `docker compose build` from the repo.
- `docker compose up` with documented env.
- Healthcheck proving usable HTTP/API behavior.
- Volume persistence across restart.
- Backup/restore dry run or documented manual recovery test.

Forbidden:

- Claiming Docker readiness from host Python tests only.
- Depending on undeclared local paths, prebuilt frontend artifacts, or hidden env
  values.

### AC-009: Provider Claims Need Provider Receipts

Real LLM acceptance must be auditable against provider-side behavior, not just
local code paths.

Forbidden:

- Marking DIKIWI, note-quality, proposal, or provider targets complete from an
  LLM log that only records prompts/responses/model names.
- Treating `manifest.acceptance.real_llm=true` as proof without independent
  receipt metadata.
- Using local monkeypatches, fake provider clients, or replayed JSONL as release
  evidence for provider usage.

Required:

- `LLMClient.last_response_metadata` or the run manifest records provider, base
  URL, HTTP status, duration, token usage, provider response ID or provider
  request ID, and success/failure.
- `scripts/provider_smoke.py` passes for the claimed provider, or the evidence
  file records a billing/API-console reconciliation for the same UTC window.
- Full DIKIWI/note-quality closure must include provider receipt metadata for
  the actual DIKIWI run, not only a separate one-call smoke.
- DIKIWI traceability and quality audits fail if successful LLM records lack
  provider-verifiable receipt metadata.

## RC0 Targets

Each target is complete only when its metric, tests, and evidence are recorded in
`docs/release-rc0-evidence.md`.

### AILY-RC0-001: Canonical Verification Harness

Metric:

- One command runs the practical release gate.
- One command runs the full available verification gate.
- The harness exits non-zero on test failure, skipped acceptance claim, health
  regression, Docker smoke failure, or chaos failure.

Minimum evidence:

- `scripts/verify_project_health.py --check --json` passes.
- The evidence file records exact commands and latest outputs.

### AILY-RC0-002: Test Lane Integrity

Metric:

- 100% of new or modified tests use exactly one semantic lane marker:
  `unit`, `contract`, `integration`, `e2e`, `real_service`, `acceptance`,
  `security`, or `chaos`.
- 0 nested `pytest.ini` files under `tests/`.
- 0 new skipped tests unless accepted with dated rationale.

Minimum evidence:

- Root pytest collection succeeds.
- Health gate reports no baseline failures.

### AILY-RC0-003: Capture Coverage

Metric:

- URL, text message, and file capture all create durable source records and
  queue or pipeline work items with source metadata.
- Duplicate behavior is deterministic and documented for all three capture
  types.

Minimum evidence:

- At least one test per capture type.
- At least one duplicate test per capture type.

### AILY-RC0-004: Queue Reliability

Metric:

- 0 silent job loss across worker restart.
- Failed jobs preserve visible status, `error_message`, and retry information.
- Stale running jobs recover or become terminal within documented timeout.

Minimum evidence:

- Worker failure test runs the production `JobWorker` loop.
- Restart test proves queued work survives restart.
- Bad input test proves visible failed state.

### AILY-RC0-005: DIKIWI Stage Traceability

Metric:

- Every successful processed item records all six DIKIWI stages: Data,
  Information, Knowledge, Insight, Wisdom, Impact.
- Each stage has persisted output or explicit structured failure.
- Every generated note includes source traceability.

Minimum evidence:

- At least 10 representative fixtures or real-run samples.
- Samples include URL, text, document/PDF, malformed input, and duplicate input.
- Successful DIKIWI samples must make real provider LLM calls and include
  provider receipt metadata for every LLM stage call.
- The traceability audit must fail if all persisted stage outputs are present
  but LLM calls are local-only, mocked, replayed, or missing provider receipts.

### AILY-RC0-006: Note Quality Contract

Metric:

- At least 10 golden/eval fixtures score >= 4/5 on a documented usefulness
  rubric.
- 100% of successful notes include title, source reference, timestamp, DIKIWI
  metadata, tags, and graph-friendly links.
- 0 notes use raw UUID-like titles unless source has no meaningful title.

Minimum evidence:

- Rubric and latest scores in the evidence file.
- Regression tests for metadata, title quality, links, and source references.
- Quality scores must be computed from notes generated by a provider-verified
  DIKIWI run. Mock-generated notes, replayed notes, or notes from a local-only
  trace cannot close this target.
- The evidence file must include the provider receipt summary for the exact run
  whose notes are scored.

### AILY-RC0-007: Obsidian/Zettelkasten Graph Safety

Metric:

- 0 broken internal links in newly generated notes during release tests.
- 0 duplicate note files for identical canonical source unless versioning is
  intentional.
- Notes are written to documented vault paths.

Minimum evidence:

- Link validation output.
- Generated note file listing.
- Vault path contract test.

### AILY-RC0-008: Interactive Web UI Core Flows

Metric:

- Studio supports submit content, view queue/status, inspect failure, inspect
  produced note/summary, and retry/reprocess eligible failure.
- Each flow has browser/e2e coverage.
- UI shows empty, loading, success, failure, and retrying states.

Minimum evidence:

- At least five browser/UI tests, one per flow.
- Tests run against real FastAPI behavior, not component-only mocks.

### AILY-RC0-009: Docker Deployment

Metric:

- Docker Compose builds from clean checkout.
- Services start with documented env.
- Healthcheck verifies usable HTTP/API behavior.
- Persistent data survives container restart.

Minimum evidence:

- Docker build/up/health/restart output in evidence file.
- Smoke script or test exists.

### AILY-RC0-010: Configuration, Secrets, And Fail-Fast Ops

Metric:

- Missing required env vars fail at startup with actionable errors.
- No API keys or secrets are hardcoded.
- `.env.example` documents required and optional production settings.

Minimum evidence:

- Config validation tests.
- Secret scan or grep-based guard.
- Updated operator docs.

### AILY-RC0-011: Chaos Failure Readiness

Metric:

- `aily_chaos` or `tests/chaos` covers provider outage, bad URL, bad file,
  duplicate submission, Obsidian unavailable, and worker restart during
  processing.
- 100% of chaos scenarios end with completed output or visible failure and no
  silent data loss.

Minimum evidence:

- Exact chaos command and latest result.
- Regression tests for chaos-discovered bugs.

### AILY-RC0-012: Release Documentation

Metric:

- A new user can run Aily locally with Docker using docs only.
- Docs cover setup, capture methods, Studio usage, env config, healthchecks,
  backups, restore, troubleshooting, and known limitations.

Minimum evidence:

- Documentation link check or project health scan has no new stale links.
- Docker quickstart commands are executed in current evidence.

## Checkpoints

### Checkpoint 0: Baseline Inventory

Exit criteria:

- `docs/production-rc0-plan.md` exists.
- It maps current capture, queue, DIKIWI, writer, Studio, Docker, test, and
  chaos surfaces.
- It lists blockers against all 12 target IDs.
- No production code changes happen before this checkpoint is written.

### Checkpoint 1: Verification Foundation

Exit criteria:

- AILY-RC0-001 and AILY-RC0-002 pass.
- Health gate prevents new false-confidence tests.
- Canonical release verification commands are documented.

### Checkpoint 2: Capture-To-Queue Reliability

Exit criteria:

- AILY-RC0-003 and AILY-RC0-004 pass.
- URL, text, and file capture are tested.
- Restart, failure, and dedup behavior are tested.

### Checkpoint 3: Queue-To-Note Second-Brain Quality

Exit criteria:

- AILY-RC0-005, AILY-RC0-006, and AILY-RC0-007 pass.
- At least 10 golden/eval fixtures exist.
- Notes are traceable, linked, deduped, and useful.

### Checkpoint 4: Web UI Operability

Exit criteria:

- AILY-RC0-008 passes.
- Browser tests prove Studio can operate normal second-brain workflows without
  reading logs.

### Checkpoint 5: Docker And Ops Readiness

Exit criteria:

- AILY-RC0-009 and AILY-RC0-010 pass.
- Clean Docker deployment, healthcheck, env validation, persistence, and
  backup/restore docs are verified.

### Checkpoint 6: Chaos And Release Closure

Exit criteria:

- AILY-RC0-011 and AILY-RC0-012 pass.
- Chaos runs the six required scenarios.
- `docs/release-rc0-evidence.md` contains final command outputs, changed files,
  known risks, and exact rerun instructions.

## Final Completion Rule

RC0 is complete only when all 12 targets are checked off in
`docs/release-rc0-evidence.md` with fresh verification evidence. If any target
is incomplete, Codex must stop at the nearest checkpoint and write the exact
continuation plan instead of claiming completion.
