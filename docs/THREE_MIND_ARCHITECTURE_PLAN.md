# Aily Three-Mind DIKIWI Architecture Plan

## Context

Re-architecting Aily from a single gating system to a **Three-Mind System** based on the DIKIWI (Data-Information-Knowledge-Insight-Wisdom-Impact) model. The user wants:

1. **DIKIWI Mind**: Continuously process information flood into atomic ideas
2. **Innovation Mind**: Daily sessions to generate insights (TRIZ-focused)
3. **Entrepreneur Mind**: Daily sessions to evaluate business potential (GStack-focused)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT LAYER                                     │
│  URLs │ Voice │ Documents │ Chat │ Clipboard │ Sessions                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HYDROLOGICAL GATING SYSTEM (Existing)                     │
│  RAIN (Inputs) → DRAINAGE (Routing) → RESERVOIR (Enrichment) → DAM (Gating)  │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│    DIKIWI MIND       │  │   INNOVATION MIND    │  │  ENTREPRENEUR MIND   │
│ (Every Input)        │  │ (Daily @ 9am)        │  │ (Daily @ 10am)       │
│                      │  │                      │  │                      │
│ • DIKIWI Pipeline    │  │ • TRIZ Analysis      │  │ • GStack Analysis    │
│ • Atomic Notes       │  │ • McKinsey Structuring│  │ • PMF Evaluation     │
│ • GraphDB Links      │  │ • Insight Proposals  │  │ • Business Proposals │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT LAYER                                    │
│  Obsidian:                          Feishu:                                  │
│  ├── Aily/Ideas/                    • "New proposals ready"                  │
│  ├── Aily/Proposals/Innovation/     • Session summaries                      │
│  └── Aily/Proposals/Business/       • Action required                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## DIKIWI Pipeline

| Stage | Description | Auto-Promote | Output |
|-------|-------------|--------------|--------|
| **D**ata | Raw input | Yes (on extraction) | QueueDB record |
| **I**nformation | Structured content | Yes (on structure) | Extracted entities |
| **K**nowledge | Atomic ideas | Yes (on atomicization) | Obsidian/Ideas/ + GraphDB |
| **I**nsight | Pattern recognition | Yes (if patterns found) | Insight tags |
| **W**isdom | Synthesis | Yes (if synthesis achieved) | Internal synthesis notes |
| **I**mpact | Actionable proposals | Yes (if proposal generated) | Obsidian/Proposals/ |

## Three Minds

### DIKIWI Mind (Knowledge Management)
- **Trigger**: Every input
- **Output**: Atomic notes in `Aily/Ideas/YYYY-MM-DD-[slug].md`
- **Responsibilities**: Extract atomic ideas, build knowledge graph, track stages

### Innovation Mind (Insight Generation)
- **Trigger**: Daily at 8:00 AM
- **Output**: Proposals in `Aily/Proposals/Innovation/`
- **Frameworks**: TRIZ (primary) + McKinsey (secondary)
- **Responsibilities**: Review 24h knowledge, find contradictions, generate insight proposals

### Entrepreneur Mind (Business Success)
- **Trigger**: Daily at 9:00 AM
- **Output**: Business proposals in `Aily/Proposals/Business/`
- **Frameworks**: GStack (primary) + McKinsey (secondary)
- **Responsibilities**: Evaluate proposals for PMF, growth loops, viability

## Implementation Files

### New Files (19)
```
aily/minds/
├── __init__.py
├── base.py                          # BaseMind abstract class
├── dikiwi/
│   ├── __init__.py
│   ├── mind.py                      # DikiwiMind
│   ├── pipeline.py                  # DIKIWI stages
│   ├── stages.py                    # DikiwiStage enum
│   ├── models.py                    # KnowledgeNode
│   └── storage.py
├── innovation/
│   ├── __init__.py
│   ├── mind.py                      # InnovationMind
│   ├── session.py                   # Innovation session logic
│   ├── proposal_generator.py
│   └── models.py
└── entrepreneur/
    ├── __init__.py
    ├── mind.py                      # EntrepreneurMind
    ├── session.py                   # Entrepreneur session logic
    ├── evaluator.py                 # PMF/growth evaluation
    └── models.py

aily/sessions/
├── __init__.py
├── scheduler.py                     # SessionScheduler
├── models.py                        # SessionConfig, SessionResult
└── registry.py

aily/proposals/
├── __init__.py
├── models.py                        # Proposal models
├── storage.py
└── formatter.py

aily/integration/three_mind_gating.py  # Gating integration
```

### Modified Files (4)
```
aily/gating/drainage.py              # Route to DIKIWI Mind
aily/gating/reservoir.py             # Track DIKIWI stage
aily/scheduler/jobs.py               # Add session schedulers
aily/main.py                         # Initialize three-mind system
```

## Configuration

```python
# Environment variables (User preferences applied)
AILY_DIKIWI_ENABLED=true
AILY_INNOVATION_ENABLED=true
AILY_ENTREPRENEUR_ENABLED=true

# Session times: Innovation 8am, Entrepreneur 9am
AILY_INNOVATION_TIME=08:00
AILY_ENTREPRENEUR_TIME=09:00

# High volume proposal generation
AILY_PROPOSAL_MIN_CONFIDENCE=0.5
AILY_PROPOSAL_MAX_PER_SESSION=10

# Notifications
AILY_NOTIFY_ON_PROPOSAL=true
```

## Implementation Sequence

| Phase | Week | Focus | Deliverables |
|-------|------|-------|--------------|
| 1 | Week 1 | Foundation | DIKIWI Mind, atomic notes, stage tracking |
| 2 | Week 2 | Innovation Mind | Daily 9am sessions, TRIZ, innovation proposals |
| 3 | Week 3 | Entrepreneur Mind | Daily 10am sessions, GStack, business proposals |
| 4 | Week 4 | Integration | Notifications, config, testing |

## Key Design Decisions

1. **DIKIWI Mind is default**: Every input flows through DIKIWI pipeline first
2. **Scheduled sessions**: Innovation (8am) / Entrepreneur (9am) minds run daily
3. **Proposal-driven output**: Both specialized minds generate structured proposals
4. **Integration with existing gating**: Hydrological system preserved, enhanced with minds
5. **Stage promotion**: All stages auto-promote when conditions are met
6. **High volume proposals**: 50% confidence threshold, max 10 per session
