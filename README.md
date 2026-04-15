# Aily

> **Your Three-Mind Knowledge System**
>
> Aily transforms scattered information into structured knowledge through three specialized minds: a **DIKIWI Mind** for continuous knowledge processing, an **Innovation Mind** for daily insight generation, and an **Entrepreneur Mind** for business opportunity detection.

---

## What Aily Does

Aily is not a bookmarking tool. It is a **knowledge system** with three autonomous minds:

### 1. DIKIWI Mind (Continuous)
**Processes every input** through a 6-stage pipeline (Data → Information → Knowledge → Insight → Wisdom → Impact)

- Drop files into `~/aily_chaos/` — PDFs, videos, images, text
- Automatic content extraction and structuring
- Atomic Zettelkasten notes written to Obsidian
- Knowledge graph with bidirectional linking
- **MAC Loop**: After each pipeline, Innolaval and Hanlin iterate twice to synthesize framework proposals into formal reports

### 2. Innolaval — Innovation Mind (Per-pipeline + Daily @ 8am)
**Generates innovation proposals** from your accumulated knowledge

- 8 methodologies running in parallel: TRIZ, SIT, Six Hats, Blue Ocean, SCAMPER, Biomimicry, Morphological, First Principles
- Wide input → focused synthesis through the "Laval nozzle"
- Runs inside the DIKIWI MAC loop after every input, plus a full daily session
- Proposals written to `Obsidian/20-Innovation/`

### 3. Entrepreneur Mind (Daily @ 9am)
**Evaluates business potential** using GStack framework

- PMF (Product-Market Fit) analysis
- Growth loop identification
- Market sizing and competitive analysis
- Business proposals written to `Obsidian/30-Business/`

---

## The Experience

### Continuous Knowledge Processing

You drop a PDF into `~/aily_chaos/`:

```
[DIKIWI Mind processing...]
↓
6-Stage Pipeline Complete
↓
MAC Loop (×2 rounds):
├── Round 1: Innolaval (TRIZ, SIT, Blue Ocean...) → Hanlin synthesis
└── Round 2: Innolaval (refined with Hanlin feedback) → Hanlin final report
↓
Saved to Obsidian:
├── 10-Knowledge/concepts/attention-mechanisms.md
├── 10-Knowledge/concepts/transformer-architecture.md
├── 10-Knowledge/sources/attention-is-all-you-need.md
└── 10-Knowledge/Hanlin Reports/2026-04-15 - Attention Mechanisms Report.md
```

### Daily Innovation Session (8am)

Feishu notification:
> *"Innolaval generated 5 proposals from yesterday's knowledge:*
> *• TRIZ: Contradiction detected between 'model size' and 'inference speed' — proposed solution: mixture-of-experts*
> *• Blue Ocean: Untapped market identified in edge AI deployment*
> *View all in Obsidian/20-Innovation/2026-04-12/"*

### Daily Business Evaluation (9am)

Feishu notification:
> *"Entrepreneur Mind evaluated 3 ideas:*
> *• GStack Score: 72/100 — Strong PMF potential in developer tools*
> *• Growth loop identified: API usage → Community content → New developers*
> *View full analysis in Obsidian/30-Business/"*

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT LAYER                                     │
│  Chaos Folder │ URLs │ Voice │ Feishu Chat │ Sessions                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│    DIKIWI MIND (Continuous) — 6-Stage Pipeline + MAC Loop                   │
│                                                                              │
│  Data → Information → Knowledge → Insight → Wisdom → Impact                  │
│       │                                                                       │
│       ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  MAC Loop (×2 rounds)                                                  ││
│  │  Round 1: Innolaval multiply → Hanlin accumulate (dry-run)             ││
│  │  Round 2: Innolaval multiply → Hanlin accumulate (persist)             ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│   INNOLAVAL          │  │   ENTREPRENEUR       │  │  MEMORY EXCITATION   │
│ (Daily @ 8am)        │  │ (Daily @ 9am)        │  │ (Continuous)         │
│                      │  │                      │  │                      │
│ • 8 Methods Parallel │  │ • GStack Analysis    │  │ • SRS scheduling     │
│ • TRIZ/SIT/etc       │  │ • PMF Evaluation     │  │ • Active recall      │
│ • Laval Synthesis    │  │ • Growth Loops       │  │ • Feishu nudges      │
└──────────┬───────────┘  └──────────┬───────────┘  └──────────┬───────────┘
           │                         │                         │
           └─────────────────────────┼─────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OBSIDIAN VAULT OUTPUT                                │
│                                                                              │
│  00-Inbox/          Raw captures, temporary notes                            │
│  10-Knowledge/      Zettelkasten notes (concepts, sources)                   │
│  20-Innovation/     Innovation proposals (TRIZ, SIT, etc.)                   │
│  30-Business/       Business analyses (GStack, market)                       │
│  90-Published/      Curated content for Obsidian Publish                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

Current architecture note:
- Active runtime docs live in [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md), [`docs/ARCHITECTURE_AND_VISION.md`](docs/ARCHITECTURE_AND_VISION.md), [`docs/AILY_CHAOS_ARCHITECTURE.md`](docs/AILY_CHAOS_ARCHITECTURE.md), and [`docs/DIKIWI_ARCHITECTURE.md`](docs/DIKIWI_ARCHITECTURE.md).
- Historical plans and review notes live under `docs/archive/`.

## Quick Start

```bash
# 1. Clone and setup
git clone <repo>
cd aily
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys (Zhipu AI for LLM, Feishu for notifications)

# 3. Start the Chaos Daemon (file watcher)
./scripts/setup_daemon.sh
# Or manually: python scripts/run_chaos_daemon.py start

# 4. Start Aily core (WebSocket, schedulers)
python -m aily.main
```

### Prerequisites

- **Zhipu AI API Key**: Get at [bigmodel.cn](https://bigmodel.cn) — used for DIKIWI processing
- **Feishu Bot** (optional): For notifications — create at [open.feishu.cn](https://open.feishu.cn/app)
- **Obsidian**: With Local REST API plugin enabled

---

## Configuration

```bash
# Required
ZHIPU_API_KEY=your-key          # For DIKIWI LLM processing
OBSIDIAN_VAULT_PATH=/Users/you/Documents/Obsidian Vault

# Optional
FEISHU_APP_ID=cli_xxx           # For notifications
FEISHU_APP_SECRET=xxx
AILY_INNOVATION_TIME=08:00      # Innolaval schedule
AILY_ENTREPRENEUR_TIME=09:00    # Entrepreneur schedule
```

---

## Usage

### File Processing (DIKIWI Mind)

Drop files into `~/aily_chaos/`:
```bash
# PDFs, videos, images, text files — all automatically processed
cp ~/Downloads/paper.pdf ~/aily_chaos/
cp ~/Downloads/lecture.mp4 ~/aily_chaos/
```

Check status:
```bash
python scripts/run_chaos_daemon.py status
```

### Manual URL Processing

In Feishu, message Aily:
```
https://arxiv.org/abs/1706.03762
```

Aily responds:
```
[DIKIWI Mind] Processing...
Saved to Obsidian: 10-Knowledge/sources/2026-04-12-attention-is-all-you-need.md
Extracted 12 concepts, 5 linked to existing notes.
```

### Innovation & Business Sessions

Automatic daily at configured times. Manual trigger:
```bash
# Run Innolaval now
python -c "from aily.sessions.innolaval_scheduler import InnolavalScheduler; ..."
```

---

## The Three Minds Explained

### DIKIWI Mind: Knowledge Filtration

The DIKIWI pipeline transforms raw data into actionable impact:

| Stage | Purpose | Output |
|-------|---------|--------|
| **D**ata | Raw input extraction | Text, transcripts, metadata |
| **I**nformation | Structure & classify | Tagged entities, topics |
| **K**nowledge | Atomic ideas | Zettelkasten cards |
| **I**nsight | Pattern detection | Connections, contradictions |
| **W**isdom | Synthesis | Principles, frameworks |
| **I**mpact | Actionable output | Proposals, decisions |
| **MAC** | Innolaval ↔ Hanlin loop | Refined proposals + formal report |

**Implementation:** `aily/sessions/dikiwi_mind.py`

### Innolaval: Innovation Laval Nozzle

Named after the Laval nozzle (convergent-divergent) — wide inputs from 8 innovation methods, focused synthesis into high-quality proposals.

**Methods:**
- **TRIZ**: Contradiction analysis, 40 inventive principles
- **SIT**: Systematic inventive thinking
- **Six Hats**: Parallel thinking perspectives
- **Blue Ocean**: Value innovation, strategy canvas
- **SCAMPER**: Substitute, Combine, Adapt, Modify, Put to other uses, Eliminate, Reverse
- **Biomimicry**: Nature-inspired solutions
- **Morphological**: Matrix-based combination
- **First Principles**: Physics-style reasoning

**Implementation:** `aily/sessions/innolaval_scheduler.py`

### Hanlin Agent (翰林): Vault Synthesis

Synthesizes DIKIWI vault outputs, knowledge graph, and Innolaval framework proposals into formal reports.

- Vault topology scan via `obsidian-cli`
- GraphDB query for recent DIKIWI nodes
- LLM synthesis with Innolaval proposals as context
- Persists `hanlin_proposal` nodes to GraphDB for downstream business evaluation

**Implementation:** `aily/dikiwi/agents/hanlin_agent.py`

### Entrepreneur Mind: Business Evaluation

Evaluates ideas through the GStack framework:
- **G**oal clarity
- **S**trategy viability
- **T**actics feasibility
- **A**ssets available
- **C**onstants (constraints)
- **K**ey metrics

**Implementation:** `aily/sessions/entrepreneur_scheduler.py`

---

## File Organization

```
aily/
├── main.py                      # FastAPI app, lifespan management
├── config.py                    # Settings
│
├── chaos/                       # Multimodal ingestion
│   ├── queue_processor.py       # SQLite queue
│   ├── processors/              # PDF, Video, Image, Text
│   └── dikiwi_bridge.py         # Chaos → DIKIWI
│
├── sessions/                    # Three-Mind System
│   ├── dikiwi_mind.py           # Continuous knowledge pipeline + MAC loop
│   ├── innolaval_scheduler.py   # Innovation mind (per-pipeline + daily 8am)
│   ├── entrepreneur_scheduler.py # Business mind (daily 9am)
│   ├── gstack_agent.py          # GStack business analysis executor
│   └── base.py                  # Shared scheduler infrastructure
│
├── dikiwi/                      # DIKIWI v2 agents + Hanlin
│   ├── agents/                  # Stage agents + post-pipeline analyst
│   │   ├── data_agent.py
│   │   ├── information_agent.py
│   │   ├── knowledge_agent.py
│   │   ├── insight_agent.py
│   │   ├── wisdom_agent.py
│   │   ├── impact_agent.py
│   │   └── hanlin_agent.py      # Vault scholar (翰林)
│   ├── orchestrator.py          # Event-driven coordination
│   ├── gates/                   # Menxia review, CVO approval
│   ├── skills/                  # Tag extraction, pattern detection
│   └── memorials/               # Audit trail
│
├── writer/                      # Output
│   ├── dikiwi_obsidian.py       # Zettelkasten writer
│   └── obsidian.py              # REST API client
│
└── scripts/
    └── run_chaos_daemon.py      # Production file watcher
```

---

## Documentation

- [`docs/ARCHITECTURE_AND_VISION.md`](docs/ARCHITECTURE_AND_VISION.md) — Core philosophy and brain-aligned design
- [`docs/DIKIWI_ARCHITECTURE.md`](docs/DIKIWI_ARCHITECTURE.md) — DIKIWI v2 detailed architecture
- [`docs/AILY_CHAOS_ARCHITECTURE.md`](docs/AILY_CHAOS_ARCHITECTURE.md) — Multimodal ingestion system
- [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) — Current runtime and doc map
- [`docs/brain-knowledge-research.md`](docs/brain-knowledge-research.md) — Cognitive science foundation

---

## Evolution

| Version | Focus | Key Features |
|---------|-------|--------------|
| v0.1.0 | Foundation | Feishu webhook, URL → Obsidian pipeline |
| v0.2.0 | Brain-Aligned | Atomic notes, SRS, entity graph |
| v0.3.0 | Bidirectional | WebSocket, conversational memory |
| v0.4.0 | Three Minds | DIKIWI, Innolaval, Entrepreneur, Chaos Daemon |
| **v0.5.0** | **MAC Architecture** | **Innolaval-Hanlin multiply-accumulate loop, agentic business gates** |

---

## License

MIT

---

Built for those who believe knowledge should live, breathe, and compound.
