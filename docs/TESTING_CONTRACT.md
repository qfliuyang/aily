# Aily Testing Contract

## Non-Negotiable Rule

Mocks can test local mechanics, but they cannot certify product behavior. A product claim requires a real-path artifact: real files, real vault writes, real GraphDB/source-store writes, real provider calls when LLM behavior is claimed, and real browser execution when Studio behavior is claimed.

## Required Evidence

Runtime tasks must write or reference an evidence folder under `logs/runs/` with command, environment, UI events, LLM calls when applicable, vault counts, graph snapshots, source manifest, failures, and samples.

## Test Gates

- Local gate: `uv run python -m pytest -q --ignore=tests/integration --ignore=tests/e2e`
- Integration gate: `uv run python -m pytest tests/integration -q`
- Frontend gate: `npm --prefix frontend run build`
- Studio browser gate: `uv run python scripts/run_studio_browser_e2e.py`
- Provider smoke gate: `uv run python scripts/provider_smoke.py`
- Health gate: `uv run python scripts/verify_project_health.py`

## Acceptance Language

Use precise wording:

- `unit verified`: local function behavior only.
- `contract verified`: API/schema/router behavior.
- `real e2e verified`: real files/vault/graph/backend path.
- `provider verified`: real provider API call with saved output.
- `browser verified`: real browser against running FastAPI.

Do not say “done” for product behavior if the evidence is only unit or mocked.
