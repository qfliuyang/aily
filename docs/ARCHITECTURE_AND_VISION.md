# Aily: Architecture and Vision

> **Aily turns information into structured knowledge cards in Obsidian, then excites your memory via Feishu conversations — like chatting with a real master or guru.**

---

## Vision

Aily is not just a link-saving bot. It is a **knowledge curator** that transforms scattered information into a living, connected second brain — then actively engages you in conversation to strengthen memory formation.

### The Knowledge Cycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INFORMATION INGEST                           │
│     (URLs, Voice Memos, Thoughts, AI Chats, Papers, Videos)         │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STRUCTURE & CONNECT                            │
│   • Atomic notes (one idea per card)                                 │
│   • Bidirectional links between related concepts                     │
│   • Knowledge graph with collision detection                         │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     MEMORY EXCITATION (Feishu)                       │
│   • "This connects to your note on X — interesting tension?"         │
│   • "Time to review: Can you explain [concept] without looking?"    │
│   • "3 ideas you captured this week form a pattern..."              │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ACTIVE RECALL & GROWTH                          │
│   • Spaced repetition at optimal intervals                           │
│   • Verification of claims against sources                           │
│   • Accumulating queries that feed back into knowledge base          │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Philosophy

1. **Raw → Compiled**: Like the brain's sensory memory → consolidated long-term memory, Aily separates messy captures from structured knowledge
2. **Elaborative Encoding**: New ideas must connect to existing knowledge to become permanent
3. **Active Recall**: Testing memory strengthens it more than re-reading
4. **Conversational**: Knowledge should feel like dialogue with a wise mentor, not filing cabinets

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FEISHU (IM)                                │
│              • WebSocket long connection (bidirectional)             │
│              • Message receipt and response                          │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         AILY CORE ENGINE                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Parser    │  │   Queue     │  │   Worker    │  │  Scheduler  │ │
│  │   Registry  │  │    (SQLite) │  │             │  │             │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
│         │                │                │                │        │
│  ┌──────▼────────────────▼────────────────▼────────────────▼──────┐ │
│  │                    Job Dispatcher                              │ │
│  │         (url_fetch | daily_digest | voice | claude_session)    │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
           ┌────────────┐  ┌────────────┐  ┌────────────┐
           │  Browser   │  │   Graph    │  │  Learning  │
           │  Fetcher   │  │    DB      │  │    Loop    │
           └────────────┘  └────────────┘  └────────────┘
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │      OBSIDIAN VAULT          │
                    │  ┌────────┐    ┌────────┐   │
                    │  │ Drafts │ →  │  Wiki  │   │
                    │  │ (raw)  │    │(compiled)│ │
                    │  └────────┘    └────────┘   │
                    └──────────────────────────────┘
```

### Key Components

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
├── main.py              # FastAPI app, lifespan management
├── config.py            # Settings (pydantic-settings)
├── bot/
│   ├── ws_client.py     # Feishu WebSocket (bidirectional)
│   └── webhook.py       # HTTP webhook (fallback)
├── queue/
│   ├── db.py            # SQLite job queue
│   └── worker.py        # Job processor
├── browser/
│   ├── fetcher.py       # Browser interface
│   ├── manager.py       # BrowserUseManager (subprocess)
│   └── agent_worker.py  # Subprocess worker for Browser Use
├── parser/
│   ├── registry.py      # URL pattern → parser
│   └── parsers.py       # Kimi, Monica, arXiv, etc.
├── graph/
│   └── db.py            # Entity graph (SQLite)
├── processing/
│   └── atomicizer.py    # Single-idea note generator
├── learning/
│   ├── loop.py          # Vault watcher for user edits
│   ├── srs.py           # Spaced repetition scheduler
│   └── recall.py        # Active recall question generator
├── digest/
│   └── pipeline.py      # Daily digest + verification
├── agent/
│   ├── registry.py      # Agent registration
│   ├── agents.py        # Summarizer, researcher, etc.
│   └── pipeline.py      # Planner pipeline
├── writer/
│   └── obsidian.py      # Obsidian REST API client
├── push/
│   └── feishu.py        # Feishu message sender
├── search/
│   └── tavily.py        # Tavily AI search
├── verify/
│   └── verifier.py      # Claim verification
├── voice/
│   ├── downloader.py    # Feishu voice file download
│   └── transcriber.py   # Whisper transcription
├── capture/
│   └── claude_code.py   # Claude Code session capture
├── llm/
│   └── client.py        # LLM client (OpenAI-compatible)
├── scheduler/
│   └── jobs.py          # Cron schedulers
└── network/
    └── tailscale.py     # Tailscale integration
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
| Future | Guru Mode | Accumulating queries, self-updating knowledge base, insight generation |

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
