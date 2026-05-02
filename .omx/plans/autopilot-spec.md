# Autopilot Spec: Evidence-First Aily Development

Date: 2026-05-02

## Goal

Execute `docs/AILY_DEVELOPMENT_AND_TEST_MASTER_PLAN.md` incrementally until the private second-brain website is complete, with every product claim backed by real-path evidence.

## Requirements

- Add a reusable evidence writer and registry for real Aily runs.
- Capture run identity, git state, environment, source file hashes, vault counts, graph snapshots, logs, LLM trace paths, sample vault artifacts, failures, and acceptance flags.
- Wire the evidence writer into the existing full-pipeline scenario in `scripts/test_framework.py`.
- Add deterministic source selection for pressure tests.
- Add durable source-store records for Studio uploads before extraction.
- Surface source-store and evidence-run state in Aily Studio.
- Continue Phase 3+ work only with real-path acceptance tests and evidence artifacts.
- Preserve existing user changes in the worktree.

## Non-Goals

- Do not expose the website publicly.
- Do not use mocked LLM/provider outputs as acceptance proof. Real E2E and pressure claims require real provider calls.

## Acceptance

- Unit tests cover the evidence module.
- `scripts/run_test_suite.py full-pipeline` can emit an evidence directory path in its result.
- The evidence manifest contains `mocked=false`, `fake_components=[]`, and source hashes for accepted real-path runs.
- Generated evidence folders follow the structure defined in the master plan.
- Studio can list durable source records and run manifests from backend APIs.
