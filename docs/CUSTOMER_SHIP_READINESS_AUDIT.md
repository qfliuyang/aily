# Aily Customer Ship Readiness Audit

Date: 2026-05-07

Customer-ready status: Achieved for the initial single-tenant/private customer
shipping scope, contingent on the latest clean `scripts/audit_customer_ship_readiness.py`
result remaining green.

This audit is stricter than the RC0 private second-brain evidence. RC0 evidence
can show that important real paths exist, but it does not by itself prove that
Aily is ready to ship to customers. A customer-ready claim must be backed by one
current, clean, reproducible evidence chain for the shipped path, not by a mix of
stale, dirty, backend-only, UI-only, or private-operator proofs.

## Objective Restated As Deliverables

The current long-running objective says: update Aily to a Docker deployed, web UI
featured, full-function tool with all functions ready to ship to customers.

For audit purposes this means initial single-tenant/private customer shipping:

| ID | Deliverable | Customer-ready success criterion | Current status |
| --- | --- | --- | --- |
| CSHIP-001 | Docker deployment | Clean current-HEAD Docker Compose evidence with real Docker, FastAPI, browser, persisted vault, and graph DB. | Passing via the latest `docker_preprod_real_llm_e2e` manifest. |
| CSHIP-002 | Interactive web UI | Clean current-HEAD real-browser Studio evidence against FastAPI and persisted backend state. | Passing via the latest `docker_preprod_real_llm_e2e` manifest. |
| CSHIP-003 | Full-function DIKIWI second brain | Clean current-HEAD provider-verified DATA→IMPACT run with real provider calls, vault notes, graph rows, and provider receipts. | Passing via the latest `docker_preprod_real_llm_e2e` manifest. |
| CSHIP-004 | No split-brain customer proof | One clean current-HEAD customer scenario combines Docker + real browser + provider-verified real LLM + real DIKIWI outputs. | Passing via the latest `docker_preprod_real_llm_e2e` manifest. |
| CSHIP-005 | Traceable customer-readiness contract | Durable audit maps requirements to evidence and blockers before any customer-ready claim. | This document plus `scripts/audit_customer_ship_readiness.py`. |
| CSHIP-006 | Customer shipping runbook | Customer operator docs define deployment scope, env, acceptance gate, ops, security boundaries, and known limits. | `docs/CUSTOMER_SHIPPING_RUNBOOK.md`. |

## Prompt-To-Artifact Checklist

| Requirement from prompt | Evidence inspected | Coverage verdict |
| --- | --- | --- |
| Docker deployed | `Dockerfile`, `docker-compose.yml`, `docker-compose.preprod.yml`, `docs/DOCKER_PREPROD.md`, `docs/CUSTOMER_SHIPPING_RUNBOOK.md`, and the latest clean `docker_preprod_real_llm_e2e` manifest selected by `scripts/audit_customer_ship_readiness.py`. | Covered for single-tenant/private Docker Compose shipping. |
| Web UI featured | `frontend/src/App.tsx`, `aily/ui/router.py`, `docs/RC0_QUICKSTART.md`, and the latest clean real-browser Docker customer manifest. | Covered for browser upload/control/status against real FastAPI and persisted backend state. |
| Full-function tool | Latest clean Docker customer manifest with `real_llm=true`, `provider_verified_dikiwi=true`, non-zero `01-Data` through `06-Impact`, real vault, real graph DB, and provider receipts. | Covered for one browser-submitted document through DATA→IMPACT in the shipped Docker path. |
| Ready to ship to customers | `docs/CUSTOMER_SHIPPING_RUNBOOK.md`, `scripts/audit_customer_ship_readiness.py`, Docker customer manifest, and targeted contract tests. | Covered for the explicitly scoped initial single-tenant/private customer release; not a multi-tenant SaaS certification. |
| Anti-mock / anti-cheat | `docs/AILY_RC0_GOAL_CONTRACT.md`, `tests/verify/test_no_mock_acceptance.py`, `scripts/run_rc0_provider_dikiwi_gate.py`, `scripts/audit_customer_ship_readiness.py`, and `--require-real-llm` Docker evidence. | Customer readiness fails closed unless evidence is current, clean, real-boundary, combined, and provider-verified. |

## Remaining non-blocking limits

These are outside the initial customer-ready scope and should become future
goals, not hidden blockers:

1. Multi-tenant SaaS account isolation and billing are not implemented.
2. The combined real-LLM customer gate covers one browser-submitted document;
   larger corpus soak and media-rich ingestion remain future hardening.
3. Public internet exposure should use a customer-controlled HTTPS reverse proxy.
4. Provider runs remain slow and budget-consuming; timeout/429/partial-stage
   failures must stay visible and must not be converted into success.

## Next verification checkpoint

Run before any customer shipping claim:

```bash
python3 scripts/run_docker_preprod_e2e.py --build --require-real-llm
python3 scripts/audit_customer_ship_readiness.py --output logs/customer-ship-readiness.json
```

The audit must exit `0` on current clean `HEAD`. If it exits non-zero, Aily is
not customer-ready for this scope.
