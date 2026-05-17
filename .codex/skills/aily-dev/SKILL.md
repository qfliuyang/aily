---
name: aily-dev
description: Aily-specific development workflow for DIKIWI, Studio, providers, and evidence-safe changes.
---

# Aily Dev

Use for any Aily code change.

1. Read `docs/CURRENT_STATE.md` and `docs/AILY_V1_UPGRADE_PLAN.md`.
2. Define write scope before editing.
3. Preserve unrelated dirty worktree changes.
4. If runtime behavior changes, produce or reference `logs/runs/<run_id>/manifest.json`.
5. Legacy test infrastructure has been removed for the Aily V1 redesign; use import/build checks and real-path evidence until the V1 test harness exists.
6. For Studio behavior, run:
   `npm --prefix frontend run build`
7. Never claim product acceptance from mocked LLM, mocked graph, mocked vault, or fake browser events.
