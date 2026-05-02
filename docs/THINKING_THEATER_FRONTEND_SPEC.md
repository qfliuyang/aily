# Aily Thinking Theater Frontend Spec

Date: 2026-04-26

## North Star

Aily should become a **first-class sensemaking environment**, not just a file processor and not just an Obsidian companion.

The frontend should let a user:

- drag files into Aily from the browser
- watch the DIKIWI pipeline work live
- see the current status of daemon workers and queued jobs
- inspect live LLM/API traffic and failure states
- understand how a new drop changes the large knowledge graph
- see when a threshold-triggered higher-order synthesis fires
- inspect proposals and entrepreneur judgments as visible cognitive artifacts

The product metaphor is:

**A thinking theater for a live knowledge system**

## Product Position

Aily has three layers:

1. **Vault layer**
   - Obsidian-compatible files and images
   - human-editable notes
2. **Cognition layer**
   - graph, DIKIWI stages, Reactor, Entrepreneur, Guru
3. **Sensemaking layer**
   - the frontend
   - the place where a human sees thinking happen

The frontend should be the primary operational interface for the system.

## Core Experience

When a user drops a PDF into the website:

1. the file visibly enters Aily
2. the user sees it become `00-Chaos`
3. the user sees `01-Data` form from chaos
4. the user sees clustering into `02-Information`
5. the user sees knowledge edges form
6. the user sees insight paths light up
7. the user sees wisdom arcs span across the graph
8. the user sees impact nuclei emerge
9. if the graph threshold is crossed, the user sees a **synaptic spark event**
10. proposals crystallize
11. entrepreneur review appears as a live judgment room

The UI should answer:

- What is Aily doing right now?
- Which worker is active?
- Which model/provider is being called?
- Which stage is blocked or slow?
- Which nodes were created from this file?
- Did this drop change the broader brain or not?
- What innovation ideas emerged from it?

## Product Surfaces

The frontend should have five major surfaces.

## 1. Intake Dock

Purpose:
- drag-and-drop entry point
- queue visibility
- source upload state

Main elements:
- full-width drop zone
- recent uploads rail
- per-file cards
- queue length and daemon health
- source type badges: `pdf`, `url`, `image`, `folder`

Required interactions:
- drag file into browser
- drag folder into browser later
- see upload progress
- see extraction start automatically
- click any file to “follow its thinking”

## 2. Stage Theater

Purpose:
- the main animated DIKIWI visual
- one input or subgraph shown moving through the pipeline

This is the hero surface.

Each DIKIWI stage needs its own visual grammar:

### `00-Chaos`
- visual: unstable particle cloud
- shape: fragments, dust, text scraps
- motion: turbulence, drift, compression
- meaning: raw, pre-structured source material

### `01-Data`
- visual: particle field splitting into atomic points
- shape: small luminous nodes
- motion: quantization, snapping, separation
- meaning: discrete datapoints extracted from chaos

### `02-Information`
- visual: nodes acquire category halos and cluster colors
- shape: bounded clouds
- motion: attraction, grouping, sorting
- meaning: classified and tagged data

### `03-Knowledge`
- visual: stable edges appear among clusters
- shape: graph bridges
- motion: gradual line growth, weak-edge pruning
- meaning: structural relationship formation

### `04-Insight`
- visual: one bright route pulses through a subgraph
- shape: directed path
- motion: flowing highlighted traversal
- meaning: meaningful local synthesis

### `05-Wisdom`
- visual: long arcs span distant clusters
- shape: cross-region trajectories
- motion: broad sweeping curves
- meaning: higher-order synthesis across far nodes

### `06-Impact`
- visual: central nodes gain gravity halos and field pull
- shape: nucleus/core
- motion: nearby nodes subtly curve inward
- meaning: innovation center with system-level leverage

### Threshold event
- visual: branching electrical burst through the graph
- motion: one-time brain-spark pulse
- meaning: enough graph change occurred to trigger deeper cognition

### `07-Proposal`
- visual: stable cards condense from impact nodes
- motion: graph energy compresses into proposal artifacts
- meaning: venture hypotheses emerge

### `08-Entrepreneurship`
- visual: proposal cards enter a panel chamber
- motion: reviewed, split, stamped, annotated
- meaning: market reality and execution logic applied

## 3. Brain Graph

Purpose:
- persistent live graph of the entire vault
- the operational knowledge map

This should be inspired by Obsidian Graph view, but not dependent on it.

The graph must support:

- zoom / pan / search
- stage filtering
- provider filtering
- source filtering
- time slicing
- “show only nodes from this upload”
- “show only affected subgraph”
- “show only new nodes since threshold event”
- click node -> open note summary and provenance

Node metadata to surface:

- DIKIWI stage
- file/source lineage
- grounded_in references
- creation time
- model/provider used
- whether node came from incremental update
- whether node triggered proposal generation

Graph styling:

- `00`: noisy, dim, diffuse
- `01`: small white points
- `02`: color-coded clusters
- `03`: brighter relationship edges
- `04`: gold path emphasis
- `05`: electric long arcs
- `06`: red-orange high-gravity centers
- `07`: diamond or card-glyph nodes
- `08`: tribunal / verdict glyph nodes

## 4. Live Log Console

Purpose:
- operational trust surface
- show that the system is actually working
- reveal API behavior, latency, retries, failures, and reasoning cadence

This is mandatory.

The user explicitly wants to see:

- LLM API calls
- actual live logs
- status of thinking

The console should support three layers:

### Layer A: human-readable event stream
- `PDF uploaded`
- `MinerU extraction started`
- `DataAgent executing`
- `DeepSeek v4-pro request started`
- `Knowledge subgraph selected`
- `Threshold crossed: +7.2% information growth`
- `Residual generated 4 proposals`
- `Entrepreneur evaluating proposal 2/4`

### Layer B: structured execution details
- job id
- pipeline id
- stage
- provider
- model
- request duration
- token usage
- retries
- errors

### Layer C: raw technical log
- request payload metadata
- response metadata
- tracebacks
- rate limit messages
- queue / worker diagnostics

The default should show Layer A + B, with Layer C expandable.

## 5. Judgment Room

Purpose:
- show proposal generation and entrepreneur evaluation
- make innovation review legible

Main elements:
- proposal cards
- GStack panel summary
- Guru appendix preview
- verdict lanes:
  - `build`
  - `pivot`
  - `needs_more_validation`
  - `deny`

The user should be able to click a proposal and see:

- originating impact / wisdom / insight chain
- proposal text
- evidence path
- GStack verdict
- Guru appendix
- provider/model used

## Visual Identity

The frontend should not look like a normal admin dashboard.

Recommended direction:

- visual theme: **cognitive systems lab**
- palette:
  - graphite / deep teal / oxidized bronze base
  - amber for chaos
  - white for data
  - cyan / green for information
  - steel blue for knowledge
  - gold for insight
  - electric blue for wisdom
  - ember / coral for impact
- tone:
  - scientific
  - cinematic
  - precise

Typography:
- one strong technical grotesk or geometric family for UI
- one more characterful display face for stage labels and hero lines

Avoid:
- generic chat-app styling
- flat dashboard grids
- purple-on-black AI cliché

## Frontend Architecture

Recommended stack:

- **React**
- **Vite**
- **TypeScript**
- **PixiJS** for the stage theater and animated graph effects
- **Sigma.js** or **react-force-graph** for the persistent graph layer
- **Framer Motion** for UI panels and card transitions
- **Zustand** for local event/state management
- **TanStack Query** for API polling/query state

Recommendation:
- use **PixiJS** for the hero theater
- use **Sigma.js** or **react-force-graph** for the persistent graph view

Do not try to reuse Obsidian’s native renderer.

## Backend Contract

The current backend writes outputs, but the frontend needs **live events**.

Add a visualization event stream.

Recommended transport:

- **WebSocket** for high-frequency live updates
- SSE fallback later if needed

Recommended event schema:

```json
{
  "type": "stage_started",
  "timestamp": "2026-04-26T14:10:22Z",
  "pipeline_id": "dikiwi_drop_abc123",
  "source_id": "rain_123",
  "stage": "INFORMATION",
  "provider": "kimi",
  "model": "kimi-k2.6",
  "payload": {
    "node_count_before": 42,
    "node_count_after": 58
  }
}
```

Core event types:

- `source_uploaded`
- `source_ingest_started`
- `chaos_note_created`
- `stage_started`
- `stage_completed`
- `node_created`
- `edge_created`
- `subgraph_selected`
- `threshold_crossed`
- `spark_triggered`
- `proposal_created`
- `proposal_review_started`
- `proposal_review_completed`
- `worker_status_changed`
- `llm_request_started`
- `llm_request_completed`
- `llm_request_failed`
- `pipeline_failed`

## Required API Endpoints

### Upload
- `POST /api/ui/uploads`
  - multipart file upload
  - returns upload id, source id, pipeline id

### Queue / daemon status
- `GET /api/ui/status`
  - daemon health
  - queue depth
  - active pipelines
  - active workers

### Graph snapshot
- `GET /api/ui/graph`
  - nodes
  - edges
  - metadata

### File-specific trace
- `GET /api/ui/pipelines/{pipeline_id}`
  - stage status
  - node ids
  - proposal ids
  - log summary

### Event stream
- `WS /api/ui/events`

### Live logs
- `GET /api/ui/logs`
  - filterable by:
    - pipeline
    - provider
    - stage
    - level

## Drag-and-Drop Requirements

This is a first-class feature.

The user should be able to:

- drag one file into the browser
- drag multiple files
- later drag a folder
- see local previews before upload starts
- choose:
  - process immediately
  - batch into a queue
  - watch live

Drop zone behavior:

- idle state: large central target
- hover state: entire stage theater subtly reacts
- accepted state: dropped object visually falls into `00-Chaos`
- upload progress: ring or spine meter

This interaction should feel theatrical, not mechanical.

## Operational Transparency

The frontend must make failures visible.

If Aily is stuck, the user should immediately see:

- which stage
- which provider/model
- how long it has been waiting
- whether a retry is happening
- whether a rate limit occurred
- whether a downstream stage is blocked

This is especially important because:

- the system uses multiple providers
- some workloads are incremental
- the user wants confidence that the system is functioning, not pretending

## Hosting Model

The system should be hostable as a website later.

Recommended deployment shape:

### Local-first mode
- FastAPI backend runs on local machine
- frontend served locally
- daemons operate against local vault and graph

### Hosted mode later
- frontend hosted as a web app
- backend API hosted with worker processes
- vault and graph persisted on the server
- local Obsidian becomes optional instead of primary

This means the frontend should not assume it lives inside Obsidian or inside a desktop shell.

## Obsidian Integration Strategy

Recommendation:

- treat Obsidian as a storage/editor ecosystem
- do not depend on Obsidian for rendering the web graph

Possible later integration:

- optional Obsidian plugin that deep-links from a node in Aily Studio to a note in Obsidian
- optional “Open in Obsidian” button
- optional sync status panel

But the main product should be independent.

## Implementation Phases

## Phase 1: Operational MVP

Goal:
- make the system observable and usable

Deliver:
- drag-and-drop upload
- queue and daemon status
- stage progress per file
- live event/log panel
- basic graph snapshot
- click-to-open note preview

No heavy cinematic animation required yet.

## Phase 2: Thinking Theater

Goal:
- show DIKIWI as live visual cognition

Deliver:
- stage-specific animation grammar
- node birth and edge formation
- threshold spark animation
- subgraph growth animation
- file-follow mode

## Phase 3: Business Theater

Goal:
- make innovation generation and judgment visible

Deliver:
- proposal crystallization animation
- judgment room
- GStack and Guru surfaces
- verdict transitions

## Phase 4: Hosted Product

Goal:
- production-grade deployable web system

Deliver:
- authentication
- multi-user sessions
- persisted run history
- replay mode
- remote daemon/worker control

## Recommended First Build

If starting implementation now, build this sequence:

1. `Aily Studio shell`
   - app layout
   - left: queue and intake
   - center: stage theater
   - right: live log console
   - bottom or separate tab: graph

2. `Event stream`
   - backend emits lifecycle events
   - frontend subscribes and updates live

3. `Drop zone`
   - drag PDF into browser
   - upload and start queue job

4. `Minimal animation mapping`
   - chaos cloud
   - data points
   - cluster formation
   - edge appearance

5. `Graph merge animation`
   - theater nodes move into persistent brain graph

6. `Threshold spark`
   - trigger when `NetworkSynthesisSelector` threshold is crossed

7. `Proposal + entrepreneur cards`

## Final Recommendation

Build **Aily Studio** as a standalone web frontend with:

- drag-and-drop intake
- live daemon and queue visibility
- live LLM/API call telemetry
- DIKIWI stage theater
- persistent brain graph
- proposal/judgment room

Do not try to embed Obsidian’s graph directly.

The right product is:

**an operational, cinematic, inspectable knowledge cognition system**

not:

**a prettier file browser for Obsidian**
