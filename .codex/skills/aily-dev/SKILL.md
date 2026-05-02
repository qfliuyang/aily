---
name: aily-dev
description: Aily-specific development workflow for DIKIWI, Studio, providers, and evidence-safe changes.
---

# Aily Dev

Use for any Aily code change.

1. Read `docs/CURRENT_STATE.md` and `docs/AILY_DEVELOPMENT_AND_TEST_MASTER_PLAN.md`.
2. Define write scope before editing.
3. Preserve unrelated dirty worktree changes.
4. If runtime behavior changes, produce or reference `logs/runs/<run_id>/manifest.json`.
5. Run the narrow tests for touched modules, then the local gate when feasible:
   `uv run python -m pytest -q --ignore=tests/integration --ignore=tests/e2e`
6. For Studio behavior, run:
   `npm --prefix frontend run build`
   `uv run python scripts/run_studio_browser_e2e.py`
7. For provider behavior, run:
   `uv run python scripts/provider_smoke.py`
8. Never claim product acceptance from mocked LLM, mocked graph, mocked vault, or fake browser events.
