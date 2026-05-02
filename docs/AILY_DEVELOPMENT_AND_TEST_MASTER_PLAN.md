# Aily Development And Test Master Plan

Date: 2026-05-02

## Purpose

This document is the execution plan for turning Aily from the current local-first knowledge pipeline into a private second-brain website.

Ultimate goal:

- I can open a private Aily website.
- I can drag or send files, links, images, audio, video, and other media into it.
- Aily stores raw inputs, converts them into structured knowledge, grows the DIKIWI graph, generates proposals, and writes entrepreneur/guru plans.
- I can open Aily Studio and see the actual system working: intake, extraction, DIKIWI stages, graph growth, LLM calls, proposals, decisions, failures, retries, and evidence.
- Future autopilot-style agents can safely improve the project because every task has traceable scope, test gates, and proof artifacts.

This is not a UI-only plan. It is a product, architecture, development, and verification plan.

## Current Status Snapshot

The repo already has the core shape of the final system.

Active backend:

- FastAPI app and lifecycle: `aily/main.py`
- UI control-plane router: `aily/ui/router.py`
- in-memory UI event stream: `aily/ui/events.py`
- DIKIWI runtime: `aily/sessions/dikiwi_mind.py`
- stage-latched batch DIKIWI: `DikiwiMind.process_inputs_batched()`
- MinerU batch ingestion: `aily/chaos/mineru_batch.py`
- graph storage: `aily/graph/db.py`
- provider routing: `aily/llm/provider_routes.py`
- Reactor, Entrepreneur, Guru: `aily/sessions/reactor_scheduler.py`, `aily/sessions/entrepreneur_scheduler.py`, `aily/sessions/gstack_agent.py`

Active frontend:

- React/Vite Aily Studio prototype: `frontend/src/App.tsx`
- visual styling: `frontend/src/styles.css`
- current surfaces: Thinking Theater, Brain Graph, Judgment Room, Operations

Active test structure:

- subsystem tests under `tests/`
- unified ad hoc scenario runner: `scripts/run_test_suite.py`
- scenario framework: `scripts/test_framework.py`
- batch runner: `scripts/run_mineru_chaos_batch.py`

Important current capabilities:

- browser upload endpoint exists at `POST /api/ui/uploads`
- studio status endpoint exists at `GET /api/ui/status`
- graph endpoint exists at `GET /api/ui/graph`
- pipeline trace endpoint exists at `GET /api/ui/pipelines/{pipeline_id}`
- websocket event stream exists at `WS /api/ui/events`
- DIKIWI batch mode already uses a stage barrier: Chaos first, then Data, then Information, then Knowledge, then higher-order stages only when graph change crosses threshold
- 00-Chaos notes can embed MinerU visual assets under `00-Chaos/_assets`
- provider routing can choose Kimi or DeepSeek by workload
- FastAPI can serve the built Aily Studio frontend for local private use
- Studio source records and evidence run manifests are available through backend APIs
- Studio events can persist to disk and reload on restart
- Studio HTTP APIs and websocket can be protected with a single-owner token
- provider timeout/retry settings and DIKIWI stage timeouts are configurable

Main gaps after Phase 0-6 completion work:

- Multi-file Studio upload has a batch path, but the durable queue-backed ingestion job model is not finished.
- Traceability across raw source, vault note, graph node, LLM call, proposal, review, and UI event is incomplete.
- A fresh real two-PDF acceptance run now proves IMPACT, 07-Proposal, and 08-Entrepreneurship in one manifest, but the path is still slow and expensive enough to need performance hardening.
- Link intake is durable, but media and website-specific intake are not productized as first-class Studio actions.
- Hosted/private deployment needs auth, storage isolation, secret handling, and operational guardrails.

Phase 0-9 completion evidence:

- Backend full-pipeline acceptance: `logs/runs/2026-05-02T12-15-35Z_full_pipeline_2pdf/manifest.json`
- Studio browser acceptance: `logs/runs/2026-05-02T13-50-50Z_studio_browser_e2e/manifest.json`
- Provider smoke evidence: `logs/provider_smoke_report.json`
- Project health evidence: `logs/project_health_report.json`
- Prompt-regression artifacts: `test-artifacts/prompt-regression/`
- Unit/regression gates: `665 passed, 4 skipped` outside integration/e2e; `6 passed, 41 skipped` integration.
- Frontend gate: `npm --prefix frontend run build`.

Provider status:

- Kimi and DeepSeek passed real smoke tests.
- Zhipu is quarantined and removed from active routing because the service is currently unreliable.

## Non-Negotiable Development Rules

### 1. No Mock Acceptance

A task is not accepted as product behavior unless it has at least one real-path verification artifact.

Unit tests may isolate tiny functions, but they are never acceptance proof. Any test used to claim Aily works must use the real configured path: real source files, real vault writes, real graph/database writes, real provider calls, real backend events, and real browser/UI execution when UI behavior is being certified.

Forbidden as acceptance proof:

- fake LLM responses proving DIKIWI quality, proposal quality, or provider behavior
- fake graph events proving graph animation or graph synthesis
- fake file paths proving vault output
- fake images proving MinerU asset copy
- fake pipeline events proving Thinking Theater
- mocked Obsidian notes proving DIKIWI stage output
- mocked upload, queue, provider, or router behavior proving end-to-end ingestion

Acceptance proof must use real files or real service calls unless the task is explicitly labeled `offline unit only`, and that label means it does not certify product behavior.

### 2. Every Real Run Must Produce Evidence

Every manual, e2e, benchmark, or pressure run must write an evidence folder.

Required evidence folder shape:

```text
logs/runs/<run_id>/
  manifest.json
  command.txt
  environment.json
  stdout.log
  stderr.log
  ui-events.jsonl
  llm-calls.jsonl
  graph-before.json
  graph-after.json
  vault-counts-before.json
  vault-counts-after.json
  source-manifest.json
  failures.json
  samples/
    chaos/
    data/
    information/
    knowledge/
    insight/
    wisdom/
    impact/
    proposal/
    entrepreneurship/
```

Minimum `manifest.json` fields:

```json
{
  "run_id": "2026-05-02T10-30-00Z_pressure_40pdf",
  "git_sha": "...",
  "dirty_worktree": true,
  "scenario": "full_pipeline",
  "source_count": 40,
  "source_selector": "seeded_random",
  "source_seed": 260502,
  "vault_path": "/absolute/path",
  "graph_db_path": "/absolute/path",
  "provider_routes": {},
  "started_at": "...",
  "completed_at": "...",
  "exit_code": 0,
  "acceptance": {
    "mocked": false,
    "real_files": true,
    "real_graph_db": true,
    "real_vault": true,
    "real_llm": true
  }
}
```

### 3. Trace IDs Must Survive The Whole System

Each input needs durable IDs that can be followed from intake to final business plan.

Required IDs:

- `source_id`: stable raw input identity, preferably content hash plus normalized source metadata
- `upload_id`: browser/API upload request identity
- `run_id`: scenario or batch execution identity
- `pipeline_id`: DIKIWI pipeline identity
- `stage_id`: one DIKIWI stage attempt identity
- `node_id`: GraphDB node identity
- `edge_id`: GraphDB edge identity
- `note_path`: Obsidian vault output path
- `proposal_id`: proposal node/note identity
- `review_id`: GStack/Entrepreneur review identity
- `guru_appendix_id`: Guru appendix section identity

Every emitted event, graph node, stage result, and generated note should carry enough of these IDs to reconstruct lineage.

### 4. The Frontend Must Animate Reality

Aily Studio must not use decorative fake progress once a backend path exists.

Allowed:

- replay fixtures clearly labeled as `demo`
- loading skeletons before data arrives
- deterministic frontend unit fixtures

Forbidden:

- showing `INSIGHT`, `WISDOM`, `IMPACT`, `PROPOSAL`, or `ENTREPRENEUR` animation unless backend emitted the corresponding event or persisted artifact
- showing graph sparks unless the backend emitted `threshold_crossed`
- showing proposal cards unless a proposal note or graph node exists
- showing completed pipeline status unless backend emitted `pipeline_completed` or persistent run state says completed

### 5. Development Must Stay Incremental

Each autopilot task must have:

- single concrete outcome
- explicit write scope
- tests to run before and after
- evidence path if it touches runtime behavior
- rollback note
- updated docs when behavior changes

No task should modify unrelated pipeline semantics, prompts, frontend design, and provider routing in one pass.

## Target Architecture

```text
Private Aily Website
  -> Intake Inbox
      -> file upload
      -> URL/link capture
      -> media upload
      -> future mobile/share extension
  -> Raw Source Store
      -> source manifest
      -> original object or pointer
      -> extracted sidecars
  -> Extraction Layer
      -> MinerU for documents/PDFs/images where useful
      -> URL fetch/markdownize
      -> audio transcription
      -> video/image processors
  -> 00-Chaos
      -> one source transcript/audit note
      -> image embeds/assets
      -> metadata and source identity
  -> DIKIWI Pipeline
      -> 01-Data
      -> 02-Information
      -> 03-Knowledge
      -> 04-Insight
      -> 05-Wisdom
      -> 06-Impact
  -> Reactor / Residual
      -> 07-Proposal
  -> Entrepreneur / GStack / Guru
      -> 08-Entrepreneurship
  -> GraphDB
      -> nodes, edges, properties, lineage, scores
  -> Aily Studio
      -> live event stream
      -> durable run replay
      -> graph view
      -> LLM telemetry
      -> evidence explorer
```

Storage layers:

- raw source store: immutable or append-only source objects
- vault: human-readable Obsidian markdown
- GraphDB: queryable network and lineage
- run evidence store: test/proof artifacts
- queue database: operational work state

## Development Roadmap

### Phase 0: Control-Plane Stabilization

Goal:

Make the current backend/frontend safe enough for daily local use and future autopilot edits.

Deliverables:

- bounded browser upload memory and concurrency
- upload count and active-upload limits
- reconnect-safe websocket client
- API error banners in frontend
- bounded pipeline/upload event traces
- local build/test commands documented

Relevant files:

- `aily/config.py`
- `aily/main.py`
- `aily/ui/router.py`
- `aily/ui/events.py`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `tests/test_ui_router.py`
- `tests/test_ui_events.py`

Acceptance tests:

- `python3 -m pytest tests/test_ui_events.py tests/test_ui_router.py -q`
- `python3 -m py_compile aily/main.py aily/ui/router.py aily/ui/events.py aily/config.py`
- `npm --prefix frontend run build`

Anti-fake proof:

- upload-limit tests must hit the real FastAPI router
- event trace tests must inspect real `UIEventHub` state
- frontend build must compile the actual `frontend/src/App.tsx`

Exit criteria:

- Studio upload cannot exhaust memory through many large files.
- Failed backend requests are visible to the user.
- Websocket reconnect does not erase selected pipeline state.

### Phase 1: Durable Run Evidence Harness

Goal:

Create the evidence layer that makes future e2e and pressure tests auditable.

Deliverables:

- `run_id` generator shared by scenario runners
- evidence folder writer
- graph/vault count snapshots
- stdout/stderr command capture for scenario runs
- source selection manifest for random pressure tests
- LLM call trace export
- UI event stream export
- final machine-readable acceptance summary

Recommended files:

- add `aily/verify/evidence.py`
- update `scripts/test_framework.py`
- update `scripts/run_test_suite.py`
- add `tests/verify/test_evidence.py`

Acceptance tests:

- unit test evidence manifest serialization with temp paths
- run `python3 scripts/run_test_suite.py full-pipeline --max 1 --log-llm --vault <temp-vault>`
- assert evidence folder contains manifest, command, graph snapshots, vault counts, and samples

Anti-fake proof:

- manifest must include `mocked=false` only when no fake LLM/client/processor class was used
- source files must exist and have recorded size/hash
- vault sample files must be copied from actual generated vault paths
- graph snapshots must be read from an initialized SQLite GraphDB

Exit criteria:

- no future pressure-test claim is accepted without a `logs/runs/<run_id>/manifest.json`

### Phase 2: Inbox And Raw Source Store

Goal:

Turn drag/drop into a durable intake system rather than fire-and-forget upload tasks.

Deliverables:

- persisted raw source records
- raw file storage or pointer storage
- idempotent source hashing
- duplicate detection
- upload lifecycle state: accepted, stored, extracting, extracted, queued, processing, completed, failed
- endpoint for links/URLs
- endpoint for media metadata
- source detail API for Studio

Recommended files:

- add `aily/source_store/`
- update `aily/main.py`
- update `aily/ui/router.py`
- update `aily/queue/db.py` if queue-backed source jobs are needed
- update `frontend/src/App.tsx`

Acceptance tests:

- upload same file twice and prove only one source identity is created unless explicit reprocess is requested
- upload invalid/oversized file and prove no partial source is promoted
- submit URL and prove source record contains normalized URL and fetch state
- restart backend and prove source status survives

Anti-fake proof:

- tests must inspect SQLite/source-store rows
- tests must verify raw stored file hash equals input file hash
- Studio must read source state from backend, not from optimistic frontend memory

Exit criteria:

- Aily can survive process restart after accepting a file.
- Every input has a stable source record before extraction begins.

### Phase 3: Batch-First DIKIWI Runtime Unification

Goal:

Make web upload, folder batch, daemon ingestion, and pressure tests use the same stage-latched DIKIWI semantics.

Current issue:

- `MinerUChaosBatchRunner` already has a strong batch path.
- Browser upload currently feeds a single extracted item through `DikiwiMind.process_input()`.
- The final product needs both: immediate single-source runs and true batch barrier runs when many inputs arrive.

Deliverables:

- unified ingestion job model: `single`, `batch`, `incremental`
- batch scheduler that groups newly ready 00-Chaos sources
- explicit stage barrier events: `batch_stage_started`, `batch_stage_completed`
- affected-node incremental runs when graph delta crosses threshold
- consistent post-impact handoff to Reactor/Residual/Entrepreneur/Guru
- no file-based higher-order generation unless a graph substructure justified it

Recommended files:

- `aily/sessions/dikiwi_mind.py`
- `aily/chaos/dikiwi_bridge.py`
- `aily/chaos/mineru_batch.py`
- `aily/dikiwi/network_synthesis.py`
- `aily/dikiwi/incremental_orchestrator.py`
- `aily/main.py`

Acceptance tests:

- batch of 10 PDFs: all successful files produce 00-Chaos before any 01-Data generation begins
- after Data, all surviving files complete 01-Data before any 02-Information generation begins
- Knowledge and higher stages must prove they used graph neighborhoods, not raw source filename
- adding a small batch below threshold stops at Knowledge
- adding a batch above threshold emits `threshold_crossed` and runs affected higher-order stages

Anti-fake proof:

- evidence must include timestamps for stage barrier events
- graph-before and graph-after counts must show information-node delta
- samples must include actual vault notes from each stage
- higher-order samples must list source graph nodes and edges used

Exit criteria:

- pressure tests can prove DIKIWI is a pipeline over the corpus graph, not a per-PDF ladder.

### Phase 4: DIKIWI Quality Hardening

Goal:

Improve semantic quality so Data, Information, Knowledge, Insight, Wisdom, and Impact are useful rather than noisy.

Deliverables:

- Data quality guard that rejects gibberish datapoints
- Data datapoints preserve image/figure/table references from 00-Chaos where relevant
- Information clusters datapoints instead of regenerating from raw source
- Knowledge uses meaningful graph subgraphs
- Insight uses short paths across information nodes
- Wisdom uses longer paths connecting distant domains
- Impact uses central/high-potential nodes with innovation pressure
- graph nodes avoid meaningless relation/token nodes such as generic `part_of`, `example_of`, or `eda` center spam

Recommended files:

- `aily/dikiwi/agents/data_agent.py`
- `aily/dikiwi/agents/information_agent.py`
- `aily/dikiwi/agents/knowledge_agent.py`
- `aily/dikiwi/agents/insight_agent.py`
- `aily/dikiwi/agents/wisdom_agent.py`
- `aily/dikiwi/agents/impact_agent.py`
- `aily/dikiwi/network_synthesis.py`
- `aily/writer/dikiwi_obsidian.py`
- `tests/sessions/test_dikiwi_data_information.py`
- `tests/dikiwi/test_graph_synthesis_agents.py`

Acceptance tests:

- Data notes include evidence snippets and asset embeds when source contains visual assets
- Information notes cite data point IDs and do not cite raw PDF filename as main semantic source
- Knowledge notes include graph neighborhood metadata
- Insight/Wisdom/Impact notes include path/subgraph metadata
- graph node labels are meaningful concepts, not relation labels or generic tags
- generated title and note body must not truncate content in a misleading way

Anti-fake proof:

- tests must parse actual generated markdown and GraphDB properties
- at least one real MinerU PDF with images must prove image carry-through
- graph-node quality check must run on actual graph snapshot, not a hardcoded fixture

Exit criteria:

- DIKIWI outputs are defensible as graph-derived knowledge, not document summaries.

### Phase 5: Proposal, Entrepreneur, And Guru Traceability

Goal:

Make 07-Proposal and 08-Entrepreneurship complete, count-consistent, and evidence-linked.

Deliverables:

- all Reactor methods run for innovation generation
- TRIZ remains part of Reactor
- Entrepreneur evaluates every eligible proposal or records why it skipped one
- Guru appends detailed plans to the same entrepreneurship note, not detached orphan files
- accepted and denied proposals both get Guru appendices
- proposal lineage links back to Impact/Wisdom/Insight/Knowledge evidence
- entrepreneurship notes link to exact proposal IDs
- counts reconcile across graph, vault, and run manifest

Recommended files:

- `aily/sessions/reactor_scheduler.py`
- `aily/dikiwi/agents/residual_agent.py`
- `aily/sessions/entrepreneur_scheduler.py`
- `aily/sessions/gstack_agent.py`
- `aily/writer/dikiwi_obsidian.py`
- `tests/sessions/test_reactor_scheduler.py`
- `tests/sessions/test_entrepreneur_scheduler.py`
- `tests/dikiwi/test_residual_agent.py`

Acceptance tests:

- clear 07/08, rerun proposal/business pass, verify proposal count equals graph proposal count within documented filters
- every evaluated proposal has one entrepreneurship section
- every entrepreneurship section contains GStack verdict and Guru appendix
- denied proposal still has a Guru plan
- each proposal contains evidence links to upstream DIKIWI artifacts

Anti-fake proof:

- tests must count actual files under `07-Proposal` and `08-Entrepreneurship`
- tests must query GraphDB proposal/review nodes
- evidence manifest must include proposal/review reconciliation table

Exit criteria:

- there are no unexplained missing entrepreneur reviews.

### Phase 6: Aily Studio Productization

Goal:

Make Aily Studio the main way to use and observe Aily.

Deliverables:

- FastAPI serves built frontend for local private site
- drag/drop source inbox
- link submission box
- live pipeline timeline
- graph view with stage/source/run filters
- LLM call console
- persistent run replay
- failure/retry/cancel controls
- evidence explorer
- proposal and entrepreneur views
- clear distinction between live, replay, and demo modes

Recommended files:

- `aily/main.py`
- `aily/ui/router.py`
- `aily/ui/events.py`
- add `aily/ui/persistence.py`
- `frontend/src/App.tsx`
- add frontend components after splitting App

Acceptance tests:

- `npm --prefix frontend run build`
- backend serves frontend `index.html`
- Playwright/browser test uploads a real small file through the UI
- websocket receives real backend events
- graph panel reflects GraphDB snapshot after pipeline completion
- replay mode loads persisted events after backend restart

Anti-fake proof:

- browser test must use actual running FastAPI app
- visual stage progress must be driven by backend events
- graph data must come from `GET /api/ui/graph`
- proposal cards must come from vault/GraphDB data

Exit criteria:

- user can operate Aily through the website without watching terminal logs.

### Phase 7: Provider Evaluation And Routing Hardening

Goal:

Make provider choice explicit, measurable, and safe.

Deliverables:

- documented workload route matrix
- Kimi/DeepSeek smoke tests
- provider capability registry for text, vision, JSON reliability, context, cost, latency
- innovation-quality benchmark scenario
- provider comparison reports generated from identical source manifests
- per-provider failure and retry metrics

Recommended files:

- `aily/llm/provider_routes.py`
- `aily/llm/client.py`
- `scripts/benchmark_providers.py`
- `scripts/benchmark_run.py`
- `docs/PROVIDER_OUTPUT_EVALUATION_2026-04-26.md`
- `tests/llm/test_provider_routes.py`

Acceptance tests:

- route resolution unit tests for every DIKIWI/Reactor/Entrepreneur workload
- provider smoke test with one small prompt per configured provider
- benchmark with identical 00-Chaos manifests across providers
- report compares novelty, feasibility, evidence grounding, EDA relevance, and business depth

Anti-fake proof:

- reports must include run IDs and LLM call traces
- provider outputs must be generated from identical source manifests
- no provider ranking without saved output artifacts

Exit criteria:

- model switching is a controlled experiment, not a hidden env accident.

### Phase 8: Hosted Private Website Readiness

Goal:

Prepare Aily to run as a private website only for the user.

Deliverables:

- single-owner authentication
- TLS/reverse-proxy-safe websocket config
- upload size/rate limits
- secret management
- storage abstraction for local vs hosted
- backup and restore procedure
- admin-only maintenance actions
- health and readiness endpoints
- basic audit log

Recommended files:

- `aily/config.py`
- `aily/main.py`
- `aily/security/`
- `aily/ui/router.py`
- deployment docs under `docs/`

Acceptance tests:

- unauthenticated upload is rejected in hosted mode
- authenticated upload succeeds
- websocket auth works
- rate limit test rejects abusive upload stream
- backup/restore dry run reconstructs vault, graph, and source manifests

Anti-fake proof:

- tests must run against the configured hosted-mode app, not direct function calls
- security tests must prove rejected requests receive 401/403/429
- backup test must restore into a temp directory and compare counts/hashes

Exit criteria:

- Aily can be exposed as a private website without trusting obscurity.

### Phase 9: Self-Improving Development Harness

Goal:

Make the project manageable by autopilot agents without losing control.

Deliverables:

- task template for every new feature/fix
- evidence gate in PR/commit checklist
- dead-code and stale-doc scan command
- architecture drift report
- prompt-regression test set
- provider benchmark cadence
- Aily-specific local skills for Codex/OMX

Recommended additions:

- `docs/AUTOPILOT_TASK_TEMPLATE.md`
- `docs/TESTING_CONTRACT.md`
- `scripts/verify_project_health.py`
- `tests/prompts/`
- custom skill: `aily-dev`
- custom skill: `aily-e2e`

Acceptance tests:

- running health script reports docs drift, dead code candidates, skipped tests, stale generated artifacts
- prompt-regression tests compare schema and quality rubric scores
- every new plan links to tests and evidence folder

Anti-fake proof:

- health script must inspect real repository files
- prompt tests must save input/output pairs
- no autopilot task closes without evidence path or explicit reason why no runtime evidence applies

Exit criteria:

- future agents can make changes while leaving a readable audit trail.

## Test Strategy

### Test Tiers

| Tier | Purpose | Mocks Allowed | Certifies Product Behavior |
|------|---------|---------------|----------------------------|
| Unit | local function/class correctness | isolated unit doubles only | no |
| Contract | schemas, API payloads, route behavior | no external-success fakes for acceptance | partial |
| Integration | real DB/filesystem/router with configured services | no core mocks for acceptance | partial |
| Real E2E | real files, real vault, real graph, real backend path | no | yes |
| Provider E2E | real model provider calls | no | yes for provider behavior |
| Pressure | volume, concurrency, reliability | no | yes |
| UI E2E | browser against FastAPI | no | yes for Studio behavior |
| Security | auth/rate-limit/secret boundaries | no | yes |

### Required Baseline Commands

Fast local gate:

```bash
python3 -m pytest tests/test_ui_events.py tests/test_ui_router.py tests/llm/test_provider_routes.py -q
npm --prefix frontend run build
python3 -m py_compile aily/main.py aily/ui/router.py aily/ui/events.py aily/config.py
```

Backend subsystem gate:

```bash
python3 -m pytest tests/chaos tests/dikiwi tests/sessions tests/thinking tests/writer -q
```

Full local unit gate:

```bash
python3 -m pytest -q --ignore=tests/integration --ignore=tests/e2e
```

Real E2E tests are separate because they use configured provider calls and are not mocked.

Real scenario gate:

```bash
python3 scripts/run_test_suite.py full-pipeline --max 3 --log-llm --vault /tmp/aily-test-vault
```

Pressure gate:

```bash
python3 scripts/run_mineru_chaos_batch.py /Users/luzi/aily_chaos --vault /tmp/aily-pressure-vault --limit 40 --run-business
```

The pressure gate is not accepted until it writes a run evidence manifest.

### Quality Rubrics

DIKIWI quality:

- Data is atomic, evidence-grounded, and non-gibberish.
- Information clusters datapoints and preserves source evidence.
- Knowledge is graph-neighborhood-derived.
- Insight is path-derived.
- Wisdom connects distant but meaningful graph regions.
- Impact identifies central innovation potential.

Proposal quality:

- proposal is not a shallow restatement of source material
- proposal contains target user/buyer/workflow
- proposal has technical mechanism
- proposal has proof path
- proposal has constraint analysis
- proposal has EDA/deep-tech relevance when source context supports it
- proposal novelty is clear enough to brief a CEO/CTO

Entrepreneur/Guru quality:

- verdict is explicit
- denied ideas still receive deep future-use planning
- business plan is hypothesis-driven and fact-based
- development plan is simulation-driven, constraint-based, and feedback-evolving
- technical plan names architecture, milestones, risks, dependencies, validation experiments
- output links back to proposal and evidence

Frontend quality:

- animations are driven by real events
- user can distinguish live, replay, demo, and failed states
- graph is inspectable at useful node counts
- errors are visible and actionable
- UI remains usable during long runs

## Traceability Matrix

| Product Capability | Backend Proof | Vault Proof | Graph Proof | UI Proof | Test Proof |
|-------------------|---------------|-------------|-------------|----------|------------|
| Drag/drop file intake | source record + upload event | 00-Chaos note | source/data nodes | upload card + live log | UI E2E |
| MinerU extraction with images | extracted sidecars | embeds under `00-Chaos/_assets` | asset metadata on data nodes | source detail drawer | real PDF E2E |
| Data generation | DATA stage result | `01-Data` notes | data nodes | stage completed event | DIKIWI E2E |
| Information clustering | INFORMATION result from data IDs | `02-Information` notes | information nodes + tag props | cluster animation | DIKIWI E2E |
| Knowledge synthesis | subgraph selection metadata | `03-Knowledge` notes | edges/subgraph props | graph edge growth | graph E2E |
| Insight/Wisdom/Impact | threshold + path metadata | `04/05/06` notes | path/centrality metadata | spark/path animation | pressure E2E |
| Proposal generation | Reactor/Residual result | `07-Proposal` notes | proposal nodes | proposal lane | business E2E |
| Entrepreneur review | GStack result | `08-Entrepreneurship` sections | review nodes | judgment room | business E2E |
| Guru appendix | Guru output | appended appendix | appendix metadata | appendix preview | business E2E |
| Provider switching | resolved route logs | run metadata | provider props | LLM console | provider benchmark |
| Hosted privacy | auth middleware | no direct proof | audit node optional | login/session state | security E2E |

## Autopilot Task Contract

Every future autonomous development task should start with this structure:

```markdown
## Task

Goal:

Write scope:

Do not touch:

Behavior expected:

Tests required:

Evidence required:

Acceptance criteria:

Rollback plan:

Docs to update:
```

Completion checklist:

- worktree status inspected before edits
- existing unrelated user changes preserved
- implementation completed
- relevant unit tests passed
- real-path evidence produced if runtime behavior changed
- docs updated if architecture or behavior changed
- final answer includes files changed, tests run, and evidence path

## Immediate Next Work Items

1. Reduce real two-PDF full-pipeline runtime and token cost; the latest accepted run took about 34.7 minutes and 109,025 tokens.
2. Keep Zhipu quarantined unless there is a later explicit decision to re-evaluate it.
3. Move Studio event persistence from JSONL reload into SQLite if JSONL query performance becomes a bottleneck.
4. Unify browser upload and batch ingestion semantics through a durable queue-backed job/run model.
5. Add graph quality checks that fail on generic meaningless hub nodes.
6. Continue refining proposal/review reconciliation checks for 07/08 on larger pressure runs.
7. Before public exposure, run hosted mode behind the actual reverse proxy and validate TLS/websocket forwarding.
8. Promote the Aily-specific development skills into the user's global skill directory if desired.

## Definition Of Done For The Ultimate Goal

Aily is ready as a personal second brain when:

- the private website is the primary interaction surface
- drag/drop and link submission are durable
- Aily Studio shows real live state, not decorative progress
- DIKIWI batch and incremental processing are graph-driven and evidence-linked
- proposals and entrepreneur/guru outputs reconcile with GraphDB and vault notes
- every major run has a saved evidence manifest
- provider/model choices are visible and benchmarkable
- hosted mode has authentication, upload limits, and backup/restore
- future autopilot agents can make changes without destroying traceability
