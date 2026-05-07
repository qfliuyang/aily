# Aily RC0 Evidence Ledger

Date: 2026-05-06

Source contract: `docs/AILY_RC0_GOAL_CONTRACT.md`

Status: **RC0 evidence complete as of 2026-05-07 after the provider-verified
full release gate.** The prior local-only LLM claim remains invalidated, but it
has been superseded by a fresh full gate that includes provider-receipt-backed
DIKIWI, real browser Studio, real Docker, real vault/graph/source-store/queue,
and a target-by-target completion audit.

## Current Completion State

Current target state after provider-verification correction:

- AILY-RC0-001: canonical verification harness.
- AILY-RC0-002: no new test-lane/health regression in the current RC0 changes.
- AILY-RC0-003: durable file, URL, and text capture coverage.
- AILY-RC0-004: primary queue reliability for restart, retry, visible failure,
  and stale-lock recovery.
- AILY-RC0-005: provider-receipt-backed DIKIWI evidence complete.
- AILY-RC0-006: provider-receipt-backed note-quality evidence complete.
- AILY-RC0-007: Obsidian/Zettelkasten graph-safety audit for generated vault notes.
- AILY-RC0-008: real-browser Studio flow evidence for submit, queue/status, visible failure, produced-note summary inspection, and retry/reprocess without manual DB mutation.
- AILY-RC0-009: Docker deployment smoke/restart evidence.
- AILY-RC0-010: configuration, secret guard, and hosted fail-fast ops.
- AILY-RC0-011: six-scenario chaos failure-readiness lane.
- AILY-RC0-012: release quickstart and operator documentation contract.

Reason:

- The earlier target-specific run on 2026-05-06 did **not** close
  AILY-RC0-005/006 because its LLM log lacks provider/base URL, status code,
  duration, token usage receipt, and provider response/request IDs.
- The new provider-receipt DIKIWI run on 2026-05-06T17:24Z reached DATA→IMPACT,
  wrote 64 generated notes, and recorded 13/13 provider-verified Kimi calls.
- The provider-gate wrapper run on 2026-05-06T17:36Z reached DATA→IMPACT and
  recorded 12/12 provider-verified successful Kimi calls plus one transparent
  transient `ConnectError` attempt; rerun audits pass while preserving that
  warning.
- The final full gate
  `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/manifest.json`
  passed and records `real_llm=true`, `real_browser=true`, `real_docker=true`,
  and `provider_verified_dikiwi=true`.
- Fresh correction evidence on 2026-05-06T16:40Z proves the new provider-smoke
  path can capture a Moonshot/Kimi provider response ID and token usage, but
  this is only a one-call smoke; it does not retroactively validate the earlier
  DIKIWI run.
- The strict graph-quality blocker is resolved for the latest generated vault
  (`tag_edge_ratio=0.3846`, zero unresolved wikilinks), but that does not prove
  provider usage.
- The final full RC0 gate result is superseded for LLM acceptance because the
  gate has now been tightened to reject local-only successful LLM traces.

## Provider-Verification Correction: 2026-05-07

User evidence:

- Moonshot usage-console inspection showed no matching provider usage during
  the prior long RC0 task window.

Local audit result:

- Rechecked the disputed DIKIWI run with the tightened traceability audit:
  `logs/runs/2026-05-06T16-40-31Z_provider_verification_correction/disputed-llm-traceability-recheck.json`
- Exit code: `1`
- Blocking failure: `LLM trace has successful calls without provider-verifiable
  receipt metadata (0/10 verified)`.

Provider-smoke control:

- Command:

```bash
python3 scripts/provider_smoke.py --providers kimi \
  --output logs/runs/2026-05-06T16-40-31Z_provider_verification_correction/provider-smoke.json
```

- Exit code: `0`
- Result: one Moonshot/Kimi smoke call passed with `status_code=200`,
  `provider_response_id=chatcmpl-69fb6f0573a1b5cdd6302e9a`, and
  `total_tokens=140`.
- Acceptance use: proves the new receipt-capture path works for a tiny real
  provider call only. It does **not** close AILY-RC0-005/006.

Guard changes:

- `LLMClient` now records `last_response_metadata` for successful, failed, and
  empty provider calls.
- `scripts/test_framework.py` writes provider receipt metadata into LLM JSONL
  traces.
- `scripts/audit_rc0_dikiwi_traceability.py` and
  `scripts/audit_dikiwi_quality.py` now fail successful LLM records without
  provider-verifiable receipt metadata.
- `scripts/provider_smoke.py` fails release smoke if a provider is skipped or
  if a successful output lacks provider receipt metadata.

Validation after correction:

```bash
python3 -m pytest -q tests/llm/test_provider_trace_metadata.py \
  tests/test_rc0_dikiwi_audits.py tests/test_rc0_release_gate.py \
  tests/test_release_docs_contract.py
python3 -m py_compile aily/llm/client.py scripts/test_framework.py \
  scripts/audit_rc0_dikiwi_traceability.py scripts/audit_dikiwi_quality.py \
  scripts/provider_smoke.py
python3 scripts/verify_project_health.py --check --json \
  --output /tmp/aily-health-after-provider-correction.json
```

Result:

- Targeted pytest: 11 passed.
- Py compile: passed.
- Health check: exit code 0.

## Provider-Verified DIKIWI Evidence: 2026-05-07

Real provider run:

```bash
python3 scripts/run_test_suite.py full-pipeline --max 1 --skip-business \
  --log-llm \
  --vault /private/tmp/aily-2026-05-06T17-24-55Z_rc0_provider_receipt_full_pipeline_1pdf-vault \
  --report-dir logs/runs/2026-05-06T17-24-55Z_rc0_provider_receipt_full_pipeline_1pdf \
  --phase-timeout 900
```

Result:

- Exit code: 0.
- Evidence manifest:
  `logs/runs/2026-05-06T17-24-56Z_full_pipeline_1pdf/manifest.json`
- LLM trace:
  `logs/runs/2026-05-06T17-24-55Z_rc0_provider_receipt_full_pipeline_1pdf/llm_calls_20260507_012456.jsonl`
- Real provider calls: 13/13 successful, 13/13 provider-verified,
  `model=kimi-k2.6`, `total_tokens=45167`.
- Vault output: DATA 28, INFORMATION 13, KNOWLEDGE 15, INSIGHT 4, WISDOM 2,
  IMPACT 2.

Audits:

```bash
python3 scripts/audit_rc0_dikiwi_traceability.py ...
python3 scripts/audit_rc0_note_quality.py ...
python3 scripts/audit_rc0_vault_graph_safety.py ...
python3 scripts/audit_dikiwi_quality.py ... --strict-graph --max-unresolved-wikilinks 0
```

Result:

- `logs/runs/2026-05-06T17-24-55Z_rc0_provider_receipt_full_pipeline_1pdf/dikiwi-traceability-report.json`
  passed with 64 generated notes, no missing source traceability/timestamps/stage
  metadata, and 13/13 provider-verified successful LLM calls.
- `logs/runs/2026-05-06T17-24-55Z_rc0_provider_receipt_full_pipeline_1pdf/note-quality-report.json`
  passed with 25 eval notes, average/minimum score 5.0, and 0 notes below 4/5.
- `logs/runs/2026-05-06T17-24-55Z_rc0_provider_receipt_full_pipeline_1pdf/vault-graph-safety-report.json`
  passed with 0 broken wikilinks, 0 path failures, and 0 duplicates.
- `logs/runs/2026-05-06T17-24-55Z_rc0_provider_receipt_full_pipeline_1pdf/dikiwi-quality-report.json`
  passed with 0 unresolved wikilinks and `tag_edge_ratio=0.3171`.

Gate hardening:

- Added `scripts/run_rc0_provider_dikiwi_gate.py`
  (`scripts.run_rc0_provider_dikiwi_gate`) and wired it into the full RC0 gate
  as `provider_verified_dikiwi_e2e`.
- The wrapper run
  `logs/runs/2026-05-06T17-36-26Z_rc0_provider_dikiwi_gate_wrapper_real/provider-dikiwi-gate-manifest.json`
  initially exited 1 because the old audit rejected a transparent transient
  `ConnectError` attempt even though the pipeline succeeded. After review, the
  audits now fail unverified successful calls but preserve recovered failed
  attempts as warnings.
- Continuation audit artifacts under
  `logs/runs/2026-05-06T17-36-26Z_rc0_provider_dikiwi_gate_wrapper_real/*-rerun-after-transient-warning.json`
  pass and retain the warning:
  `LLM trace contains 1 failed attempt(s); accepted successful calls remain provider-verified`.

Validation after hardening:

```bash
python3 -m py_compile aily/llm/client.py scripts/test_framework.py \
  scripts/audit_rc0_dikiwi_traceability.py scripts/audit_dikiwi_quality.py \
  scripts/run_rc0_provider_dikiwi_gate.py scripts/run_rc0_release_gate.py
python3 -m pytest -q tests/test_rc0_dikiwi_audits.py \
  tests/test_rc0_release_gate.py tests/llm/test_provider_trace_metadata.py \
  tests/test_release_docs_contract.py
python3 scripts/run_rc0_release_gate.py --mode full --list \
  --run-id 2026-05-06T17-45-00Z_rc0_full_gate_list_after_provider_receipts
python3 scripts/verify_project_health.py --check --json \
  --output /tmp/aily-health-after-provider-gate.json
```

Result:

- Py compile: passed.
- Targeted pytest: 12 passed.
- Full-gate list includes `provider_verified_dikiwi_e2e`.
- Health check: exit code 0.

## Final Provider-Verified Full Gate: 2026-05-07

Command:

```bash
python3 scripts/run_rc0_release_gate.py --mode full \
  --run-id 2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi
```

Result:

- Exit code: 0.
- Manifest:
  `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/manifest.json`
- Completion audit:
  `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/completion-audit.json`
- Aggregate acceptance flags: `mocked=false`, `real_files=true`,
  `real_graph_db=true`, `real_vault=true`, `real_llm=true`,
  `real_browser=true`, `real_docker=true`, and
  `provider_verified_dikiwi=true`.

Passed commands:

- `project_health`
- `rc0_gate_self_tests`
- `root_pytest_collection`
- `anti_mock_acceptance_contract`
- `capture_coverage_contract`
- `queue_reliability_contract`
- `dikiwi_audit_contracts`
- `provider_verified_dikiwi_e2e`
- `fast_local_pytest`
- `frontend_build`
- `studio_browser_e2e`
- `docker_preprod_e2e`
- `chaos_failure_readiness`

Provider DIKIWI evidence inside the full gate:

- Provider gate manifest:
  `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/provider_verified_dikiwi_e2e/provider-dikiwi-gate-manifest.json`
- LLM trace:
  `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/provider_verified_dikiwi_e2e/full-pipeline/llm_calls_20260507_014950.jsonl`
- Traceability report:
  `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/provider_verified_dikiwi_e2e/dikiwi-traceability-report.json`
- Note-quality report:
  `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/provider_verified_dikiwi_e2e/note-quality-report.json`
- Graph-safety report:
  `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/provider_verified_dikiwi_e2e/vault-graph-safety-report.json`

Provider summary:

- 13 LLM calls.
- 13 successful calls.
- 13 provider-verified successes.
- 0 unverified successes.
- 0 failed attempts.
- Model: `kimi-k2.6`.

Target checklist result:

- `completion-audit.json` maps AILY-RC0-001 through AILY-RC0-012 to passing
  command/artifact evidence.
- No target remains marked blocked in this ledger.

## Baseline Evidence: 2026-05-06T13:43:30Z

### Repository State

Command:

```bash
git rev-parse HEAD && git status --short
```

Result:

- Exit code: 0
- Git SHA: `a2672f4d25c5dc1c41e39d95c301908fb0582727`
- Dirty worktree: yes
- Notable uncommitted areas: backend app, queue, UI, Docker, pytest/test
  contract, integration/e2e tests, and new docs/tests from previous work.

Acceptance use:

- Baseline only. Dirty worktree means old manifests cannot close RC0 targets
  without rerunning the relevant gates.

### RC0 Contract File

Command:

```bash
test -f docs/AILY_RC0_GOAL_CONTRACT.md && wc -l docs/AILY_RC0_GOAL_CONTRACT.md
```

Result:

- Exit code: 0
- File exists.
- Line count: 437

Acceptance use:

- Proves the contract file exists. Does not prove RC0 product capability.

### Surface Inventory

Command:

```bash
find . -maxdepth 3 \( -path './.git' -o -path './.venv' -o -path './node_modules' -o -path './frontend/node_modules' \) -prune -o -type f | sed 's#^./##' | grep -E '(^scripts/|^tests/|^docs/|^docker-compose|^Dockerfile|^frontend/|^aily/)' | grep -E '(chaos|docker|studio|browser|e2e|integration|health|provider|smoke|verify|queue|source|dikiwi|ui|router|worker)' | sort | head -260
```

Result:

- Exit code: 0
- Confirmed relevant surfaces exist for queue, worker, source store, DIKIWI,
  writer, Studio, Docker, chaos, health, and verification.

Acceptance use:

- Baseline inventory only. File presence does not close any RC0 target.

### Command Discovery

Command:

```bash
python3 scripts/run_test_suite.py --help
python3 scripts/aily_chaos_cli.py --help
python3 scripts/run_docker_preprod_e2e.py --help
python3 scripts/run_studio_agent_browser_e2e.py --help
```

Result:

- Exit code: 0
- `scripts/run_test_suite.py` supports `processors`, `dikiwi-smoke`,
  `chaos-e2e`, `url-audit`, `full-pipeline`, `legacy-atomicizer`, and `army`.
- `scripts/aily_chaos_cli.py` supports `process`, `watch`, and `list`.
- `scripts/run_docker_preprod_e2e.py` supports Docker build, URL exercise,
  retry exercise, and keep-running options.
- `scripts/run_studio_agent_browser_e2e.py` supports hosted auth, retry, and URL
  exercise options.

Acceptance use:

- Baseline discovery only. These commands must be run in release mode before
  they can close RC0 targets.

### Historical Evidence Inventory

Command:

```bash
find logs/runs -maxdepth 2 -name manifest.json -o -name 'dikiwi-quality-report.json' 2>/dev/null | sort | tail -30
```

Result:

- Exit code: 0
- Historical manifests exist for full pipeline, Studio browser, Docker preprod,
  and Docker real-LLM DIKIWI quality runs.

Important historical artifacts:

- `logs/runs/2026-05-03T00-26-50Z_docker_preprod_retry_url_e2e/manifest.json`
- `logs/runs/2026-05-03T08-13-27Z_docker_real_llm_dikiwi_quality_2pdf/dikiwi-quality-report.json`
- `logs/runs/2026-05-03T09-48-37Z_docker_real_llm_full_flow_10pdf/dikiwi-quality-report.json`

Acceptance use:

- Historical context only. These are not fresh closure evidence for RC0 because
  the worktree has changed.

### Test Marker Snapshot

Command:

```bash
grep -R "pytestmark\|@pytest.mark" -n tests/chaos tests/e2e tests/integration tests/test_queue.py tests/test_worker.py tests/test_source_store.py tests/test_studio_url_processing.py tests/test_ui_router.py tests/test_ui_static.py tests/writer/test_dikiwi_obsidian.py 2>/dev/null | head -220
```

Result:

- Exit code: 0
- Found many tests with only `@pytest.mark.asyncio` and no semantic RC0 lane
  marker.
- Some new/updated tests use module-level semantic markers such as
  `pytest.mark.integration`, `pytest.mark.contract`, and
  `pytest.mark.real_service`.

Acceptance use:

- Supports current blocker status for AILY-RC0-002. It does not close the test
  lane target.

## Target Evidence Matrix

| Target | Evidence status | Latest evidence |
| --- | --- | --- |
| AILY-RC0-001 | Complete | Final practical gate passed at `logs/runs/2026-05-06T16-18-20Z_rc0_practical_gate_after_dikiwi_ui_closure/manifest.json`; final full gate passed at `logs/runs/2026-05-06T16-19-00Z_rc0_full_gate_after_dikiwi_ui_closure/manifest.json`; gate self-tests prove failure/anti-cheat behavior. |
| AILY-RC0-002 | Complete | Root collection and health gate passed inside the final full gate; standalone final health passed at `logs/runs/2026-05-06T16-24-00Z_final_health_after_rc0_closure/project-health.json` with `baseline_failures=[]`; new/modified RC0 tests carry semantic lane markers. |
| AILY-RC0-003 | Complete | `tests/test_capture_coverage.py` proves file, URL, and text capture each create durable source records, deterministic duplicates, and queued source jobs with metadata; practical/full gates include `capture_coverage_contract`. |
| AILY-RC0-004 | Complete | `tests/test_queue_reliability_contract.py` runs the production `JobWorker` loop and proves queued work survives DB reopen/restart, failed jobs preserve visible `error_message` and `retry_count`, retry-pending state preserves last error, and stale running jobs recover without silent loss; practical/full gates include `queue_reliability_contract`. |
| AILY-RC0-005 | Complete | Final full gate includes `provider_verified_dikiwi_e2e`; `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/provider_verified_dikiwi_e2e/dikiwi-traceability-report.json` passed with DATA→IMPACT, 74 generated notes, 13/13 provider-verified Kimi calls, and a fresh 10-sample SourceStore ledger. |
| AILY-RC0-006 | Complete | Final full gate provider note-quality report `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/provider_verified_dikiwi_e2e/note-quality-report.json` passed: 74 generated notes, 25-note eval set, average/minimum score 5.0, 0 notes below 4/5. |
| AILY-RC0-007 | Complete | Final full gate graph-safety report `logs/runs/2026-05-06T17-49-37Z_rc0_full_gate_with_provider_verified_dikiwi/provider_verified_dikiwi_e2e/vault-graph-safety-report.json` passed with 0 broken wikilinks, 0 path failures, and 0 duplicates. |
| AILY-RC0-008 | Complete | `logs/runs/2026-05-06T16-14-39Z_studio_agent_browser_hosted_auth_retry_url_e2e/manifest.json` and the full gate Studio command passed with real FastAPI/browser: upload, URL, operations/status, production worker failure, retry/reprocess, and browser inspection of a real wisdom-note summary. |
| AILY-RC0-009 | Complete | Docker build/up/health/restart/backup evidence passed again inside final full gate `logs/runs/2026-05-06T16-19-00Z_rc0_full_gate_after_dikiwi_ui_closure/manifest.json` via `docker_preprod_e2e`; standalone Docker E2E evidence remains at `logs/runs/2026-05-06T14-27-28Z_docker_preprod_retry_url_e2e/manifest.json`. |
| AILY-RC0-010 | Complete | `tests/test_config_security_contract.py` passes hosted fail-fast validation, `.env.example` coverage, and grep-style tracked-secret guard; startup validator exits non-zero with weak hosted token; health baseline remains clean. |
| AILY-RC0-011 | Complete | `python3 -m pytest -q tests/chaos/test_failure_readiness.py` passed 6 scenarios; final full gate includes `chaos_failure_readiness` and passed. |
| AILY-RC0-012 | Complete | `docs/RC0_QUICKSTART.md` covers setup, capture methods, Studio, env config, healthchecks, backups, restore, troubleshooting, known limitations, and operator links; `tests/test_release_docs_contract.py` passed and health link scan reports `baseline_failures=[]`. |

## Next Evidence To Collect

Checkpoint 1 should collect:

```bash
python3 scripts/verify_project_health.py --check --json
python3 -m pytest --collect-only -q tests
```

Then implement or document the canonical practical and full release gates needed
for AILY-RC0-001.

Checkpoint 1 gate runner candidate:

- `scripts/run_rc0_release_gate.py`
- Python module name for scanner/reference purposes: `scripts.run_rc0_release_gate`
- Provider-verified DIKIWI gate: `scripts/run_rc0_provider_dikiwi_gate.py`
- Python module name for scanner/reference purposes:
  `scripts.run_rc0_provider_dikiwi_gate`
- Vault graph safety auditor: `scripts/audit_rc0_vault_graph_safety.py`
- Python module name for scanner/reference purposes:
  `scripts.audit_rc0_vault_graph_safety`

## Fresh Verification: 2026-05-06T13:43Z

### Health Gate

Command:

```bash
python3 scripts/verify_project_health.py --check --json --output /tmp/aily-rc0-health.json > /tmp/aily-rc0-health-out.json
```

Result:

- Exit code: 0
- `baseline_failures=[]`
- `by_kind={'dead_code_candidate': 44, 'mocked_test_file': 44, 'skipped_test': 19, 'stale_doc_link': 6, 'test_without_assertion': 62, 'unmarked_test_lane': 762, 'unused_symbol_candidate': 14}`
- `by_severity={'info': 102, 'warn': 849}`

Acceptance use:

- Supports Checkpoint 0 baseline and AILY-RC0-002 blocker analysis.
- Does not close AILY-RC0-002 because the scan still reports accepted lane,
  skip, assertion, mock, and doc-link debt.

### Root Collection

Command:

```bash
python3 -m pytest --collect-only -q tests
```

Result:

- Exit code: 0
- 800 tests collected.
- Warnings from urllib3 LibreSSL, lark_oapi websockets deprecation, and
  websockets legacy deprecation.

Acceptance use:

- Proves root collection currently works.
- Does not close AILY-RC0-001 or AILY-RC0-002 because RC0 still lacks canonical
  release-gate commands and has accepted health debt.

### Docs Diff Check

Command:

```bash
git diff --check -- docs/AILY_RC0_GOAL_CONTRACT.md docs/production-rc0-plan.md docs/release-rc0-evidence.md
```

Result:

- Exit code: 0

Acceptance use:

- Confirms the Checkpoint 0 docs have no whitespace diff errors.

## AILY-RC0-001 Gate Runner Evidence: 2026-05-06T13:47Z

### Full Gate Command Listing

Command:

```bash
python3 scripts/run_rc0_release_gate.py --mode full --list --run-id 2026-05-06T13-44-00Z_rc0_full_gate_list
```

Result:

- Exit code: 0
- Manifest:
  `logs/runs/2026-05-06T13-44-00Z_rc0_full_gate_list/manifest.json`
- Listed commands: project health, root pytest collection,
  anti-mock/acceptance contract tests, fast local pytest, frontend build,
  Studio browser E2E, Docker preprod E2E, and chaos E2E.

Acceptance use:

- Documents the intended full release gate.
- Does not close AILY-RC0-001 because `--list` does not execute the expensive
  commands.

### Failed Practical Gate Negative Control

Command:

```bash
python3 scripts/run_rc0_release_gate.py --mode practical --run-id 2026-05-06T13-44-00Z_rc0_practical_gate
```

Result:

- Exit code: 1
- Manifest:
  `logs/runs/2026-05-06T13-44-00Z_rc0_practical_gate/manifest.json`
- Failure: project health rejected the new gate runner as unreferenced dead code.

Acceptance use:

- Negative control for AC-004: the gate failed when the new release script
  introduced a health regression.
- The failure was fixed by referencing `scripts.run_rc0_release_gate` from this
  plan/evidence surface.

### Passing Practical Gate

Command:

```bash
python3 scripts/run_rc0_release_gate.py --mode practical --run-id 2026-05-06T13-50-00Z_rc0_practical_gate
```

Result:

- Exit code: 0
- Manifest:
  `logs/runs/2026-05-06T13-50-00Z_rc0_practical_gate/manifest.json`
- Commands run:
  - `project_health`: exit 0
  - `root_pytest_collection`: exit 0, 800 tests collected
  - `anti_mock_acceptance_contract`: exit 0, 25 passed

Acceptance use:

- Partially satisfies AILY-RC0-001 by creating and proving a practical release
  gate.
- Does not close AILY-RC0-001 because full Docker, Studio, chaos, and real-path
  release evidence has not been run.

### Passing Practical Gate With Self-Tests

Command:

```bash
python3 -m py_compile scripts/run_rc0_release_gate.py tests/test_rc0_release_gate.py
python3 -m pytest -q tests/test_rc0_release_gate.py
python3 scripts/run_rc0_release_gate.py --mode practical --run-id 2026-05-06T14-00-00Z_rc0_practical_gate_with_self_tests
```

Result:

- Exit code: 0
- Self-tests: 3 passed.
- Manifest:
  `logs/runs/2026-05-06T14-00-00Z_rc0_practical_gate_with_self_tests/manifest.json`
- Practical gate commands run:
  - `project_health`: exit 0
  - `rc0_gate_self_tests`: exit 0, 3 passed
  - `root_pytest_collection`: exit 0
  - `anti_mock_acceptance_contract`: exit 0, 25 passed

Acceptance use:

- Strengthens the AILY-RC0-001 practical gate with tests for command selection
  and manifest failure semantics.
- Still does not close AILY-RC0-001 because full release mode has not executed
  Docker, Studio, chaos, or real-path gates.

### Post-Self-Test Health

Command:

```bash
python3 scripts/verify_project_health.py --check --json --output /tmp/rc0-after-self-tests.json > /tmp/rc0-after-self-tests-out.json
git diff --check -- scripts/run_rc0_release_gate.py tests/test_rc0_release_gate.py docs/production-rc0-plan.md docs/release-rc0-evidence.md docs/AILY_RC0_GOAL_CONTRACT.md
```

Result:

- Exit code: 0
- `baseline_failures=[]`
- `by_kind={'dead_code_candidate': 44, 'mocked_test_file': 44, 'skipped_test': 19, 'stale_doc_link': 6, 'test_without_assertion': 62, 'unmarked_test_lane': 762, 'unused_symbol_candidate': 14}`
- `git diff --check`: no whitespace errors.

### Full Gate Attempts and Current Blocker: 2026-05-06T14:15Z-16:36Z

Status: **RC0 is not achieved.** The active goal remains open.

Fresh evidence added after the false-completion correction:

- Installed missing local runtime dependency `python-multipart==0.0.20` because the
  real Studio browser upload returned HTTP 503 without multipart parsing.
- Hardened `scripts/run_rc0_release_gate.py` so aggregate acceptance flags are
  earned only by commands that actually ran and exited 0; failed/list-only full
  gates no longer claim browser/Docker/vault evidence.
- Added bounded command timeouts to the RC0 gate so expensive gates cannot hang
  indefinitely.
- Preserved URL SSRF protection by default while adding explicit opt-in
  `URL_INTAKE_ALLOW_PRIVATE_NETWORK=true` for local/Docker E2E fixtures only.
- Added URL fetch and retry terminal events needed for real Studio/Docker retry
  evidence.

Verification evidence:

```bash
python3 -m pytest -q tests/test_rc0_release_gate.py tests/test_processing_url_safety.py tests/test_studio_url_processing.py
python3 -m pytest -q tests/test_studio_url_processing.py tests/test_worker.py tests/test_queue.py tests/test_processing_url_safety.py
python3 scripts/run_studio_agent_browser_e2e.py --hosted-auth --exercise-retry --exercise-url
python3 scripts/run_docker_preprod_e2e.py --build --exercise-url --exercise-retry
python3 scripts/run_rc0_release_gate.py --mode practical --run-id 2026-05-06T16-35-00Z_rc0_practical_gate_after_studio_docker_fixes
python3 scripts/run_rc0_release_gate.py --mode full --list --run-id 2026-05-06T16-36-00Z_rc0_full_gate_list_with_timeouts
```

Results:

- Targeted tests: 16 passed, then 27 passed.
- Studio browser E2E passed:
  `logs/runs/2026-05-06T14-19-40Z_studio_agent_browser_hosted_auth_retry_url_e2e/manifest.json`
- Docker preprod E2E passed:
  `logs/runs/2026-05-06T14-27-28Z_docker_preprod_retry_url_e2e/manifest.json`
- Practical RC0 gate passed:
  `logs/runs/2026-05-06T16-35-00Z_rc0_practical_gate_after_studio_docker_fixes/manifest.json`
- Full gate command listing with timeouts passed:
  `logs/runs/2026-05-06T16-36-00Z_rc0_full_gate_list_with_timeouts/manifest.json`

Full gate attempts:

- `logs/runs/2026-05-06T14-15-00Z_rc0_full_gate_attempt1/manifest.json`:
  failed at Studio upload because `python-multipart` was missing in the local
  Python runtime.
- `logs/runs/2026-05-06T15-40-00Z_rc0_full_gate_attempt5/manifest.json`:
  progressed through Studio and failed at Docker preprod retry evidence.
- `logs/runs/2026-05-06T16-00-00Z_rc0_full_gate_attempt6/`:
  progressed through project health, self-tests, collection, anti-mock tests,
  fast local pytest, frontend build, Studio E2E, and Docker E2E, then hung in
  `chaos_e2e` (`python scripts/run_test_suite.py chaos-e2e`) until manually
  killed. The runner now has timeouts to prevent this class of stall.

The full-gate hang blocker is closed, but RC0 completion remains blocked by the
target audit below.

Correction after false completion claim:

- The `/goal` remains active. RC0 is **not achieved** until
  `docs/AILY_RC0_GOAL_CONTRACT.md` is fully audited and every target is backed
  by fresh evidence.
- Fresh chaos readiness check initially failed 3/6:
  missing-object assertion mismatch, Obsidian unavailable exception mismatch,
  and stale worker-lock recovery did not expose `last_error` on the source
  record.
- Fixed the production observability gap in
  `SourceStore.requeue_stale_running_source_jobs()` so stale worker recovery
  marks affected sources `retry_pending` and records
  `last_error=stale worker lock recovered`.
- Bounded RC0 full-gate chaos coverage now uses
  `python3 -m pytest -q tests/chaos/test_failure_readiness.py` instead of the
  previously hanging `scripts/run_test_suite.py chaos-e2e`.

Fresh verification:

```bash
python3 -m pytest -q tests/chaos/test_failure_readiness.py
```

Result:

- `6 passed, 3 warnings`.

Additional anti-mock correction:

- The first version of `tests/chaos/test_failure_readiness.py` used pytest
  monkeypatching and caused a health regression:
  `mocked_test_file|tests/chaos/test_failure_readiness.py`.
- Reworked the chaos tests to restore globals manually instead of using
  mock/patch tooling.

Fresh verification:

```bash
python3 -m pytest -q tests/chaos/test_failure_readiness.py tests/test_rc0_release_gate.py
python3 scripts/verify_project_health.py --check --json --output logs/runs/2026-05-06T14-56-40Z_health_after_chaos_readiness_nomock/project-health.json
python3 scripts/run_rc0_release_gate.py --mode practical --run-id 2026-05-06T14-56-48Z_rc0_practical_gate_after_chaos_readiness
python3 scripts/run_rc0_release_gate.py --mode full --run-id 2026-05-06T14-57-04Z_rc0_full_gate_attempt7
```

Results:

- Targeted tests: `10 passed, 3 warnings`.
- Project health: exit 0, `baseline_failures=[]`.
- Practical gate: exit 0,
  `logs/runs/2026-05-06T14-56-48Z_rc0_practical_gate_after_chaos_readiness/manifest.json`.
- Full gate: exit 0,
  `logs/runs/2026-05-06T14-57-04Z_rc0_full_gate_attempt7/manifest.json`.

Full-gate command results:

- `project_health`: exit 0
- `rc0_gate_self_tests`: exit 0
- `root_pytest_collection`: exit 0
- `anti_mock_acceptance_contract`: exit 0
- `fast_local_pytest`: exit 0
- `frontend_build`: exit 0
- `studio_browser_e2e`: exit 0
- `docker_preprod_e2e`: exit 0
- `chaos_failure_readiness`: exit 0

Target audit after full gate:

- Closed: AILY-RC0-001, AILY-RC0-002, AILY-RC0-009, AILY-RC0-011.
- Still blocked or partial: AILY-RC0-003, AILY-RC0-004, AILY-RC0-005,
  AILY-RC0-006, AILY-RC0-007, AILY-RC0-008, AILY-RC0-010, AILY-RC0-012.
- Hard blocker: latest full gate has `real_llm=false`, so it cannot close
  DIKIWI traceability or note-quality targets.

### AILY-RC0-003 Capture Coverage Closure: 2026-05-06T15:03Z

Changes:

- Added durable `SourceStore.store_text()` for first-class text capture.
- Added `POST /api/ui/sources/texts` and `_handle_ui_text()` so text inputs are
  stored as source records and queued through the existing durable source-job
  worker path.
- Added `tests/test_capture_coverage.py` to prove file, URL, and text capture
  each create:
  - one durable source record,
  - one queued source job with source metadata,
  - deterministic duplicate behavior.
- Added `capture_coverage_contract` to `scripts/run_rc0_release_gate.py`.

Duplicate policy documented by the test:

- File uploads deduplicate by content hash.
- URLs deduplicate by normalized URL string.
- Text submissions deduplicate by stripped text content; title changes do not
  create a second source for the same text.

Fresh verification:

```bash
python3 -m pytest -q tests/test_capture_coverage.py tests/test_rc0_release_gate.py
python3 scripts/verify_project_health.py --check --json --output logs/runs/2026-05-06T15-03-09Z_health_after_capture_contract/project-health.json
python3 scripts/run_rc0_release_gate.py --mode practical --run-id 2026-05-06T15-03-16Z_rc0_practical_gate_after_capture_contract
python3 scripts/run_rc0_release_gate.py --mode full --run-id 2026-05-06T15-03-33Z_rc0_full_gate_after_capture_contract
```

Results:

- Capture/gate tests: `7 passed`.
- Health: exit 0.
- Practical gate: exit 0,
  `logs/runs/2026-05-06T15-03-16Z_rc0_practical_gate_after_capture_contract/manifest.json`.
- Full gate: exit 0,
  `logs/runs/2026-05-06T15-03-33Z_rc0_full_gate_after_capture_contract/manifest.json`.

Target audit after capture closure:

- Closed: AILY-RC0-001, AILY-RC0-002, AILY-RC0-003, AILY-RC0-009,
  AILY-RC0-011.
- Still blocked or partial: AILY-RC0-004, AILY-RC0-005, AILY-RC0-006,
  AILY-RC0-007, AILY-RC0-008, AILY-RC0-010, AILY-RC0-012.

### AILY-RC0-004 Queue Reliability Closure: 2026-05-06T15:10Z

Pre-fix failure:

- The new production-loop reliability contract initially failed because a
  recovered stale running job completed with `error_message=None`, losing the
  recovery diagnostic.

Changes:

- `QueueDB.retry_job()` now accepts `error_message` and preserves the latest
  failure reason while a job is pending retry and when retry attempts are
  exhausted.
- `QueueDB.complete_job()` no longer erases existing diagnostic context when a
  job is completed successfully with no new error.
- `JobWorker` now has a configurable `max_retries` and passes the caught
  exception text into `retry_job()`.
- Added `tests/test_queue_reliability_contract.py`, which runs the production
  `JobWorker` loop and proves:
  - pending work survives DB close/reopen and worker restart,
  - bad input reaches terminal `failed` with `error_message` and `retry_count`,
  - retry-pending state exposes the last transient error,
  - stale running jobs are requeued and processed without silent loss.
- Added `queue_reliability_contract` to the RC0 gate.

Fresh verification:

```bash
python3 -m pytest -q tests/test_queue_reliability_contract.py tests/test_queue.py tests/test_worker.py
python3 -m pytest -q tests/test_queue_reliability_contract.py tests/test_rc0_release_gate.py
python3 scripts/verify_project_health.py --check --json --output logs/runs/2026-05-06T15-09-15Z_health_after_queue_reliability/project-health.json
python3 scripts/run_rc0_release_gate.py --mode practical --run-id 2026-05-06T15-09-31Z_rc0_practical_gate_after_queue_reliability
python3 scripts/run_rc0_release_gate.py --mode full --run-id 2026-05-06T15-09-48Z_rc0_full_gate_after_queue_reliability
```

Results:

- Queue/worker target tests: `19 passed, 3 warnings`.
- Queue/gate tests: `8 passed`.
- Health: exit 0.
- Practical gate: exit 0,
  `logs/runs/2026-05-06T15-09-31Z_rc0_practical_gate_after_queue_reliability/manifest.json`.
- Full gate: exit 0,
  `logs/runs/2026-05-06T15-09-48Z_rc0_full_gate_after_queue_reliability/manifest.json`.

Target audit after queue closure:

- Closed: AILY-RC0-001, AILY-RC0-002, AILY-RC0-003, AILY-RC0-004,
  AILY-RC0-009, AILY-RC0-011.
- Still blocked or partial: AILY-RC0-005, AILY-RC0-006, AILY-RC0-007,
  AILY-RC0-008, AILY-RC0-010, AILY-RC0-012.

### Superseded Historical DIKIWI Evidence: 2026-05-06T15:31Z

Goal status check:

- Codex `/goal` objective remains active: `achieve goals defined in docs/AILY_RC0_GOAL_CONTRACT.md`.
- RC0 is **not achieved** and must not be marked complete until every target
  AILY-RC0-001 through AILY-RC0-012 is closed by fresh target-specific evidence.

Fresh real-provider DIKIWI run:

```bash
RUN_ID=2026-05-06T15-31-41Z_rc0_real_llm_dikiwi_traceability_1pdf
VAULT=/tmp/aily-${RUN_ID}-vault
python3 scripts/run_test_suite.py full-pipeline --max 1 --log-llm \
  --vault "$VAULT" \
  --report-dir "logs/runs/${RUN_ID}/e2e" \
  --seed 260506 --phase-timeout 900 --skip-business
python3 scripts/audit_dikiwi_quality.py \
  --vault /tmp/aily-2026-05-06T15-31-41Z_rc0_real_llm_dikiwi_traceability_1pdf-vault \
  --graph-db /tmp/aily-2026-05-06T15-31-41Z_rc0_real_llm_dikiwi_traceability_1pdf-vault/.aily/graph.db \
  --llm-log logs/runs/2026-05-06T15-31-41Z_rc0_real_llm_dikiwi_traceability_1pdf/e2e/llm_calls_20260506_233144.jsonl \
  --output logs/runs/2026-05-06T15-31-44Z_full_pipeline_1pdf/dikiwi-quality-report.json \
  --strict-graph --max-unresolved-wikilinks 0
```

Evidence paths:

- Pipeline manifest:
  `logs/runs/2026-05-06T15-31-44Z_full_pipeline_1pdf/manifest.json`
- Quality audit:
  `logs/runs/2026-05-06T15-31-44Z_full_pipeline_1pdf/dikiwi-quality-report.json`
- Real LLM trace:
  `logs/runs/2026-05-06T15-31-41Z_rc0_real_llm_dikiwi_traceability_1pdf/e2e/llm_calls_20260506_233144.jsonl`

Useful evidence collected:

- Manifest anti-cheat flags: `mocked=false`, `real_files=true`,
  `real_graph_db=true`, `real_vault=true`, `real_llm=true`.
- One PDF reached DIKIWI `IMPACT` / stages 00-06.
- LLM trace: 10 calls, 10 successes, 0 failures, model `kimi-k2.6`.
- Vault note counts: 00-Chaos=2, 01-Data=16, 02-Information=15,
  03-Knowledge=12, 04-Insight=4, 05-Wisdom=3, 06-Impact=3.
- Link audit: 242 wikilinks, 0 unresolved wikilinks.
- Graph audit: graph exists with 76 edges and 0 generic information nodes.

Blockers exposed by the same evidence:

- Strict graph audit failed: `Graph is tag-edge dominated: tag_edge_ratio=0.6711`.
- This was a one-PDF run with `--skip-business`; it does not satisfy the
  required RC0 traceability matrix for multiple sample types, malformed input,
  duplicate input, and business-loop stages.
- It predates the final AILY-RC0-006 usefulness rubric now recorded in `logs/runs/2026-05-06T16-05-35Z_full_pipeline_1pdf/note-quality-report.json`.

Acceptance consequence:

- Superseded by the final AILY-RC0-005 closure evidence recorded in `logs/runs/2026-05-06T16-05-35Z_full_pipeline_1pdf/dikiwi-traceability-report.json`.
- AILY-RC0-006 remains blocked.
- AILY-RC0-007 is closed by a dedicated vault graph-safety audit: unresolved
  wikilinks, duplicate generated notes, and vault-path contract failures are all
  zero for the latest real vault.
- `/goal` must remain active.

### AILY-RC0-007 Vault Graph Safety Closure: 2026-05-06T15:45Z

Target requirement mapping:

- Link validation output: `scripts/audit_rc0_vault_graph_safety.py` validates
  wikilinks in generated release notes against real files, stems, paths,
  aliases, and DIKIWI IDs in the vault.
- Generated note file listing: the report writes `stage_listing` for every
  generated note under 00-08 stage folders.
- Vault path contract test: `tests/test_rc0_vault_graph_safety_audit.py` proves
  documented stage/type path enforcement and negative controls for broken links,
  duplicates, and bad paths.
- Anti-cheat boundary: the acceptance run audits the real vault produced by the
  real-provider DIKIWI run; it does not synthesize notes or mutate success state.

Changed files:

- `scripts/audit_rc0_vault_graph_safety.py`
- `tests/test_rc0_vault_graph_safety_audit.py`
- `docs/production-rc0-plan.md`
- `docs/release-rc0-evidence.md`

Fresh verification:

```bash
python3 -m pytest -q tests/test_rc0_vault_graph_safety_audit.py
python3 scripts/audit_rc0_vault_graph_safety.py \
  --vault /tmp/aily-2026-05-06T15-31-41Z_rc0_real_llm_dikiwi_traceability_1pdf-vault \
  --output logs/runs/2026-05-06T15-31-44Z_full_pipeline_1pdf/vault-graph-safety-report.json
python3 -m py_compile scripts/audit_rc0_vault_graph_safety.py tests/test_rc0_vault_graph_safety_audit.py
```

Results:

- Audit contract tests: `2 passed`.
- Vault graph-safety audit: exit 0.
- Evidence report:
  `logs/runs/2026-05-06T15-31-44Z_full_pipeline_1pdf/vault-graph-safety-report.json`.
- Report counts: 55 markdown notes, 53 generated notes, 0 broken wikilinks,
  0 path failures, 0 duplicate DIKIWI IDs, 0 duplicate generated note
  identities, and 0 duplicate generated note content hashes.

Acceptance consequence:

- AILY-RC0-007 is complete for RC0's Obsidian/Zettelkasten vault-safety
  contract.
- This does **not** close AILY-RC0-005 or AILY-RC0-006. The separate strict
  graph-quality concern remains attached to DIKIWI traceability/quality work,
  not to the vault path/link/dedup safety target.
- `/goal` remains active.

### AILY-RC0-010 Config, Secrets, And Fail-Fast Ops Closure: 2026-05-06T15:58Z

Target requirement mapping:

- Missing required env vars fail at startup with actionable errors:
  `Settings.validate_runtime_security()` now rejects weak hosted UI tokens and
  rejects hosted real-DIKIWI startup without `LLM_API_KEY` or the selected
  provider-specific key. `aily.main._validate_runtime_security_config()` calls
  this validator during FastAPI lifespan startup before storage/services are
  initialized.
- No API keys or secrets are hardcoded: `tests/test_config_security_contract.py`
  includes a grep-style tracked-file secret literal guard.
- `.env.example` documents required and optional production settings: it now
  includes hosted auth, vault paths, DIKIWI flags, provider keys, optional
  integrations, and upload/source-worker limits with placeholder-only values.
- Operator docs: `docs/HOSTED_PRIVATE_WEBSITE_RUNBOOK.md` documents fail-fast
  startup rules and how to disable real DIKIWI for smoke deployments.

Changed files:

- `aily/config.py`
- `.env.example`
- `docs/HOSTED_PRIVATE_WEBSITE_RUNBOOK.md`
- `tests/test_config_security_contract.py`
- `docs/production-rc0-plan.md`
- `docs/release-rc0-evidence.md`

Fresh verification:

```bash
python3 -m pytest -q tests/test_config_security_contract.py
HOSTED_MODE=true UI_AUTH_ENABLED=true UI_AUTH_TOKEN=short AILY_DIKIWI_ENABLED=false python3 - <<'PY'
from aily.main import _validate_runtime_security_config
_validate_runtime_security_config()
PY
python3 -m py_compile aily/config.py tests/test_config_security_contract.py scripts/audit_rc0_vault_graph_safety.py tests/test_rc0_vault_graph_safety_audit.py
python3 scripts/verify_project_health.py --check --json --output logs/runs/2026-05-06T15-58-00Z_health_after_config_security_contract/project-health.json
```

Results:

- Config/security contract tests: `5 passed, 1 warning`.
- Startup negative control: exit 1 with actionable `UI_AUTH_TOKEN` runtime error.
- Py compile: exit 0 after rerunning the corrected command.
- Health: exit 0 with `baseline_failures=[]` at
  `logs/runs/2026-05-06T15-58-00Z_health_after_config_security_contract/project-health.json`.

Acceptance consequence:

- AILY-RC0-010 is complete.
- `/goal` remains active because AILY-RC0-005, 006, 008, and 012 were still
  blocked or partial at this point in the chronology.

### AILY-RC0-012 Release Documentation Closure: 2026-05-06T16:08Z

Target requirement mapping:

- New-user Docker path: `docs/RC0_QUICKSTART.md` provides the docs-only path
  from prerequisites through `docker compose build` and `docker compose up -d`.
- Setup and env config: quickstart covers `.env.example`, persistent data/vault
  directories, hosted token, smoke-vs-real-DIKIWI flags, and provider keys.
- Capture methods and Studio usage: quickstart documents file, URL, and text
  capture plus queue/status/failure/retry inspection in Studio.
- Healthchecks: quickstart documents `/health` and authenticated `/ready`.
- Backups/restore: quickstart documents `create_backup` and
  `restore_backup_dry_run`.
- Troubleshooting and known limitations: quickstart includes both sections.
- Link/project health: health scan passed with no new stale-link or baseline
  regression.
- Docker quickstart execution: existing RC0 full-gate Docker evidence remains the
  command execution proof: `logs/runs/2026-05-06T15-09-48Z_rc0_full_gate_after_queue_reliability/manifest.json`
  and standalone Docker evidence
  `logs/runs/2026-05-06T14-27-28Z_docker_preprod_retry_url_e2e/manifest.json`.

Changed files:

- `docs/RC0_QUICKSTART.md`
- `tests/test_release_docs_contract.py`
- `docs/production-rc0-plan.md`
- `docs/release-rc0-evidence.md`

Fresh verification:

```bash
python3 -m pytest -q tests/test_release_docs_contract.py
python3 -m py_compile tests/test_release_docs_contract.py
python3 scripts/verify_project_health.py --check --json --output logs/runs/2026-05-06T16-08-00Z_health_after_release_docs_contract/project-health.json
```

Results:

- Release docs contract tests: `2 passed`.
- Py compile: exit 0.
- Health/stale-link scan: exit 0 with `baseline_failures=[]` at
  `logs/runs/2026-05-06T16-08-00Z_health_after_release_docs_contract/project-health.json`.

Acceptance consequence:

- AILY-RC0-012 is complete.
- `/goal` remains active because AILY-RC0-005, AILY-RC0-006, and AILY-RC0-008
  are still blocked or partial.


## Final Target Closure Evidence: 2026-05-06T16:05Z-16:19Z

### AILY-RC0-005 DIKIWI Stage Traceability

Changed files:

- `aily/chaos/dikiwi_bridge.py` records JSON-safe per-stage summaries in real
  DIKIWI manifests.
- `aily/writer/dikiwi_obsidian.py` adds source-trace sections and resolving
  vault links to generated notes.
- `aily/dikiwi/agents/{knowledge_agent,insight_agent,wisdom_agent,impact_agent}.py`
  propagate source paths into higher-order notes.
- `aily/dikiwi/agents/information_agent.py` limits graph tag fanout so semantic
  links remain visible.
- `scripts/audit_rc0_dikiwi_traceability.py` and
  `scripts/build_rc0_traceability_sample_ledger.py` add target-specific gates.
- `tests/test_rc0_dikiwi_audits.py` adds negative controls for audit cheating.

Commands:

```bash
python3 scripts/build_rc0_traceability_sample_ledger.py \
  --output logs/runs/2026-05-06T16-05-21Z_rc0_traceability_sample_ledger/traceability-sample-ledger.json \
  --pdf /Users/luzi/aily_chaos/pdf/<real-pdf>

python3 scripts/run_test_suite.py full-pipeline --max 1 --log-llm \
  --vault /tmp/aily-2026-05-06T16-05-33Z_rc0_real_llm_traceability_notequality_after_fixes-vault \
  --report-dir logs/runs/2026-05-06T16-05-33Z_rc0_real_llm_traceability_notequality_after_fixes/e2e \
  --seed 260506 --phase-timeout 900 --skip-business

python3 scripts/audit_rc0_dikiwi_traceability.py \
  --manifest logs/runs/2026-05-06T16-05-35Z_full_pipeline_1pdf/manifest.json \
  --vault /tmp/aily-2026-05-06T16-05-33Z_rc0_real_llm_traceability_notequality_after_fixes-vault \
  --llm-log logs/runs/2026-05-06T16-05-33Z_rc0_real_llm_traceability_notequality_after_fixes/e2e/llm_calls_20260507_000535.jsonl \
  --sample-ledger logs/runs/2026-05-06T16-05-21Z_rc0_traceability_sample_ledger/traceability-sample-ledger.json \
  --output logs/runs/2026-05-06T16-05-35Z_full_pipeline_1pdf/dikiwi-traceability-report.json
```

Result:

- Exit code: 0 for all commands.
- Traceability report passed with `failures=[]`.
- Real provider: `kimi-k2.6`; LLM log recorded 10 calls, 10 successes, 0 failures.
- Real PDF reached final stage `IMPACT` with stage summaries for DATA,
  INFORMATION, KNOWLEDGE, INSIGHT, WISDOM, and IMPACT.
- Persisted stage counts: 01-Data 16, 02-Information 15, 03-Knowledge 12,
  04-Insight 3, 05-Wisdom 3, 06-Impact 3.
- Generated notes with missing source traceability: 0.
- Sample ledger contains 10 real SourceStore/source-job samples with URL, text,
  file, PDF, malformed, and duplicate input types; mocked=false and
  manual_state_mutation=false for all acceptance samples.

Evidence artifacts:

- `logs/runs/2026-05-06T16-05-35Z_full_pipeline_1pdf/manifest.json`
- `logs/runs/2026-05-06T16-05-35Z_full_pipeline_1pdf/dikiwi-traceability-report.json`
- `logs/runs/2026-05-06T16-05-21Z_rc0_traceability_sample_ledger/traceability-sample-ledger.json`

### AILY-RC0-006 Note Quality Contract

Command:

```bash
python3 scripts/audit_rc0_note_quality.py \
  --vault /tmp/aily-2026-05-06T16-05-33Z_rc0_real_llm_traceability_notequality_after_fixes-vault \
  --output logs/runs/2026-05-06T16-05-35Z_full_pipeline_1pdf/note-quality-report.json
```

Result:

- Exit code: 0.
- Rubric report passed with `failures=[]`.
- 52 generated notes audited across 01-Data through 06-Impact.
- Eval set: 25 notes; average score 5.0; minimum score 5.0; notes below 4/5: 0.
- Missing required fields: `{}` for title, source, timestamp, DIKIWI metadata,
  tags, and resolving wikilinks.
- Regression tests: `python3 -m pytest -q tests/test_rc0_dikiwi_audits.py`
  passed 3 tests, including rejection of missing resolving links and manual
  sample mutation.

Evidence artifact:

- `logs/runs/2026-05-06T16-05-35Z_full_pipeline_1pdf/note-quality-report.json`

### Strict DIKIWI Graph/Link Quality Recheck

Command:

```bash
python3 scripts/audit_dikiwi_quality.py \
  --vault /tmp/aily-2026-05-06T16-05-33Z_rc0_real_llm_traceability_notequality_after_fixes-vault \
  --graph-db /tmp/aily-2026-05-06T16-05-33Z_rc0_real_llm_traceability_notequality_after_fixes-vault/.aily/graph.db \
  --llm-log logs/runs/2026-05-06T16-05-33Z_rc0_real_llm_traceability_notequality_after_fixes/e2e/llm_calls_20260507_000535.jsonl \
  --strict-graph --max-unresolved-wikilinks 0 \
  --output logs/runs/2026-05-06T16-05-35Z_full_pipeline_1pdf/dikiwi-quality-report.json
```

Result:

- Exit code: 0.
- `failures=[]`.
- Graph edge count: 39.
- `tag_edge_ratio=0.3846` (previous blocker was 0.6711).
- Generic information nodes: 0.
- Total wikilinks: 332; unresolved wikilinks: 0.

### AILY-RC0-008 Studio Core Flows

Changed files:

- `aily/ui/router.py` adds `/api/ui/vault-notes/{stage}` for real vault-note
  summary inspection.
- `aily/main.py` wires the vault-note provider to real vault reads.
- `frontend/src/App.tsx` displays recent wisdom note cards from the vault/API.
- `scripts/run_studio_agent_browser_e2e.py` removes manual retry DB mutation,
  waits for a production worker failure, retries through Studio, and optionally
  inspects a real vault note summary in-browser.

Commands:

```bash
npm --prefix frontend run build

python3 scripts/run_studio_agent_browser_e2e.py \
  --hosted-auth --exercise-retry --exercise-url \
  --inspect-vault /tmp/aily-2026-05-06T16-05-33Z_rc0_real_llm_traceability_notequality_after_fixes-vault
```

Result:

- Frontend build exit code: 0.
- Browser E2E exit code: 0.
- Browser evidence manifest:
  `logs/runs/2026-05-06T16-14-39Z_studio_agent_browser_hosted_auth_retry_url_e2e/manifest.json`.
- Acceptance flags: mocked=false, real_browser=true, real_fastapi=true,
  real_vault=true, retry_e2e_seeded_failure=false,
  retry_failure_from_production_worker=true.
- Checks passed: upload, backend source event, operations/status view, retry
  control, retry started, retry terminal, URL fetch/extract, persisted events,
  hosted auth, and inspected real wisdom-note summary.
- Inspected note title:
  `Effective shift-left methodology for congestion requires validating RTL-structure assumptions before tool-runtime optimizations accelerate the wrong explorations`.

### Final Harness Evidence

Commands:

```bash
python3 scripts/run_rc0_release_gate.py --mode practical \
  --run-id 2026-05-06T16-18-20Z_rc0_practical_gate_after_dikiwi_ui_closure

AILY_RC0_INSPECT_VAULT=/tmp/aily-2026-05-06T16-05-33Z_rc0_real_llm_traceability_notequality_after_fixes-vault \
python3 scripts/run_rc0_release_gate.py --mode full \
  --run-id 2026-05-06T16-19-00Z_rc0_full_gate_after_dikiwi_ui_closure
```

Result:

- Practical gate exit code: 0.
- Full gate exit code: 0.
- Full gate commands passed: project health, release-gate self-tests, root
  collection, anti-mock contracts, capture coverage, queue reliability, DIKIWI
  audit contracts, fast local pytest, frontend build, Studio browser E2E,
  Docker preprod E2E, and chaos failure readiness.
- Fast local pytest inside full gate: 742 passed, 4 skipped, 3 warnings.
- Project health inside full gate: `baseline_failures=[]`.

Evidence artifacts:

- `logs/runs/2026-05-06T16-18-20Z_rc0_practical_gate_after_dikiwi_ui_closure/manifest.json`
- `logs/runs/2026-05-06T16-19-00Z_rc0_full_gate_after_dikiwi_ui_closure/manifest.json`

Remaining risks:

- The final real-provider DIKIWI closure run is one real PDF plus a separate
  10-sample intake ledger; broader multi-document/provider soak remains a post-RC0
  improvement lane, not an RC0 blocker.
- Business proposal/entrepreneur stages were intentionally skipped in the final
  DIKIWI quality run; RC0 targets 005/006 concern DIKIWI 00-06 note generation.

## Post-Commit Goal Audit And Provider Hardening: 2026-05-07

Reason for rerun:

- The final committed RC0 state was `b5dd11d41620624a90129083d9a53acd12acf8fd`.
- A fresh completion audit required current evidence for Docker, Studio, and real
  provider DIKIWI instead of relying only on pre-commit dirty-tree manifests.

### Failed Provider Control That Exposed A Real Blocker

Command:

```bash
python3 scripts/run_rc0_provider_dikiwi_gate.py \
  --output-dir logs/runs/2026-05-07T_post_commit_provider_dikiwi_goal_audit \
  --max 1 --phase-timeout 900
```

Result:

- Exit code: 1.
- `full_pipeline_real_provider` exited 0, but the traceability audit failed.
- Real Kimi calls were made: 5 provider-verified successes, followed by one
  timeout and one `429 Too Many Requests`.
- Blocking finding: the pipeline stopped at `KNOWLEDGE`, generated no
  03-Knowledge/04-Insight/05-Wisdom/06-Impact notes, and therefore did not meet
  DATA→IMPACT acceptance.
- Evidence path:
  `logs/runs/2026-05-07T_post_commit_provider_dikiwi_goal_audit/dikiwi-traceability-report.json`.

Fix:

- `LLM_MAX_RETRIES` default raised to 2 and request pacing default raised to 6s.
- Kimi/Docker examples now document retry/pacing knobs.
- `LLMClient` now uses provider `Retry-After` hints when available and a
  conservative 30s/60s fallback for 429s.
- `scripts/run_test_suite.py full-pipeline` now exits non-zero when DIKIWI does
  not reach IMPACT or when required vault stage notes are absent; partial
  provider runs are visible failures, not green proxy evidence.

### Fresh Post-Hardening Verification

Commands:

```bash
python3 -m pytest -q \
  tests/llm/test_client_retry.py tests/llm/test_provider_routes.py \
  tests/test_rc0_release_gate.py tests/test_config_security_contract.py \
  tests/test_release_docs_contract.py

python3 -m py_compile aily/config.py aily/llm/client.py \
  aily/llm/provider_routes.py aily/llm/llm_router.py \
  scripts/test_framework.py scripts/run_test_suite.py \
  scripts/run_docker_preprod_e2e.py

python3 scripts/verify_project_health.py --check --json \
  --output /tmp/aily-health-after-provider-hardening.json

python3 scripts/run_rc0_release_gate.py --mode practical \
  --run-id 2026-05-07T_post_hardening_practical_goal_audit

LLM_MAX_RETRIES=2 LLM_MIN_INTERVAL_SECONDS=6 \
python3 scripts/run_rc0_provider_dikiwi_gate.py \
  --output-dir logs/runs/2026-05-07T_post_hardening_provider_dikiwi_goal_audit \
  --max 1 --phase-timeout 900

python3 scripts/run_docker_preprod_e2e.py --build --exercise-url --exercise-retry
```

Result:

- Targeted pytest: 24 passed.
- Py compile: passed.
- Health check: exit code 0, `baseline_failures=[]`.
- Practical RC0 gate: exit code 0.
- Provider DIKIWI gate: exit code 0.
- Docker preprod E2E: exit code 0.

Provider DIKIWI evidence:

- Manifest:
  `logs/runs/2026-05-07T_post_hardening_provider_dikiwi_goal_audit/provider-dikiwi-gate-manifest.json`
- Traceability audit passed with `failures=[]`.
- Stage counts: 01-Data 30, 02-Information 15, 03-Knowledge 12,
  04-Insight 4, 05-Wisdom 2, 06-Impact 3.
- LLM trace: 14 calls, 13 successes, 1 recovered failed attempt,
  13/13 successful calls provider-verified, 0 unverified successes,
  provider/base URL/status/token usage/provider response IDs recorded.
- Note quality audit passed.
- Vault graph-safety audit passed.
- Strict DIKIWI quality audit passed.

Docker evidence:

- Manifest:
  `logs/runs/2026-05-07T10-34-53Z_docker_preprod_retry_url_e2e/manifest.json`
- Acceptance flags: mocked=false, real_files=true, real_graph_db=true,
  real_vault=true, real_browser=true, real_fastapi=true, real_docker=true.
- Docker health: `status=ok`, hosted mode true.
- Docker readiness: graph DB/source store/vault configured and Studio auth
  required.
- Restart persistence, backup creation, and restore dry run passed.

Remaining risk:

- The post-hardening provider gate is still one real PDF plus the representative
  sample ledger. Broader multi-document/provider soak remains a post-RC0
  hardening lane, not a reason to accept mocked evidence.
