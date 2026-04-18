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

The stage order is:

`DATA -> INFORMATION -> KNOWLEDGE -> INSIGHT -> WISDOM -> IMPACT`

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

After IMPACT completes, DIKIWI hands off to the proposal layer.

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
- proposal nodes
- innovation scores
- business scores
- review metadata

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

The code that matters for present behavior is the orchestrator, the six stage agents, Residual, Reactor, Entrepreneur, and Guru.
