# Aily Current Status

This file is a short operational status pointer. The canonical detailed status map is `docs/CURRENT_STATE.md`.

Date: 2026-05-03

## Status

Aily has a working local FastAPI backend, React/Vite Studio, source store, persistent UI event log, provider routing for Kimi and DeepSeek, DIKIWI batch pipeline, Reactor/Entrepreneur/Guru path, Docker pre-production packaging, and real evidence from backend, browser Studio, and Docker runs.

The 2026-05-03 review blocker sprint is implemented for Studio truth-gating, retry semantics, hosted browser auth, scoped browser evidence, Studio URL fetch/extract/DIKIWI routing, Docker pre-production control proof, and Docker real-LLM DIKIWI quality proof. The next product gaps are richer media processing and a full-product browser E2E with real DIKIWI/LLM enabled.

## Recently Fixed

- Studio DIKIWI theater is truth-gated: unreached stages render locked, and Proposal/Entrepreneur visuals require real persisted artifacts.
- Studio retry reloads failed stored uploads, re-enters the processing path, and emits retry lifecycle events.
- Hosted/private browser mode supports token entry plus cookie/query bootstrap for first-page load, API calls, and websocket events.
- Studio browser E2E now writes the required evidence folder shape and labels disabled-DIKIWI runs as `ui_control`.
- Studio URL submission stores the link, performs real HTTP fetch/extraction, and routes the content into the DIKIWI processing path.

## Proof To Reuse

- Full pipeline proof: `logs/runs/2026-05-02T12-15-35Z_full_pipeline_2pdf/manifest.json`
- Studio browser proof: `logs/runs/2026-05-02T16-38-24Z_studio_agent_browser_e2e/manifest.json`
- Hosted-auth retry plus URL browser proof: `logs/runs/2026-05-02T17-12-50Z_studio_agent_browser_hosted_auth_retry_url_e2e/manifest.json`
- Docker pre-production proof: `logs/runs/2026-05-03T00-26-50Z_docker_preprod_retry_url_e2e/manifest.json`
- Docker real-LLM DIKIWI quality proof: `logs/runs/2026-05-03T08-13-27Z_docker_real_llm_dikiwi_quality_2pdf/dikiwi-quality-report.json`
- Provider smoke proof: `logs/provider_smoke_report.json`
- Project health proof: `logs/project_health_report.json`

## Gates Passed In Latest Fix Pass

- `npm --prefix frontend run build`
- `uv run python -m pytest tests/test_ui_router.py tests/test_ui_events.py tests/test_source_store.py tests/verify/test_evidence.py tests/verify/test_run_registry.py tests/test_ui_static.py -q`
- `uv run python -m pytest -q --ignore=tests/e2e --ignore=tests/integration`
- `uv run python scripts/run_studio_agent_browser_e2e.py`
- `uv run python scripts/run_studio_agent_browser_e2e.py --hosted-auth --exercise-retry`
- `uv run python scripts/run_studio_agent_browser_e2e.py --hosted-auth --exercise-retry --exercise-url`
- `uv run python scripts/run_docker_preprod_e2e.py --build --exercise-url --exercise-retry`
- Docker real-LLM DIKIWI quality run: 2 PDFs, 20 successful Kimi calls, 47 Data, 43 Information, 20 Knowledge, 3 Insight, 4 Wisdom, 5 Impact, 191 graph edges, 0 audit failures.

## Remaining Docker Work

- Add a full real-LLM browser E2E that drives Studio and waits for DIKIWI artifacts rather than invoking the backend test runner directly.
- Add a dedicated Docker MinerU/OCR proof before treating the optional MinerU profile as accepted.
- Docker is now the repeatable pre-production/distribution gate; local remains the final personal-product acceptance gate.
