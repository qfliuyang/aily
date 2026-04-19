# DIKIWI Architecture

This document describes the DIKIWI runtime that is active in the repo today.

## Active Entry Point

The continuous DIKIWI entrypoint is:

- `aily/sessions/dikiwi_mind.py`

That file builds an `AgentContext`, instantiates `DikiwiOrchestrator`, registers the stage agents, and runs the pipeline.

## Stage Runtime

The active stage agents live in:

- `aily/dikiwi/agents/data_agent.py`
- `aily/dikiwi/agents/information_agent.py`
- `aily/dikiwi/agents/knowledge_agent.py`
- `aily/dikiwi/agents/insight_agent.py`
- `aily/dikiwi/agents/wisdom_agent.py`
- `aily/dikiwi/agents/impact_agent.py`

The nominal stage order is:

`DATA -> INFORMATION -> KNOWLEDGE -> INSIGHT -> WISDOM -> IMPACT`

The semantic boundary is important:

- `DATA` is raw scattered datapoints from the incoming file/message.
- `INFORMATION` is classified, tagged datapoints written into GraphDB and the vault.
- `KNOWLEDGE` and later stages operate on selected graph neighborhoods, not only on the current file text.

`KNOWLEDGE` now scans the GraphDB node structure through `aily/dikiwi/network_synthesis.py`. It selects meaningful subgraphs around changed information nodes, shared tags, existing information neighbors, edge density, and source diversity. If the graph-change score does not cross the configured threshold, or the changed nodes do not attach to an existing information neighborhood, the pipeline stops at `KNOWLEDGE` and does not generate `INSIGHT`, `WISDOM`, `IMPACT`, or post-impact proposals.

The relevant settings are:

- `DIKIWI_NETWORK_MIN_NODES` / `dikiwi_network_min_nodes`
- `DIKIWI_NETWORK_TRIGGER_SCORE` / `dikiwi_network_trigger_score`
- `DIKIWI_NETWORK_MAX_CANDIDATE_NODES` / `dikiwi_network_max_candidate_nodes`

This matches the intended DIKIWI methodology: higher-order generated content should come from graph structure and graph change, not from a single source file acting alone.

## Orchestrator

The runtime coordinator is:

- `aily/dikiwi/orchestrator.py`

Its active responsibilities are:

- event-driven stage coordination
- state transitions
- Menxia review gate
- CVO approval gate
- stage-agent dispatch

The orchestrator is active runtime. It is not just design material.

## Current Gate Behavior

The DIKIWI runtime still contains explicit Menxia and CVO gates.

In the `DikiwiMind` entry path, CVO is configured with immediate TTL auto-approval so the continuous pipeline does not block waiting for manual approval.

## Post-Impact Flow

After IMPACT completes, DIKIWI hands off to the proposal layer. If a run stops at `KNOWLEDGE` because the graph-change threshold was not reached, this post-impact flow is skipped.

### Reactor

- file: `aily/sessions/reactor_scheduler.py`
- role: generate framework proposals and innovation-screen residual proposals

### Residual

- file: `aily/dikiwi/agents/residual_agent.py`
- role: synthesize vault, graph, and reactor proposals into structured proposal drafts

Residual persists proposal nodes as `residual_proposal` in GraphDB.

### Entrepreneur

- file: `aily/sessions/entrepreneur_scheduler.py`
- role: business review for `pending_business` proposals

### Guru

- file: `aily/sessions/gstack_agent.py`
- role: produce deep post-verdict appendix planning for both approved and denied proposals

## Effective Pipeline

The effective runtime is:

`DIKIWI -> Reactor -> Residual -> Reactor screening -> Entrepreneur -> Guru`

That is the actual operational model. Older documentation that refers to `Innolaval` and `Hanlin` is stale relative to the current code.

## Storage Outputs

### Obsidian

The active vault layout is:

- `00-Chaos`
- `01-Data`
- `02-Information`
- `03-Knowledge`
- `04-Insight`
- `05-Wisdom`
- `06-Impact`
- `07-Proposal`
- `08-Entrepreneurship`

### GraphDB

GraphDB currently stores:

- DIKIWI nodes and edges
- information-node properties used for graph synthesis: tags, domain, concept, source paths, pipeline id
- proposal nodes
- innovation scores
- business scores
- review metadata

## Graph-Triggered Generation

DIKIWI uses a lightweight dynamic-graph trigger rather than blindly running the whole six-stage ladder for every file.

1. `INFORMATION` writes every classified datapoint as an information node and connects it to tag nodes.
2. `KNOWLEDGE` loads neighborhoods around changed nodes, especially shared tag neighborhoods.
3. The network selector scores candidate subgraphs by changed-node count, existing information neighbors, source diversity, edge count, and local relation strength.
4. If the best candidate crosses threshold, `KNOWLEDGE` asks the LLM to map durable relations across the selected graph subgraph.
5. `INSIGHT` receives the selected subgraph and generated relations, then looks for 2-4 node paths that reveal non-obvious mechanisms, tensions, gaps, or opportunities.
6. `WISDOM` and `IMPACT` use those network-grounded insights, not the raw file, as their grounding.

Research basis:

- GraphRAG argues that broad corpus questions need graph construction and community summaries rather than flat retrieval: https://arxiv.org/abs/2404.16130
- Dynamic graph matching research distinguishes full-snapshot matching from incremental matching over changed graph regions: https://link.springer.com/article/10.1007/s10115-022-01753-x
- Incremental community detection addresses the need to update graph communities when new streams are added: https://arxiv.org/abs/2110.06311
- Frequent subgraph mining frames recurring connected structures as meaningful graph patterns: https://hanj.cs.illinois.edu/pdf/icdm02_gspan.pdf

## Experimental Packages

The repo still includes:

- `aily/dikiwi/skills/`
- `aily/dikiwi/memorials/`

These are not part of the active production path. They should be treated as experimental or quarantined subsystems until they are explicitly rewired into the runtime.

## What DIKIWI Is Not Right Now

DIKIWI is not currently:

- a skills-driven runtime
- a memorial-persisting audit system
- the old `Innolaval/Hanlin` MAC architecture described in older docs
- a guarantee that every file reaches `INSIGHT` or `IMPACT`

The code that matters for present behavior is the orchestrator, the six stage agents, Residual, Reactor, Entrepreneur, and Guru.
