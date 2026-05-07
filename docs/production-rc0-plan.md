# Aily RC0 Production Plan

Date: 2026-05-06

Source contract: `docs/AILY_RC0_GOAL_CONTRACT.md`

Status: RC0 target-closure complete as of 2026-05-07 after the
provider-verified full release gate
`logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/manifest.json`.
The earlier local-only LLM claim remains invalidated and superseded by
provider-receipt-backed evidence.

## Goal

Ship Aily RC0 as a production-grade private personal second-brain release
candidate. RC0 means Aily can be run from Docker, accept URLs/text/files, expose
normal operations through Aily Studio, produce traceable Obsidian/Zettelkasten
knowledge through DIKIWI, surface failures, and prove the claims with fresh
automated evidence.

## Non-Negotiable Constraints

- Do not mark any RC0 target complete without fresh evidence in
  `docs/release-rc0-evidence.md`.
- Do not use mocked, skipped, manually mutated, stale, or undocumented evidence
  as product acceptance.
- Do not regenerate health baselines to hide new debt.
- Do not modify production code before the target ID, expected failing proof, and
  rollback note are recorded here.
- Do not claim RC0 complete until all targets AILY-RC0-001 through
  AILY-RC0-012 are closed.

## Current Baseline Map

### Capture And Source Store

Observed surfaces:

- Studio upload and URL APIs: `aily/ui/router.py`
- Source persistence: `aily/source_store/store.py`
- URL processing: `aily/processing/router.py`, `aily/browser/simple_extractor.py`
- Capture-related tests: `tests/test_source_store.py`,
  `tests/test_studio_url_processing.py`, `tests/test_ui_router.py`

Known gap:

- RC0 requires URL, text message, and file capture coverage with duplicate
  behavior for all three. Current evidence suggests file and URL paths are
  developed, but text-message capture and a single unified capture-to-job
  contract remain blockers until proven by fresh tests.

### Queue And Worker

Observed surfaces:

- Queue DB: `aily/queue/db.py`
- Worker: `aily/queue/worker.py`
- Queue/worker tests: `tests/test_queue.py`, `tests/test_worker.py`,
  `tests/integration/test_e2e_mvp.py`

Known gap:

- RC0 requires restart survival, stale-running recovery, visible terminal
  failure state, and production worker-loop failure proof. Some coverage exists,
  but RC0 closure needs a fresh release-gate run and explicit evidence mapping.

### DIKIWI Pipeline And Writer

Observed surfaces:

- Runtime: `aily/sessions/dikiwi_mind.py`
- Orchestration: `aily/dikiwi/orchestrator.py`,
  `aily/dikiwi/network_synthesis.py`
- Stages: `aily/dikiwi/stages.py`
- Obsidian writer: `aily/writer/dikiwi_obsidian.py`
- Tests: `tests/dikiwi/`, `tests/sessions/`, `tests/writer/`
- Historical real evidence: `logs/runs/2026-05-03T08-13-27Z_docker_real_llm_dikiwi_quality_2pdf/dikiwi-quality-report.json`

Known gap:

- Historical real LLM evidence is useful background, not sufficient RC0 closure.
  RC0 requires fresh 10-fixture/rubric evidence and explicit traceability from
  source to all six DIKIWI stages to note and graph artifacts.

### Aily Studio

Observed surfaces:

- Backend APIs/events: `aily/ui/router.py`, `aily/ui/events.py`,
  `aily/ui/telemetry.py`
- Frontend: `frontend/src/App.tsx`
- Tests/scripts: `tests/test_ui_router.py`, `tests/test_ui_static.py`,
  `scripts/run_studio_browser_e2e.py`,
  `scripts/run_studio_agent_browser_e2e.py`
- Historical browser evidence under `logs/runs/*studio*`

Known gap:

- RC0 requires five browser-proven operator flows: submit content, view
  queue/status, inspect failure, inspect produced note/summary, and
  retry/reprocess. Historical UI/control evidence is not enough until the five
  flows are freshly run and mapped to RC0 targets.

### Docker And Operations

Observed surfaces:

- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.preprod.yml`
- Docker E2E script: `scripts/run_docker_preprod_e2e.py`
- Historical Docker evidence:
  `logs/runs/2026-05-03T00-26-50Z_docker_preprod_retry_url_e2e/manifest.json`

Known gap:

- RC0 requires fresh Docker build/up/health/restart evidence and docs-only
  reproducibility. Historical Docker evidence is not closure evidence for the
  current dirty worktree.

### Chaos And Failure Readiness

Observed surfaces:

- Chaos runtime: `aily/chaos/`
- Chaos CLI: `scripts/aily_chaos_cli.py`
- Unified scenario runner: `scripts/run_test_suite.py`
- Tests: `tests/chaos/`

Known gap:

- RC0 requires six chaos scenarios: provider outage, bad URL, bad file,
  duplicate submission, Obsidian unavailable, and worker restart during
  processing. Existing chaos tests focus on chaos processors/bridges and are not
  yet proven to cover the six RC0 failure scenarios end to end.

### Verification And Evidence

Observed surfaces:

- Health gate: `scripts/verify_project_health.py`
- Evidence runtime: `aily/verify/evidence.py`,
  `aily/verify/run_registry.py`, `aily/verify/verifier.py`
- Evidence tests: `tests/verify/`
- Current health baseline exists at `tests/quality_baseline.json`

Known gap:

- A practical release gate and full release gate are not yet codified as one or
  two canonical commands that cover health, tests, Docker, Studio, and chaos.

## Target Status

| Target | Status | Current blocker |
| --- | --- | --- |
| AILY-RC0-001 Canonical Verification Harness | Complete | Practical and full gates now pass with manifests; self-tests cover failure/anti-cheat manifest behavior. |
| AILY-RC0-002 Test Lane Integrity | Complete | Current RC0 changes add no health baseline regression; root collection and health pass in the full gate, and standalone health reports `baseline_failures=[]`. |
| AILY-RC0-003 Capture Coverage | Complete | File, URL, and text capture now have a fresh contract test proving durable source records, queued source jobs with metadata, and deterministic duplicate behavior; the practical/full gates include it. |
| AILY-RC0-004 Queue Reliability | Complete | Fresh contract tests run the production `JobWorker` loop and prove DB-reopen restart survival, terminal visible failures with retry count/error message, retry-pending error visibility, and stale-lock recovery without silent loss. |
| AILY-RC0-005 DIKIWI Stage Traceability | Complete | Final full gate `provider_verified_dikiwi_e2e` records DATA→IMPACT, 74 generated notes, 13/13 provider-verified Kimi calls, and a fresh 10-sample SourceStore ledger. |
| AILY-RC0-006 Note Quality Contract | Complete | Final full gate provider-verified note-quality audit scores 25/25 eval notes at 5.0 with zero required-field/link failures. |
| AILY-RC0-007 Obsidian/Zettelkasten Graph Safety | Complete | Final full gate provider-verified graph-safety audit proves 0 broken wikilinks, 0 path failures, and 0 duplicate generated note identities/content. |
| AILY-RC0-008 Interactive Web UI Core Flows | Complete | Fresh real-browser Studio gate covers upload, URL, operations/status, production worker failure, retry/reprocess without manual mutation, and browser inspection of a real wisdom-note summary. |
| AILY-RC0-009 Docker Deployment | Complete | Fresh Docker preprod E2E passed via the full gate, including build, up, auth, HTTP/API behavior, restart persistence, and backup/restore dry run. |
| AILY-RC0-010 Configuration, Secrets, And Fail-Fast Ops | Complete | Hosted startup now fails closed for weak UI auth and missing provider key when real DIKIWI is enabled; `.env.example` is placeholder-only and complete; contract tests include a grep-style secret guard; hosted runbook documents fail-fast rules. |
| AILY-RC0-011 Chaos Failure Readiness | Complete | Fresh `tests/chaos/test_failure_readiness.py` covers provider outage, bad URL, bad file, duplicate submission, Obsidian unavailable, and stale worker restart recovery with visible terminal state/no silent data loss. |
| AILY-RC0-012 Release Documentation | Complete | `docs/RC0_QUICKSTART.md` now covers Docker setup, capture methods, Studio, env config, healthchecks, backups, restore, troubleshooting, known limitations, and links to operator references; contract tests and health link scan pass. |

## Checkpoint Plan

### Checkpoint 0: Baseline Inventory

Exit criteria:

- This plan exists and maps capture, queue, DIKIWI, writer, Studio, Docker,
  test, and chaos surfaces.
- `docs/release-rc0-evidence.md` exists and records fresh baseline commands.
- All 12 targets have an initial blocked/partial status.

Rollback note:

- This checkpoint is docs-only. Revert
  `docs/production-rc0-plan.md` and `docs/release-rc0-evidence.md` if the plan
  needs to be replaced.

### Checkpoint 1: Verification Foundation

Target IDs:

- AILY-RC0-001
- AILY-RC0-002

Expected work:

- Define practical and full release gates.
- Use `scripts/run_rc0_release_gate.py` (`scripts.run_rc0_release_gate`) as the
  canonical RC0 gate runner unless a later checkpoint replaces it with a better
  verified command.
- Use `scripts/run_rc0_provider_dikiwi_gate.py`
  (`scripts.run_rc0_provider_dikiwi_gate`) inside the full gate for
  provider-receipt-backed AILY-RC0-005/006/007 evidence.
- Make the health gate reject new anti-mock/anti-cheat regressions.
- Prove root collection and health run from current tree.

Expected tests:

- `python3 scripts/verify_project_health.py --check --json`
- `python3 -m pytest --collect-only -q tests`
- Targeted tests for new verifier/health behavior.

### Checkpoint 2: Capture-To-Queue Reliability

Target IDs:

- AILY-RC0-003
- AILY-RC0-004

Expected work:

- Close capture coverage for URL, text message, and file.
- Prove deterministic duplicate behavior.
- Prove worker restart/failure/stale-running behavior through production paths.

### Checkpoint 3: Queue-To-Note Second-Brain Quality

Target IDs:

- AILY-RC0-005
- AILY-RC0-006
- AILY-RC0-007

Expected work:

- Build or identify 10 representative fixtures.
- Add note-quality rubric/evaluator.
- Prove traceability and graph/link safety.

### Checkpoint 4: Web UI Operability

Target IDs:

- AILY-RC0-008

Expected work:

- Prove the five operator flows with browser tests against real backend state.

### Checkpoint 5: Docker And Ops Readiness

Target IDs:

- AILY-RC0-009
- AILY-RC0-010

Expected work:

- Run fresh Docker build/up/health/restart smoke.
- Prove env validation, no hardcoded secrets, and backup/restore guidance.

### Checkpoint 6: Chaos And Release Closure

Target IDs:

- AILY-RC0-011
- AILY-RC0-012

Expected work:

- Run six named chaos scenarios.
- Complete release docs and final rerun instructions.
- Only after all targets are closed, audit RC0 completion.

## Immediate Next Action

RC0 target evidence is closed. Preserve the current evidence set and do not
change target status without rerunning the affected target gate. Post-RC0 work
should focus on broader multi-document/provider soak and long-running hosted
operation, not on reclassifying the closed RC0 acceptance evidence.

### Checkpoint 4/5 Closure Addendum: DIKIWI And Studio Evidence Gates

Scope:

- Add target-specific auditors for AILY-RC0-005 and AILY-RC0-006:
  `scripts.audit_rc0_dikiwi_traceability`, `scripts.audit_rc0_note_quality`, and
  representative intake ledger builder `scripts.build_rc0_traceability_sample_ledger`.
- Repair DIKIWI generated note traceability so data/information/knowledge/
  insight/wisdom/impact notes carry source trace sections and resolving vault
  links.
- Reduce graph tag fanout so semantic relation edges are no longer drowned by
  bookkeeping tag edges.
- Extend Studio UI/API/browser evidence so AILY-RC0-008 covers real production
  failure/retry, URL intake, and browser inspection of real vault note summaries.

Expected failing proof before fixes:

- Previous strict DIKIWI audit failed on tag-edge dominance
  (`tag_edge_ratio=0.6711`).
- Previous note inspection showed generated data notes lacked graph-friendly
  links and knowledge/higher-order notes lacked consistent source paths.
- Previous Studio retry evidence used direct DB mutation and did not inspect a
  produced vault note/summary in-browser.

Rollback note:

- Revert the DIKIWI writer/agent propagation changes, the Studio vault note API,
  and the new audit scripts/tests if the auditors block valid real-provider
  output. Do not relax audit thresholds without a new real evidence run.

## Post-Commit Hardening Addendum: 2026-05-07

Scope:

- Address the fresh provider-gate failure where Moonshot timeout/429 pressure
  left DIKIWI at KNOWLEDGE while the full-pipeline scenario process exited 0.
- Preserve the anti-cheat rule: partial provider output is a visible failure,
  not acceptance evidence.

Changed plan decisions:

- Default provider retry budget is now `LLM_MAX_RETRIES=2`.
- Default request pacing is now `LLM_MIN_INTERVAL_SECONDS=6`.
- Docker deployment exposes the same retry/pacing knobs with
  `AILY_DOCKER_LLM_MAX_RETRIES` and `AILY_DOCKER_LLM_MIN_INTERVAL_SECONDS`.
- Full-pipeline scenario acceptance now requires DATA→IMPACT plus persisted
  Knowledge/Insight/Wisdom/Impact vault notes before returning a green CLI exit.

Fresh evidence:

- Failed control:
  `logs/runs/2026-05-07T_post_commit_provider_dikiwi_goal_audit/dikiwi-traceability-report.json`.
- Passing provider rerun:
  `logs/runs/2026-05-07T_post_hardening_provider_dikiwi_goal_audit/provider-dikiwi-gate-manifest.json`.
- Passing practical gate:
  `logs/runs/2026-05-07T_post_hardening_practical_goal_audit/manifest.json`.
- Passing Docker rerun:
  `logs/runs/2026-05-07T10-34-53Z_docker_preprod_retry_url_e2e/manifest.json`.

Rollback note:

- If provider cost or latency becomes unacceptable, tune the explicit env knobs;
  do not lower release gates to accept partial DIKIWI or provider-unverified
  traces.

### Clean-Commit Provider Timeout Follow-Up

A clean pushed-commit provider run at
`logs/runs/2026-05-07T_post_commit_clean_provider_dikiwi_goal_audit/` failed
because INFORMATION exceeded the old 240s DIKIWI stage timeout under real Kimi
latency/retry pressure. The failure was correctly terminal and visible after the
full-pipeline acceptance hardening.

Plan update:

- Use `DIKIWI_STAGE_TIMEOUT_SECONDS=600` as the default production/release
  timeout.
- Use a 1200s provider-gate phase timeout for the one-PDF RC0 provider gate.
- Preserve the 240s failure artifact as a negative control; do not reinterpret
  it as success.

### Final Clean Timeout-Budget Verification

After increasing DIKIWI stage timeout and provider-gate timeout budgets, a clean
pushed commit provider rerun passed at
`logs/runs/2026-05-07T_post_timeout_clean_provider_dikiwi_goal_audit/` with the
underlying evidence manifest on `c45bb3a9e8877b379926a2169b6b86ebf46e725b` and
`dirty_worktree=false`. Docker and practical gates also passed on the same clean
commit. This closes the timeout-budget follow-up unless a broader soak uncovers
new provider-specific limits.
