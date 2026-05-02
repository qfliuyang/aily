---
name: aily-e2e
description: Real-path Aily evidence workflow for full DIKIWI, provider, Studio, and hosted-mode tests.
---

# Aily E2E

Use when certifying Aily product behavior.

Required pattern:

1. Start from real files or a real running FastAPI app.
2. Save command, environment, source manifest, UI events, LLM calls if used, graph/vault snapshots, failures, and samples.
3. Reject evidence with `mocked=true` for product acceptance.
4. For DIKIWI/business:
   `uv run python scripts/run_test_suite.py full-pipeline --max <n> --log-llm --vault <temp-vault>`
5. For Studio:
   `npm --prefix frontend run build`
   `uv run python scripts/run_studio_browser_e2e.py`
6. For hosted safety:
   run security/router tests and backup/restore dry run.
7. For provider quality:
   use identical source manifests across providers and save LLM traces before ranking.
