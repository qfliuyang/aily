# Aily Current State

This file is the shortest trustworthy map of the codebase as it exists now.

## Active Runtime

- App bootstrap: `aily/main.py`
- Private local Studio entrypoint: `aily/main.py` serves `frontend/dist` when the frontend has been built
- Continuous pipeline entrypoint: `aily/sessions/dikiwi_mind.py`
- DIKIWI runtime coordination: `aily/dikiwi/orchestrator.py`
- DIKIWI graph-trigger selector: `aily/dikiwi/network_synthesis.py`
- Post-pipeline proposal synthesis: `aily/dikiwi/agents/residual_agent.py`
- Innovation scheduler: `aily/sessions/reactor_scheduler.py`
- Business evaluation scheduler: `aily/sessions/entrepreneur_scheduler.py`
- GStack and Guru planning: `aily/sessions/gstack_agent.py`
- Chaos ingestion bridge: `aily/chaos/dikiwi_bridge.py`
- Chaos daemon entrypoint: `scripts/run_chaos_daemon.py`
- Real-run evidence harness: `aily/verify/evidence.py`
- Evidence run registry/API: `aily/verify/run_registry.py`
- Durable source store: `aily/source_store/store.py`
- Persistent Studio event log: `aily/ui/events.py` writes and reloads `SETTINGS.ui_event_log_path`
- Persistent Studio event query: `/api/ui/events/query` filters durable UI events by `run_id`, `pipeline_id`, `upload_id`, and event type for replay/debug
- Provider route and timeout control: `aily/llm/provider_routes.py`, `aily/llm/llm_router.py`
- Provider capability matrix: `aily/llm/provider_capabilities.py` for active providers Kimi and DeepSeek
- Hosted-mode guardrails: `aily/security/`
- Project health harness: `scripts/verify_project_health.py`

## Active Flow

1. Input enters through Feishu WebSocket, the chaos bridge, queue-driven jobs, Aily Studio uploads, or Aily Studio URL submission.
2. Studio uploads and URLs are hashed and persisted into the source store before extraction or downstream work; duplicate file content or duplicate URLs map to the same `source_id`.
3. Single-file Studio uploads still run one pipeline directly after source-store persistence.
4. Multi-file Studio uploads are grouped into one backend batch: all sources are stored, all extract into Chaos content, then `DikiwiMind.process_inputs_batched()` advances the batch stage-by-stage.
5. For batch chaos ingestion, `00-Chaos` is written first and then the whole batch advances stage-by-stage through `01-Data`, `02-Information`, and `03-Knowledge`.
6. After at least one successful batch `KNOWLEDGE` result, Aily measures incremental graph growth. If new information nodes add less than `5%` to the existing information graph, the batch stops after `KNOWLEDGE`.
7. If the batch crosses the incremental threshold and a context has a synthesis-grade changed neighborhood, that context continues through `INSIGHT -> WISDOM -> IMPACT`.
8. If every source fails before `KNOWLEDGE`, no graph-threshold event is emitted. If a higher-order stage has zero surviving contexts, no empty downstream stage event is emitted.
9. After IMPACT, `ReactorScheduler` generates proposal candidates from multiple frameworks.
10. `ResidualAgent` synthesizes vault, graph, and reactor context into structured `residual_proposal` nodes.
11. Reactor screens those residual proposals for innovation quality and promotes passing proposals to `pending_business`.
12. `EntrepreneurScheduler` runs GStack business review on pending proposals.
13. `Guru` writes an appendix for every reviewed proposal, including denied ones.
14. Notes are written into the numbered Obsidian vault layout.

## Active Vault Layout

- `00-Chaos`
- `01-Data`
- `02-Information`
- `03-Knowledge`
- `04-Insight`
- `05-Wisdom`
- `06-Impact`
- `07-Proposal`
- `08-Entrepreneurship`

## Reference Docs

- `README.md` - repo entrypoint and current workflow overview
- `docs/ARCHITECTURE_AND_VISION.md` - high-level system map
- `docs/DIKIWI_ARCHITECTURE.md` - current DIKIWI runtime and post-pipeline flow
- `docs/AILY_CHAOS_ARCHITECTURE.md` - current chaos ingestion and bridge path
- `docs/AILY_DEVELOPMENT_AND_TEST_MASTER_PLAN.md` - traceable development and anti-mock test roadmap to the private second-brain website
- `docs/AI_INNOVATION_METHODOLOGIES.md` - framework reference
- `docs/prompt-improvement-spec.md` - prompt design direction and prompt-layer changes

## Experimental Or Quarantined

- `aily/dikiwi/skills/` is shipped in-tree but is not part of the active production path.
- `aily/dikiwi/memorials/` is shipped in-tree but is not wired into the active runtime.
- `aily/gating/` remains as older/secondary infrastructure and fallback material, not the primary DIKIWI path.

## Known Hybrid Areas

- The Feishu WebSocket path routes directly into `DikiwiMind`.
- The chaos batch path now uses `DikiwiMind.process_inputs_batched()` through `aily/chaos/dikiwi_bridge.py` and `aily/chaos/mineru_batch.py`.
- Some older queue-based jobs still exist in `aily/main.py` for URL fetch, digest, voice, file, and session processing.
- The passive capture scheduler exists, but its browser tab detection remains incomplete and should not be treated as the core ingestion path.
- Full-pipeline test runs can now emit durable evidence folders under `logs/runs/` through `scripts/run_test_suite.py full-pipeline --seed ...`.
- Aily Studio Operations can list persisted source records and evidence run manifests through `/api/ui/sources` and `/api/ui/runs`; links can be submitted through `/api/ui/sources/urls`.
- Aily Studio Judgment Room reads real proposal and entrepreneurship notes through `/api/ui/proposals` and `/api/ui/entrepreneurship`.
- Aily Studio controls can cancel active uploads and mark failed sources for retry through `/api/ui/control`.
- DIKIWI batch runs emit explicit `batch_stage_started` and `batch_stage_completed` barrier events.
- Aily Studio HTTP APIs and websocket can be protected with `UI_AUTH_ENABLED=true` and `UI_AUTH_TOKEN=...`; auth is disabled by default for local development.
- Studio uploads have file-count and size checks at the router boundary; backend processing also enforces configured max file size.
- Provider timeout and retry behavior is configurable through `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, and workload-specific `llm_workload_routes_json` fields `timeout` and `max_retries`.
- Provider switching is documented and queryable through `PrimaryLLMRoute.describe_routes()` and `docs/PROVIDER_ROUTING_MATRIX.md`; active providers are Kimi and DeepSeek only.
- Hosted mode can require token auth for Studio APIs/static frontend, rate-limit upload/control/link actions, write an audit JSONL log, and create backup/restore dry-run artifacts.
- Autopilot development now has a task template, testing contract, local health script, prompt-regression artifacts, and Aily-specific local skills under `.codex/skills/`.
- DIKIWI batch stages have `DIKIWI_STAGE_TIMEOUT_SECONDS`; a timed-out stage records `stage_failed` and the batch continues to a manifest instead of hanging until the outer test phase times out.

## Latest Real Evidence

- `logs/runs/2026-05-02T10-17-46Z_full_pipeline_2pdf/manifest.json`
  - Real files, real vault, real graph, real Kimi calls, `mocked=false`.
  - Proved stage-latched batch events through DATA, INFORMATION, KNOWLEDGE, INSIGHT, and WISDOM.
  - Proved threshold crossing from graph growth: `incremental_ratio=1.0`, `incremental_threshold=0.05`.
  - Exposed a remaining bottleneck: both sources timed out in WISDOM after 240 seconds, so no IMPACT, 07-Proposal, or 08-Entrepreneurship output was generated.
- `logs/runs/2026-05-02T10-45-53Z_full_pipeline_2pdf/manifest.json`
  - Real two-PDF run after WISDOM compaction.
  - Proved both documents can reach IMPACT with real provider calls.
  - Exposed a Reactor handoff bug that was later patched: Reactor returned 10 proposals but the lightweight scenario path did not persist/write 07-Proposal before Entrepreneur.
- `logs/runs/2026-05-02T10-36-40Z_full_pipeline_2pdf/manifest.json`
  - Real low-timeout batch proving stage failure is recorded as evidence instead of a process hang.
  - One source failed at DATA while the surviving source advanced through KNOWLEDGE; downstream batch events only referenced the surviving source.
  - No empty INSIGHT/WISDOM/IMPACT stage event was emitted after there were no synthesis-qualified higher-order contexts.
- `logs/runs/2026-05-02T11-49-38Z_full_pipeline_1pdf/manifest.json`
  - Real one-PDF business smoke with `AILY_PROPOSAL_MAX_PER_SESSION=1`.
  - Proved 07-Proposal notes are written and GraphDB gets `reactor_proposal` nodes.
  - Proved 08-Entrepreneurship writes a denied proposal note with a long Guru appendix.
  - Exposed an evidence-reporting bug that was patched: scenario `result.vault_status` was captured before business output even though manifest `vault_counts_after` was correct.
- `logs/runs/2026-05-02T12-15-35Z_full_pipeline_2pdf/manifest.json`
  - Final combined real acceptance pass with two PDFs, real Kimi calls, real vault, real GraphDB, `mocked=false`.
  - Proved both documents reached IMPACT.
  - Proved Reactor wrote one real 07-Proposal note with bounded method execution.
  - Proved Entrepreneur wrote 08-Entrepreneurship output for the proposal, including a denied proposal note with a Guru appendix.
  - Final vault counts: `04-Insight=6`, `05-Wisdom=6`, `06-Impact=5`, `07-Proposal=1`, `08-Entrepreneurship=2`.
- `logs/runs/2026-05-02T13-50-50Z_studio_browser_e2e/manifest.json`
  - Real browser and real FastAPI Studio run.
  - Proved the built frontend loads through FastAPI static serving.
  - Proved a real file upload through the Studio file input reaches the backend source store.
  - Proved the Studio WebSocket path works after the auth dependency fix.
  - Proved persisted UI events are queryable after backend restart.
- `logs/runs/2026-05-02T15-47-31Z_studio_agent_browser_e2e/manifest.json`
  - Real `agent-browser` session against a running FastAPI backend.
  - Saved full-page screenshots at a 1920x1400 CSS viewport with 2x device scale: home, after upload, Operations view, and post-control click.
  - The after-upload snapshot captures the redesigned Gapingvoid-inspired DIKIWI theater glyphs for Chaos, Data, Information, Knowledge, Insight, Wisdom, Impact, Proposal, and Entrepreneurship.
  - Proved a human-style file input upload writes persisted `source_uploaded`, `source_stored`, `chaos_note_created`, and `source_ingest_completed` events.
  - Proved the visible Operations controls can be clicked and persisted as `retry_failed_sources_requested`.
- `logs/provider_smoke_report.json`
  - Real provider smoke report with no mocked providers.
  - Kimi passed on `kimi-k2.6`.
  - DeepSeek passed on `deepseek-v4-pro`.
  - Active provider set is now Kimi and DeepSeek only.
- `logs/project_health_report.json`
  - Real repository health scan covering skipped tests, stale doc links, dead-code candidates, syntax errors, and generated artifacts.

## Current Gaps

- The full Impact-to-07/08 path is now proven in one fresh real run, but it remains slow and expensive: the final two-PDF acceptance pass took about 34.7 minutes and 109,025 tokens.
- The latest low-timeout real run was intentionally configured to fail early; it is evidence for failure handling, not evidence of DIKIWI quality.
- Phase 0 through Phase 9 now have implementation and test evidence. Zhipu is intentionally quarantined; active provider work continues with Kimi and DeepSeek.
