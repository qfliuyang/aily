# Aily: Architecture and Vision

> **Aily turns information into structured knowledge cards in Obsidian, then excites your memory via Feishu conversations — like chatting with a real master or guru.**

---

## Vision

Aily is not just a link-saving bot. It is a **Three-Mind Knowledge System** that transforms scattered information into structured knowledge through three specialized minds:

1. **DIKIWI Mind** (Continuous) — Processes every input through a 6-stage pipeline into atomic Zettelkasten notes
2. **Innolaval** (Daily @ 8am) — 8 innovation methodologies running in parallel to generate insight proposals
3. **Entrepreneur Mind** (Daily @ 9am) — GStack business analysis to evaluate opportunities

Then actively engages you in conversation to strengthen memory formation.

### The Knowledge Cycle (Three-Mind System)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INFORMATION INGEST                           │
│   (Chaos Folder, URLs, Voice Memos, Thoughts, AI Chats, Videos)     │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DIKIWI MIND (Continuous)                        │
│   • 6-Stage Pipeline (Data→Information→Knowledge→Insight→Wisdom→Impact)│
│   • Atomic notes (one idea per card)                                 │
│   • Bidirectional links between related concepts                     │
│   • Knowledge graph with collision detection                         │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│   INNOLAVAL       │  │   ENTREPRENEUR    │  │  MEMORY EXCITATION │
│   (Daily @ 8am)   │  │   (Daily @ 9am)   │  │  (Continuous)      │
│                   │  │                   │  │                    │
│ • TRIZ Analysis   │  │ • GStack Eval     │  │ • SRS scheduling   │
│ • SIT/SCAMPER/etc │  │ • PMF Analysis    │  │ • Active recall    │
│ • Innovation      │  │ • Growth loops    │  │ • Feishu nudges    │
│   Proposals       │  │ • Business        │  │ • Pattern alerts   │
│                   │  │   Proposals       │  │                    │
└─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      OBSIDIAN VAULT OUTPUT                           │
│   10-Knowledge/  20-Innovation/  30-Business/  90-Published/        │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Philosophy

1. **Raw → Compiled**: Like the brain's sensory memory → consolidated long-term memory, Aily separates messy captures from structured knowledge
2. **Elaborative Encoding**: New ideas must connect to existing knowledge to become permanent
3. **Active Recall**: Testing memory strengthens it more than re-reading
4. **Conversational**: Knowledge should feel like dialogue with a wise mentor, not filing cabinets

---

## Architecture

### System Overview (Three-Mind Architecture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                           INPUT LAYER                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │    Chaos    │  │   Feishu    │  │   Voice     │  │   Claude    │ │
│  │   Folder    │  │  WebSocket  │  │   Memos     │  │   Sessions  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
└─────────┼────────────────┼────────────────┼────────────────┼────────┘
          │                │                │                │
          └────────────────┴────────────────┴────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    THREE-MIND PROCESSING SYSTEM                      │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │   DIKIWI MIND    │  │   INNOLAVAL      │  │   ENTREPRENEUR   │   │
│  │  (Continuous)    │  │  (Daily @ 8am)   │  │  (Daily @ 9am)   │   │
│  │                  │  │                  │  │                  │   │
│  │ • 6-Stage Pipe   │  │ • 8 Methods      │  │ • GStack Eval    │   │
│  │ • Atomic Notes   │  │ • TRIZ/SIT/etc   │  │ • PMF Analysis   │   │
│  │ • GraphDB Links  │  │ • Synthesis      │  │ • Growth Loops   │   │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘   │
│           │                     │                     │             │
│           └─────────────────────┼─────────────────────┘             │
│                                 ▼                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              OBSIDIAN VAULT OUTPUT                            │  │
│  │  10-Knowledge/  20-Innovation/  30-Business/  90-Published/  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Components

### Runtime Status

- `aily/main.py` is the active app bootstrap.
- `aily/sessions/dikiwi_mind.py` is the active continuous DIKIWI runtime.
- `aily/sessions/innolaval_scheduler.py` is the active daily innovation runtime.
- `aily/sessions/entrepreneur_scheduler.py` is the active daily entrepreneur runtime.
- `aily/dikiwi/` and `aily/gating/` are kept as secondary or experimental architectures, not the primary runtime path.

#### 1. Input Layer (Feishu WebSocket)
- **File**: `aily/bot/ws_client.py`
- **Purpose**: Bidirectional chat with users via Feishu (Lark)
- **Mechanism**: WebSocket long connection — no public URL required
- **Features**:
  - Receive text messages with URLs
  - Receive voice messages (auto-transcribed)
  - Send knowledge nudges and recall prompts

#### 2. Processing Pipeline

**Parser Registry** (`aily/parser/registry.py`)
- URL pattern matching → specialized parser
- Support: Kimi, Monica, arXiv, GitHub, YouTube, Generic web

**Queue System** (`aily/queue/`)
- SQLite-backed job queue with deduplication
- Job types: `url_fetch`, `daily_digest`, `voice_message`, `claude_session`, `agent_request`

**Browser Fetcher** (`aily/browser/`)
- **Subprocess Worker**: Isolated Playwright/Browser Use for content extraction
- **Features**: Chrome profile support (authenticated pages), Chinese text handling

#### 3. Knowledge Layer

**GraphDB** (`aily/graph/db.py`)
- SQLite-based entity graph (nodes, edges, occurrences)
- Tracks: people, concepts, technologies, papers
- Collision detection across sources

**Atomicizer** (`aily/processing/atomicizer.py`)
- Breaks captures into single-idea atomic notes
- Mimics brain's encoding → elaboration process

**Spaced Repetition** (`aily/learning/srs.py`)
- Ebbinghaus intervals: 1d → 3d → 7d → 21d → 60d
- Schedules review for consolidation

**Active Recall** (`aily/learning/recall.py`)
- Generates questions from notes (factual, conceptual, application)
- Tests memory via Feishu messages

#### 4. Output Layer

**Obsidian Writer** (`aily/writer/obsidian.py`)
- REST API integration with Obsidian Local REST API plugin
- Draft folder staging → user moves to approve
- Frontmatter: `aily_generated`, `aily_source`, `aily_type`

**Digest Pipeline** (`aily/digest/pipeline.py`)
- Daily knowledge summaries
- Verification layer (claims checked against sources)
- Collision reports (insights from connected sources)

### Data Flow

```
User sends URL in Feishu
        │
        ▼
┌───────────────┐
│ WebSocket     │
│ receives msg  │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ URL extracted │
│ Job enqueued  │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Worker picks  │
│ up job        │
└───────┬───────┘
        │
        ▼
┌───────────────┐     ┌───────────────┐
│ Browser fetches│────→│ Content parsed │
│ page content  │     │ (service-aware)│
└───────┬───────┘     └───────────────┘
        │
        ▼
┌───────────────┐
│ Atomic notes  │
│ generated     │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Connections   │
│ suggested     │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Written to    │
│ Obsidian Draft│
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Feishu:       │
│ "Saved! Move  │
│  to vault to  │
│  activate."   │
└───────────────┘
```

---

## Brain-Aligned Design

Aily's architecture mirrors how the human brain forms permanent memories:

| Brain Phase | Neuroscience | Aily Implementation |
|-------------|--------------|---------------------|
| **Encoding** | Hippocampus converts experience to neural patterns | Atomic notes (one idea = one note) |
| **Elaboration** | Connect new info to existing schemas | Connection suggester links related notes |
| **Consolidation** | Spaced reactivation during sleep | SRS with Ebbinghaus intervals |
| **Retrieval** | Testing strengthens memory traces | Active recall questions via Feishu |
| **Error Correction** | Checking sources builds accuracy | Claim verification against original URLs |

---

## File Organization

```
aily/
├── main.py                      # FastAPI app, lifespan management
├── config.py                    # Settings (pydantic-settings)
│
├── sessions/                    # THREE-MIND SYSTEM
│   ├── dikiwi_mind.py           # Continuous knowledge pipeline (DIKIWI)
│   ├── innolaval_scheduler.py   # Innovation mind - 8 methods (Daily @ 8am)
│   ├── entrepreneur_scheduler.py        # Business mind (Daily @ 9am)
│   ├── base.py                  # BaseMind scheduler infrastructure
│   ├── models.py                # Session models
│   └── gstack_agent.py          # GStack business analysis
│
├── chaos/                       # MULTIMODAL INGESTION
│   ├── queue_processor.py       # SQLite persistent queue
│   ├── dikiwi_bridge.py         # Chaos → DIKIWI integration
│   ├── config.py                # Chaos processing configuration
│   ├── types.py                 # ExtractedContentMultimodal
│   ├── processor.py             # Main processor coordinator
│   ├── processors/              # File type processors
│   │   ├── pdf.py               # PDF text + visual extraction
│   │   ├── video.py             # Frame + transcript extraction
│   │   ├── image.py             # OCR + visual analysis
│   │   ├── document.py          # Generic document processor
│   │   ├── pptx.py              # PowerPoint extraction
│   │   └── base.py              # Processor base class
│   └── tagger/                  # Intelligent tagging
│       ├── engine.py
│       ├── content_based.py
│       └── llm_based.py
│
├── dikiwi/                      # Experimental DIKIWI architecture
│   ├── orchestrator.py          # Event-driven coordination
│   ├── stages.py                # Stage definitions
│   ├── gates/                   # Institutional review
│   │   ├── menxia.py            # 门下省 quality gate
│   │   └── cvo.py               # Chief Vision Officer gate
│   ├── skills/                  # Capability system
│   │   ├── registry.py          # Skill loading
│   │   ├── base.py              # Skill interface
│   │   └── builtin/             # Built-in skills
│   │       ├── tag_extraction.py
│   │       ├── pattern_detection.py
│   │       └── synthesis.py
│   ├── events/                  # Event-driven communication
│   │   ├── bus.py
│   │   └── models.py
│   └── memorials/               # Audit trail
│       ├── models.py
│       └── storage.py
│
├── writer/                      # OUTPUT
│   ├── dikiwi_obsidian.py       # Zettelkasten writer (Three-Mind)
│   └── obsidian.py              # Legacy Obsidian REST client
│
├── bot/                         # INPUT
│   ├── ws_client.py             # Feishu WebSocket
│   └── webhook.py               # HTTP fallback
│
├── queue/                       # LEGACY QUEUE
│   ├── db.py                    # SQLite job queue
│   └── worker.py                # Job processor
│
├── graph/                       # KNOWLEDGE GRAPH
│   └── db.py                    # Entity graph (SQLite)
│
├── learning/                    # MEMORY SYSTEM
│   ├── loop.py                  # Vault watcher
│   ├── srs.py                   # Spaced repetition
│   └── recall.py                # Active recall
│
├── browser/                     # WEB FETCHING
│   ├── fetcher.py               # Browser interface
│   ├── manager.py               # BrowserUse subprocess manager
│   └── agent_worker.py          # Subprocess worker
│
├── parser/                      # CONTENT PARSERS
│   ├── registry.py              # URL pattern → parser
│   └── parsers.py               # Kimi, Monica, arXiv, etc.
│
├── llm/                         # LLM CLIENTS
│   ├── client.py                # Main LLM client
│   ├── llm_router.py            # Multi-provider routing
│   ├── coding_plan_client.py    # Coding-specific LLM
│   └── kimi_client.py           # Kimi API client
│
├── scheduler/                   # CRON JOBS
│   └── jobs.py                  # Daily schedulers
│
└── scripts/
    └── run_chaos_daemon.py      # Production file watcher daemon
```

---

## Key Design Decisions

### 1. WebSocket over Webhook
- **Why**: WebSocket connects outbound to Feishu servers — no public URL or ngrok required
- **Benefit**: Works from local machine, personal use only

### 2. Draft Folder + Manual Approval
- **Why**: User moving a note from `Aily Drafts/` to vault signals "this is worth keeping"
- **Benefit**: Eliminates false positives in learning loop

### 3. Subprocess Browser
- **Why**: Playwright memory leaks + concurrent instances = OOM on personal Mac
- **Benefit**: Single subprocess queue, lifecycle managed, crash isolation

### 4. SQLite for Everything
- **Why**: Personal scale (10K nodes), zero external dependencies
- **Benefit**: Single file backup, no PostgreSQL to maintain

### 5. Raw vs Compiled Distinction
- **Why**: Brain separates sensory memory from consolidated long-term memory
- **Benefit**: Clean separation between messy captures and structured knowledge

---

## Configuration

Environment variables (`.env`):

```bash
# Feishu Bot
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
FEISHU_VOICE_ENABLED=true

# Obsidian
OBSIDIAN_VAULT_PATH=/Users/you/Documents/Vault
OBSIDIAN_REST_API_KEY=your-key
OBSIDIAN_REST_API_PORT=27123

# LLM
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Optional
TAVILY_API_KEY=tvly-...
WHISPER_API_KEY=sk-...
AILY_DIGEST_HOUR=9
AILY_DIGEST_MINUTE=0
```

---

## Evolution

Aily has evolved through several phases:

| Version | Focus | Key Features |
|---------|-------|--------------|
| v0.1.0 | Foundation | Feishu webhook, URL → Obsidian pipeline, basic parsers |
| v0.2.0 | Brain-Aligned | Atomic notes, SRS, active recall, entity graph, verification |
| v0.3.0 | Bidirectional | WebSocket client, conversational memory, proactive nudges |
| v0.4.0 | **Three-Mind System** | **Chaos ingestion, DIKIWI pipeline, Innolaval (8 methods), Entrepreneur mind** |

---

## Research Foundation

Aily's design is grounded in cognitive science research:

- **Memory Formation**: [Nature Communications - Consolidation](https://www.nature.com/subjects/consolidation/ncomms)
- **Spaced Repetition**: [Ebbinghaus Forgetting Curve](https://memoryos.com/article/the-ebbinghaus-forgetting-curve-and-how-to-hack-it)
- **Active Recall**: [Roediger & Karpicke (2006)](http://psychnet.wustl.edu/memory/wp-content/uploads/2018/04/Roediger-Karpicke-2006_PPS.pdf)
- **Zettelkasten Method**: [Obsibrain - Connected Second Brain](https://www.obsibrain.com/blog/zettelkasten-how-to-build-a-connected-second-brain-that-actually-grows-with-you)
- **Karpathy's LLM Knowledge Base**: [Twitter Thread](https://x.com/karpathy/status/2039805659525644595)

See full research: [`docs/brain-knowledge-research.md`](./brain-knowledge-research.md)

---

## The Ultimate Vision

> Aily becomes a **conversational knowledge companion** — not a tool you use, but a presence that understands what you know, what you're learning, and what you've forgotten.

When you send a link, Aily doesn't just save it. It:
1. Extracts atomic ideas
2. Connects them to your existing knowledge
3. Surfaces unexpected collisions
4. Tests your memory at optimal intervals
5. Engages you in dialogue like a thoughtful mentor

**Knowledge should compound. Memory should strengthen. Learning should feel like conversation.**
