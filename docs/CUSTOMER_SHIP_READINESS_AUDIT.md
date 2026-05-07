# Aily Customer Ship Readiness Audit

Date: 2026-05-07

Customer-ready status: Not achieved.

This audit is stricter than the RC0 private second-brain evidence. RC0 evidence
can show that important real paths exist, but it does not by itself prove that
Aily is ready to ship to customers. A customer-ready claim must be backed by one
current, clean, reproducible evidence chain for the shipped path, not by a mix of
stale, dirty, backend-only, UI-only, or private-operator proofs.

## Objective Restated As Deliverables

The current long-running objective says: update Aily to a Docker deployed, web UI
featured, full-function tool with all functions ready to ship to customers.

For audit purposes this means:

| ID | Deliverable | Customer-ready success criterion | Current status |
| --- | --- | --- | --- |
| CSHIP-001 | Docker deployment | Clean current-HEAD Docker Compose evidence with real Docker, FastAPI, browser, persisted vault, and graph DB. | Passing control-plane evidence exists. |
| CSHIP-002 | Interactive web UI | Clean current-HEAD real-browser Studio evidence against FastAPI and persisted backend state. | Passing control-plane evidence exists. |
| CSHIP-003 | Full-function DIKIWI second brain | Clean current-HEAD provider-verified DATA→IMPACT run with real provider calls, vault notes, and graph rows. | Blocked/stale for customer claim: latest clean provider proof is not on the final docs HEAD and is backend-only. |
| CSHIP-004 | No split-brain customer proof | One clean current-HEAD customer scenario combines Docker + real browser + real provider LLM + real DIKIWI outputs. | Blocked: current proof is split across separate UI/Docker control-plane and backend provider runs. |
| CSHIP-005 | Traceable customer-readiness contract | Durable audit maps requirements to evidence and blockers before any customer-ready claim. | This document plus `scripts/audit_customer_ship_readiness.py`. |

## Prompt-To-Artifact Checklist

| Requirement from prompt | Evidence inspected | Coverage verdict |
| --- | --- | --- |
| Docker deployed | `Dockerfile`, `docker-compose.yml`, `docker-compose.preprod.yml`, `docs/DOCKER_PREPROD.md`, and `logs/runs/2026-05-07T11-09-48Z_docker_preprod_retry_url_e2e/manifest.json` on `6423e4652df6607780b4c90e74b173f4116cefb4`. | Good for current-head Docker control-plane deployment. Not enough for customer shipping with real LLM inside Docker. |
| Web UI featured | `frontend/src/App.tsx`, `aily/ui/router.py`, `docs/RC0_QUICKSTART.md`, and `logs/runs/2026-05-07T11-09-01Z_studio_agent_browser_hosted_auth_retry_url_e2e/manifest.json` on `6423e4652df6607780b4c90e74b173f4116cefb4`. | Good for current-head real-browser Studio control-plane behavior. Not enough for full real-LLM browser acceptance. |
| Full-function tool | `logs/runs/2026-05-07T_post_timeout_clean_provider_dikiwi_goal_audit/dikiwi-traceability-report.json` and `logs/runs/2026-05-07T10-47-37Z_full_pipeline_1pdf/manifest.json`. | Real provider DATA→IMPACT proof exists, but it is backend-only and on parent commit `c45bb3a9e8877b379926a2169b6b86ebf46e725b`; customer claim needs current-head and shipped-path proof. |
| Ready to ship to customers | `docs/CURRENT_STATE.md`, `docs/AILY_DEVELOPMENT_AND_TEST_MASTER_PLAN.md`, RC0 evidence docs, current manifests, and this audit. | Not achieved. Existing docs explicitly call out missing full real-LLM browser E2E, richer media, unfinished queue-backed ingestion model, incomplete lineage, and private/single-owner rather than customer-grade posture. |
| Anti-mock / anti-cheat | `docs/AILY_RC0_GOAL_CONTRACT.md`, `tests/verify/test_no_mock_acceptance.py`, `scripts/run_rc0_provider_dikiwi_gate.py`, `scripts/audit_customer_ship_readiness.py`. | RC0 anti-mock guardrails exist. Customer readiness now also fails closed when evidence is stale, split, or scoped. |

## Blocking gaps

1. No single current-head evidence run proves the shipped customer path end to end
   with Docker, browser, FastAPI, real provider LLM, real vault, real graph DB,
   and DATA→IMPACT outputs together.
2. Current browser and Docker evidence is intentionally UI/control-plane scoped:
   `real_llm=false` in the current manifests.
3. The latest clean provider evidence proves the backend DIKIWI path, but not the
   final docs HEAD and not the browser/Docker customer path.
4. Existing planning docs still describe future gaps: full real-LLM browser E2E,
   richer media productization, durable queue-backed ingestion completion,
   cross-artifact lineage, and performance hardening.
5. Customer shipping posture is not yet defined beyond private hosted mode:
   support, upgrade/migration, security model, observability, and customer data
   handling need explicit gates before a customer-ready claim.

## Next verification checkpoint

Run the customer-readiness audit after each ship-readiness slice:

```bash
python3 scripts/audit_customer_ship_readiness.py --output logs/customer-ship-readiness.json
```

The command must exit non-zero until every CSHIP criterion passes with current,
clean, real-boundary evidence. Passing RC0 gates can remain useful evidence, but
it is not sufficient to mark customer shipping complete.

## Next implementation target

The next concrete engineering target is CSHIP-004: create a single Docker-based
customer E2E path that starts the shipped Compose stack with provider credentials,
submits a document through Studio in a real browser, waits for DATA→IMPACT output,
and verifies the resulting vault notes and graph rows from the same run manifest.
