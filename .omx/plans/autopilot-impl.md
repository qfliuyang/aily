# Autopilot Implementation Plan

Date: 2026-05-02

## Completed Scope

Implemented the first evidence-first development slice from `docs/AILY_DEVELOPMENT_AND_TEST_MASTER_PLAN.md`, plus the stability fixes required to make the gates trustworthy.

## Completed Steps

1. Add `aily/verify/evidence.py`.
2. Add tests under `tests/verify/`.
3. Wire `scenario_full_pipeline()` to create a run evidence folder.
4. Add a `--seed` option to `scripts/run_test_suite.py full-pipeline`.
5. Serve built Aily Studio assets from `aily/main.py`.
6. Add `LLMClient.complete()` compatibility for DIKIWI gates and skills.
7. Remove the E2E LLM mock fallback. E2E now requires a real configured provider.
8. Harden integration fixtures so external services skip explicitly when not configured.
9. Fix lingering pytest teardown by closing the `QueueDB` fixture in URL dedup tests.
10. Align `pyproject.toml` dependencies with runtime/test requirements.
11. Add `RunRegistry` and `/api/ui/runs` evidence explorer APIs.
12. Add `SourceStore` and `/api/ui/sources` durable intake APIs.
13. Add `/api/ui/sources/urls` for durable URL/link intake.
14. Show source-store and evidence-run summaries in Aily Studio Operations.
15. Add a Studio link-submission control backed by the source store.
16. Route multi-file Studio uploads through one batch path after all sources are stored and extracted.
17. Emit real `batch_stage_started` / `batch_stage_completed` DIKIWI barrier events.
18. Persist Studio UI events to disk and reload them on startup.
19. Add Studio upload size guardrails and hosted-mode single-owner token auth.
20. Add configurable provider timeout/retry settings and DIKIWI per-stage timeouts.
21. Prevent fake downstream UI events when batch stages have zero surviving contexts.
22. Suppress threshold events unless at least one Knowledge stage succeeded.
23. Compact WISDOM prompts and make WISDOM reviewer mode opt-in for offline/deeper runs.
24. Persist/output Reactor proposals from the full-pipeline scenario before Entrepreneur runs.
25. Add bounded Reactor method execution to prevent one innovation method from hanging the business path.
26. Fix the scenario vault-status reporting order so final 07/08 counts are reflected after business output.

## Verification Completed

- `timeout 180 uv run python -m pytest -q --ignore=tests/integration --ignore=tests/e2e` -> `644 passed, 8 skipped`
- `timeout 180 uv run python -m pytest tests/integration -q` -> `6 passed, 41 skipped`
- `npm --prefix frontend run build`
- `uv run python -m py_compile aily/llm/client.py aily/thinking/orchestrator.py tests/e2e/conftest.py tests/test_llm_client.py tests/test_url_dedup.py`
- `uv run python -m pytest tests/e2e/test_dikiwi_pipeline.py::TestDIKIWIPipeline::test_url_drop_to_knowledge -q`
- `uv run python scripts/run_test_suite.py full-pipeline --max 1 --log-llm --vault /tmp/aily-autopilot-vault --seed 260502 --phase-timeout 600`
- `uv run python -m pytest tests/test_source_store.py tests/test_ui_router.py tests/verify -q`
- `uv run python -m pytest tests/sessions/test_dikiwi_batch_mode.py tests/test_ui_router.py tests/test_source_store.py -q`
- `uv run python -m pytest tests/sessions/test_dikiwi_batch_mode.py tests/llm/test_provider_routes.py tests/test_ui_events.py tests/test_ui_router.py -q`
- `uv run python scripts/run_test_suite.py full-pipeline --max 2 --log-llm --vault /tmp/aily-autopilot-vault --seed 260502 --phase-timeout 900`
- `env DIKIWI_STAGE_TIMEOUT_SECONDS=150 LLM_TIMEOUT_SECONDS=120 LLM_MAX_RETRIES=0 uv run python scripts/run_test_suite.py full-pipeline --max 2 --log-llm --vault /tmp/aily-autopilot-vault --seed 260502 --phase-timeout 400` -> `logs/runs/2026-05-02T10-36-40Z_full_pipeline_2pdf/manifest.json`
- `env LLM_MAX_RETRIES=0 uv run python scripts/run_test_suite.py full-pipeline --max 2 --log-llm --vault /tmp/aily-autopilot-vault --seed 260502 --phase-timeout 1200` -> `logs/runs/2026-05-02T10-45-53Z_full_pipeline_2pdf/manifest.json`
- `env AILY_PROPOSAL_MAX_PER_SESSION=1 REACTOR_METHOD_TIMEOUT_SECONDS=180 LLM_MAX_RETRIES=0 uv run python scripts/run_test_suite.py full-pipeline --max 1 --log-llm --vault /tmp/aily-business-smoke-vault-2 --seed 260502 --phase-timeout 900 --force-business` -> `logs/runs/2026-05-02T11-49-38Z_full_pipeline_1pdf/manifest.json`
- `env AILY_PROPOSAL_MAX_PER_SESSION=1 REACTOR_METHOD_TIMEOUT_SECONDS=180 DIKIWI_STAGE_TIMEOUT_SECONDS=480 LLM_MAX_RETRIES=0 uv run python scripts/run_test_suite.py full-pipeline --max 2 --log-llm --vault /tmp/aily-final-acceptance-vault-480 --seed 260502 --phase-timeout 2400` -> `logs/runs/2026-05-02T12-15-35Z_full_pipeline_2pdf/manifest.json`
- `npm --prefix frontend run build`
- `git diff --check`

## Follow-Up

Next autopilot slice should reduce runtime/cost and add real Studio browser acceptance. The combined post-patch path now passes in `logs/runs/2026-05-02T12-15-35Z_full_pipeline_2pdf/manifest.json`, but it took about 34.7 minutes and 109,025 tokens.
