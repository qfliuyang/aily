# Aily Thinking Theater Development Plan

Date: 2026-04-26

## Goal

Build a production-capable frontend for Aily that functions as a **first-class sensemaking environment**.

The frontend must let a user:

- drag and drop files into Aily from the browser
- watch DIKIWI stages execute live
- inspect daemon, queue, and worker status
- inspect LLM/API traffic and failures live
- see graph growth in real time
- watch threshold-triggered higher-order synthesis
- inspect proposals and entrepreneur judgments

This plan assumes:

- backend remains FastAPI-based
- vault and `graph.db` remain core data stores
- local-first deployment comes first
- hosted deployment comes after the local-first UI is stable

## Success Criteria

The frontend is successful when all of the following are true:

1. A user can drop a PDF in the browser and immediately see a live pipeline trace.
2. A user can tell, at any point, which stage is active and which provider/model is being used.
3. A user can see nodes appear and merge into the long-lived graph.
4. A user can distinguish normal progress from stuck / rate-limited / failed states.
5. A user can inspect why a proposal was generated and what evidence path led to it.
6. The frontend works as a standalone website and does not depend on Obsidian rendering.

## Product Scope

## In scope

- web app frontend
- live upload flow
- live event stream
- queue / daemon / worker status
- stage theater animation
- persistent graph view
- live log console
- proposal / entrepreneur review surfaces
- replay support for recent runs

## Out of scope for v1

- full multi-user collaboration
- editing notes in the browser
- embedding native Obsidian graph view
- mobile-first optimization beyond basic responsive support
- complete cloud tenancy / SaaS auth stack

## Delivery Strategy

Use a staged build:

1. **Operational visibility first**
2. **Live graph and stage theater second**
3. **Proposal and entrepreneur theater third**
4. **Hosted hardening fourth**

This avoids spending weeks on cinematic visuals before the system is observable.

## Workstreams

The project should be split into five workstreams:

1. **Frontend app shell**
2. **Backend event and status APIs**
3. **Graph and pipeline visualization**
4. **Operational logging and telemetry**
5. **Production hardening and deployment**

## Target Architecture

## Frontend

Recommended stack:

- React
- TypeScript
- Vite
- Zustand
- TanStack Query
- PixiJS
- Sigma.js or `react-force-graph`
- Framer Motion
- Tailwind or CSS Modules

### Why this stack

- React gives fast iteration and state composition
- Vite keeps the local-first developer loop fast
- PixiJS is well-suited for the stage theater
- Sigma.js or `react-force-graph` is better than writing the entire persistent graph from scratch
- Zustand is sufficient for runtime event state without Redux overhead

## Backend

Keep FastAPI as the control plane and add UI-oriented services:

- upload ingestion endpoint
- queue / daemon status endpoint
- graph snapshot endpoint
- pipeline trace endpoint
- websocket event stream
- structured log query endpoint

## Data sources

The frontend should read from:

- vault markdown
- `graph.db`
- queue state
- daemon state
- LLM request telemetry
- pipeline event stream

## Phase Plan

## Phase 0: Foundation and Discovery

Duration:
- 2 to 4 days

Goal:
- establish the frontend project and the backend event contract

Deliverables:

- `frontend/` app scaffold
- app shell routing
- basic design tokens
- initial websocket event schema
- backend API contract doc
- recorded real event replay file from an evidence run

Tasks:

- create frontend workspace
- define app routes
- define shared TS types for events
- define stage enum and node metadata schema
- define provider/model telemetry schema
- define log level taxonomy

Decisions to lock:

- `frontend/` placement in repo
- package manager
- styling system
- graph library choice
- websocket protocol shape

## Phase 1: Operational MVP

Duration:
- 1 to 2 weeks

Goal:
- make Aily observable and usable without fancy visuals yet

Frontend deliverables:

- app shell layout
- drag-and-drop upload zone
- upload progress
- queue and daemon status panel
- worker cards
- live event/log console
- file-by-file pipeline progress view

Backend deliverables:

- `POST /api/ui/uploads`
- `GET /api/ui/status`
- `GET /api/ui/pipelines/{pipeline_id}`
- `WS /api/ui/events`
- event emission from upload, chaos extraction, DIKIWI stage start/finish

UI layout for MVP:

- left column: Intake + queue
- center: active pipeline cards
- right column: live log console

Tasks:

### Frontend

- build `AppShell`
- build `DropZone`
- build `UploadQueuePanel`
- build `DaemonStatusPanel`
- build `WorkerStatusGrid`
- build `PipelineRunCard`
- build `LiveLogPanel`
- build websocket store
- build status polling

### Backend

- file upload API
- pipeline/job registration
- event broadcaster service
- queue/daemon summary serializer
- initial event producers from chaos and DIKIWI

Acceptance criteria:

- drag a file into the browser
- upload starts successfully
- queue count updates
- worker status updates appear
- stage changes appear in the log
- API/provider/model info is visible in the live console

## Phase 2: Brain Graph MVP

Duration:
- 1 week

Goal:
- show the persistent graph and let the user inspect the knowledge structure

Frontend deliverables:

- graph page/panel
- stage filter controls
- search
- node detail drawer
- source filter
- “show nodes from current pipeline” mode

Backend deliverables:

- `GET /api/ui/graph`
- graph snapshot serializer
- node metadata endpoint if separate

Tasks:

### Graph model

- define graph node schema
- define graph edge schema
- define stage/color mapping
- define node-to-note deep link metadata

### Frontend

- implement graph canvas
- node hover tooltips
- node detail drawer
- stage legend
- graph filters
- fit-to-subgraph function

Acceptance criteria:

- user can see the full graph
- user can filter by DIKIWI stage
- user can click a node and inspect metadata
- user can isolate nodes created by a specific upload

## Phase 3: Thinking Theater

Duration:
- 2 to 3 weeks

Goal:
- add stage-specific animated cognition visuals tied to real pipeline events

This is the cinematic phase.

Deliverables:

- stage theater canvas
- stage-specific visual states
- live transition engine
- node birth and edge birth animation
- graph merge animation
- threshold spark animation

Tasks:

### Visual engine

- set up PixiJS scene manager
- create stage transition controller
- build particle engine for chaos
- build node formation animation for data
- build clustering animation for information
- build edge growth animation for knowledge
- build path pulse animation for insight
- build long-arc bridge animation for wisdom
- build nucleus/gravity animation for impact
- build spark event for threshold crossing

### Event mapping

Map real events to visuals:

- `chaos_note_created` -> create turbulence cloud
- `node_created` during DATA -> emit point nodes
- `node_created` during INFORMATION -> cluster and recolor
- `edge_created` during KNOWLEDGE -> grow structural links
- `subgraph_selected` -> spotlight affected neighborhood
- `threshold_crossed` -> show charge buildup
- `spark_triggered` -> fire branching pulse

### Interaction

- follow one file mode
- follow one subgraph mode
- pause/replay current run

Acceptance criteria:

- user can visually follow one file through DIKIWI
- theater animations are driven by actual events, not fake timers
- threshold spark triggers only when real backend threshold event fires

## Phase 4: Proposal and Judgment Theater

Duration:
- 1 to 2 weeks

Goal:
- make innovation generation and entrepreneur evaluation visible and inspectable

Deliverables:

- proposal crystallization panel
- proposal cards from `07-Proposal`
- entrepreneur judgment room
- GStack summary panel
- Guru appendix preview
- verdict lanes and transitions

Tasks:

### Frontend

- build `ProposalLane`
- build `ProposalCard`
- build `JudgmentRoom`
- build `VerdictPill`
- build `EvidenceChainPanel`
- build `GuruAppendixPanel`

### Backend

- proposal-created event
- review-started event
- review-completed event
- proposal lineage API
- judgment metadata API

Acceptance criteria:

- user can see proposals appear after higher-order synthesis
- user can open a proposal and inspect its origin chain
- user can see entrepreneur verdict and rationale

## Phase 5: Replay and Comparative Runs

Duration:
- 1 week

Status:
- partially implemented: evidence run registry APIs exist, Studio Operations can list runs, and UI events can persist to JSONL and reload after restart.
- remaining: queryable event storage, timeline scrubber, graph diff overlays, and provider comparison UI.

Goal:
- make past runs explainable and comparable

Deliverables:

- replay mode for recent runs
- timeline scrubber
- run comparison mode
- compare providers visually

Tasks:

- persist event streams for completed runs
- build replay timeline controller
- build run selector
- build diff overlays for graph changes

Acceptance criteria:

- user can replay a previous pipeline run
- user can compare Kimi vs DeepSeek runs visually

## Phase 6: Local Product Hardening

Duration:
- 1 week

Goal:
- make the frontend robust for daily use on a local machine

Deliverables:

- reconnect-safe websocket client
- large-log virtualization
- graph performance tuning
- persistent UI state
- error boundaries

Tasks:

- log list virtualization
- graph node count performance testing
- websocket resume/retry strategy
- upload retry handling
- stage timeout UI indicators
- stalled worker detection

Acceptance criteria:

- UI remains responsive during long runs
- reconnect after backend restart works
- large graphs remain usable

## Phase 7: Hosted Website Readiness

Duration:
- 1 to 2 weeks

Goal:
- prepare the product to run as a hosted website later

Deliverables:

- deployable frontend build
- reverse-proxy-safe websocket handling
- config separation for local vs hosted
- single-owner auth boundary
- upload size and active-upload guardrails

Tasks:

- extract environment config
- add backend CORS/session strategy
- add artifact path abstraction
- define user/session scoping model
- define storage abstraction for vault and graph access
- add hosted-mode rate-limit tests before public exposure

## Detailed Backend Plan

## 1. UI event bus

Add a backend event broadcaster.

Responsibilities:

- accept internal pipeline events
- fan out to websocket subscribers
- persist events for replay when configured

Implementation options:

- in-process async pub/sub plus JSONL persistence first
- Redis pub/sub later if needed

Recommended first version:

- in-process event hub with replay buffer and disk-backed JSONL reload

## 2. Event emission points

Instrument these locations:

- upload accepted
- chaos extraction start/finish
- MinerU start/finish
- DATA/INFORMATION/KNOWLEDGE/INSIGHT/WISDOM/IMPACT stage start/finish
- node creation
- edge creation
- threshold decision
- proposal creation
- entrepreneur review start/finish
- LLM request start/finish/failure

Likely code touchpoints:

- chaos processors
- `DikiwiMind`
- `IncrementalOrchestrator`
- `ReactorScheduler`
- `EntrepreneurScheduler`
- LLM client wrapper

## 3. LLM telemetry

This must be explicit.

Capture:

- provider
- model
- stage
- pipeline id
- latency
- token usage if available
- success / failure
- retry count
- rate limit events

Add event types:

- `llm_request_started`
- `llm_request_completed`
- `llm_request_failed`

## 4. Queue and daemon visibility

Create a daemon snapshot model:

- daemon up/down
- active workers
- queue depth
- active pipelines
- last completed pipeline
- last failure

Expose:

- `GET /api/ui/status`

## Detailed Frontend Plan

## Routes

Recommended routes:

- `/`
  - main theater
- `/graph`
  - brain graph
- `/runs`
  - historical runs
- `/proposals`
  - proposal and entrepreneur view
- `/settings`
  - provider and daemon diagnostics later

## Core components

### App shell

- `StudioShell`
- `TopBar`
- `SidebarNav`
- `StatusStrip`

### Intake

- `DropZone`
- `UploadProgressCard`
- `QueuePanel`

### Operations

- `DaemonStatusPanel`
- `WorkerGrid`
- `PipelineRunList`
- `LiveLogPanel`

### Theater

- `ThinkingStageCanvas`
- `ChaosParticleField`
- `DataNodeBurst`
- `InformationClusterLayer`
- `KnowledgeEdgeLayer`
- `InsightPathPulse`
- `WisdomArcLayer`
- `ImpactCoreLayer`
- `ThresholdSparkLayer`

### Graph

- `BrainGraph`
- `GraphFilters`
- `NodeDrawer`

### Judgment

- `ProposalLane`
- `ProposalCard`
- `JudgmentRoom`
- `EvidenceChain`
- `GuruAppendix`

## Design system plan

Create explicit tokens for:

- colors by DIKIWI stage
- motion durations
- spacing
- typography scale
- panel depth and glass effect
- alert/failure states

Motion tokens should differentiate:

- slow atmospheric motion
- stage transition motion
- critical event flashes
- verdict transitions

## Animation Implementation Plan

## Principle

Animations must be **event-driven**, not decorative.

Every visible motion should correspond to a real backend event.

## Animation layers

### Layer 1: ambient

- subtle background motion
- always on
- low visual priority

### Layer 2: stage process

- file-specific DIKIWI evolution
- medium visual priority

### Layer 3: graph mutation

- new nodes/edges joining persistent graph
- high informational priority

### Layer 4: cognition spikes

- threshold spark
- proposal crystallization
- verdict transition

## Performance constraints

- stage theater should stay smooth with dozens of animated nodes
- persistent graph should degrade gracefully with larger vaults
- logs must be virtualized
- animation should respect reduced motion preference

## Testing Plan

## Frontend tests

- component rendering tests
- websocket event reducer tests
- upload flow tests
- graph filter tests
- log panel expansion tests

## Backend tests

- event emission tests
- websocket delivery tests
- upload endpoint tests
- graph serialization tests
- daemon status snapshot tests

## Integration tests

- upload a file -> UI receives stage events
- threshold crossing -> spark event emitted
- proposal generated -> proposal card appears
- entrepreneur review -> judgment room updates

## Manual acceptance tests

1. drop a PDF in browser
2. confirm upload appears instantly
3. confirm worker status updates
4. confirm LLM call telemetry visible
5. confirm data nodes appear in theater
6. confirm graph gains nodes
7. confirm threshold spark appears when appropriate
8. confirm proposal and entrepreneur outputs appear

## Team / Sequence Recommendation

Best execution order:

1. backend event model
2. upload and queue UX
3. live logs and worker status
4. graph snapshot view
5. stage theater animation
6. proposal/judgment room
7. replay and hosting hardening

Reason:

- observability must exist before cinematic layers are worth building
- event correctness is the backbone of the whole product

## Risks

## Risk 1: event plumbing too shallow

If backend does not emit enough structured events, the frontend will devolve into fake animation.

Mitigation:

- instrument stage lifecycle before animation work starts

## Risk 2: graph rendering performance

Large vaults may overwhelm a naive force-directed graph.

Mitigation:

- start with filtered views
- add level-of-detail behavior
- separate theater graph from full persistent graph

## Risk 3: log noise overload

Too much raw logging will make the UI unreadable.

Mitigation:

- three log layers
- human-readable stream by default
- structured/raw expandable

## Risk 4: visual polish without product clarity

The UI could become cinematic but not useful.

Mitigation:

- operational MVP first
- every animation tied to real meaning

## Risk 5: local-first assumptions block hosted future

Mitigation:

- define API-first boundaries now
- do not couple frontend directly to filesystem paths

## MVP Definition

The minimum version that should be considered “real” is:

- drag-and-drop upload works
- queue/daemon status visible
- live stage progress visible
- provider/model/latency visible
- graph snapshot visible
- nodes merge into graph from active run
- threshold spark event supported
- proposal/judgment output visible

If any of those are missing, the theater is not yet complete enough.

## Final Recommendation

Build this as **Aily Studio** in the following order:

1. event backbone
2. operational shell
3. graph view
4. stage theater
5. judgment room
6. replay and hosted readiness

This gives Aily not just a frontend, but a visible cognition environment that users can trust, inspect, and eventually host as a website.
