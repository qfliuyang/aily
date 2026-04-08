# Aily

> **Your Personal Knowledge Curator**
>
> Aily transforms scattered information into structured knowledge, then engages you in conversation like a thoughtful master—surfacing connections, testing recall, and exciting your memory at exactly the right moments.

---

## What Aily Does

Aily is not a bookmarking tool. It is a **knowledge companion** that:

1. **Captures** — You send links, voice memos, or thoughts via Feishu
2. **Structures** — Breaks content into atomic knowledge cards with connections
3. **Surfaces** — Proactively messages you when ideas collide or patterns emerge
4. **Excites** — Tests your memory at scientifically optimal intervals
5. **Compounds** — Every capture enriches your growing knowledge network

---

## The Experience

You send a link to Aily on Feishu. An hour later, it messages you:

> *"Saved your article on transformers. Interesting—it contradicts your note on RNNs from March. Want me to create a comparison card?"*

Three days later:

> *"Quick recall: Can you explain 'attention mechanisms' without looking at your notes?"*

A week later:

> *"Three ideas you captured this week form a pattern around 'emergent behavior in LLMs.' I've created a hub note."*

---

## Why Aily Is Different

| Traditional Tools | Aily |
|-------------------|------|
| Passive storage | Active conversation |
| You organize | Aily suggests connections |
| You remember to review | Aily excites memory at optimal times |
| Dead archives | Living knowledge that compounds |
| Filing cabinets | A master who knows what you know |

---

## How It Works

```
Feishu Message (URL/voice/text)
        ↓
   [Aily Core]
        ↓
  ┌─────┴─────┬──────────┬──────────┐
  ▼           ▼          ▼          ▼
Browser    Parser    Atomicizer   Graph
Fetcher    Registry  (1 idea =    Engine
           (Kimi,    1 note)      (entities,
           Monica,                collisions)
           arXiv...)
  └─────┬─────┴──────────┴──────────┘
        ↓
   Obsidian Drafts
        ↓
   (You move to vault)
        ↓
   Learning Loop
        ↓
   Spaced Repetition
   Active Recall
   Insight Generation
        ↓
   Feishu Conversations
```

---

## Brain-Aligned Design

Aily mirrors how your brain actually forms memories:

| Phase | Brain Science | Aily Implementation |
|-------|---------------|---------------------|
| **Encoding** | Hippocampus converts experience to neural patterns | Atomic notes (one idea = one card) |
| **Elaboration** | Connect new info to existing schemas | Connection suggester links related notes |
| **Consolidation** | Spaced reactivation during sleep | SRS with Ebbinghaus intervals (1d→3d→7d→21d→60d) |
| **Retrieval** | Testing strengthens memory traces | Active recall questions via Feishu |
| **Error Correction** | Checking sources builds accuracy | Claim verification against original URLs |

---

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
# Edit .env with your Feishu app credentials, Obsidian API key, LLM API key

# 3. Start Aily
python -m aily.main
```

### Prerequisites

- **Feishu Bot**: Create at [open.feishu.cn](https://open.feishu.cn/app), get App ID and Secret
- **Obsidian**: Install [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin
- **LLM**: OpenAI API key or compatible endpoint

---

## Configuration

```bash
# Required
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
OBSIDIAN_VAULT_PATH=/Users/you/Documents/Vault
OBSIDIAN_REST_API_KEY=your-key
LLM_API_KEY=sk-...

# Optional
FEISHU_VOICE_ENABLED=true
AILY_DIGEST_HOUR=9
AILY_DIGEST_MINUTE=0
TAVILY_API_KEY=tvly-...  # For AI search
```

---

## Usage

### Send a Link

In Feishu, message Aily:
```
https://arxiv.org/abs/1706.03762
```

Aily responds:
```
Saved to Obsidian: Aily/Daily/2026-04-08 - Attention Is All You Need.md

I found 3 connections to your existing notes. Move to vault to activate.
```

### Voice Memo

Send a voice message. Aily transcribes with Whisper and creates a note.

### Ask Questions

```
Aily, how does this relate to my notes on RNNs?
```

Aily searches your knowledge graph and responds with connections.

---

## Architecture

See full details in [`docs/ARCHITECTURE_AND_VISION.md`](docs/ARCHITECTURE_AND_VISION.md).

Key components:

- **Feishu WebSocket** — Bidirectional chat without public URLs
- **Browser Fetcher** — Subprocess worker for authenticated content
- **Atomicizer** — Single-idea note generator
- **GraphDB** — Entity graph with collision detection
- **SRS** — Spaced repetition scheduler
- **Learning Loop** — Vault watcher that responds to your edits

---

## The Vision

> *"Knowledge should compound. Memory should strengthen. Learning should feel like conversation with a master who knows exactly what you need to hear, exactly when you need to hear it."*

Aily's ultimate goal is to be a **presence** in your intellectual life—not a tool you use, but a companion that:

- Remembers what you've forgotten
- Surfaces patterns you haven't seen
- Challenges your understanding at the edge of your competence
- Celebrates the growth of your knowledge network

---

## Research Foundation

Aily is grounded in cognitive science:

- **Memory Formation**: Hippocampal encoding and consolidation
- **Spaced Repetition**: Ebbinghaus forgetting curve
- **Active Recall**: Testing effect (Roediger & Karpicke)
- **Elaborative Encoding**: Schema theory and connection-building
- **Zettelkasten**: Luhmann's slip-box method

See [`docs/brain-knowledge-research.md`](docs/brain-knowledge-research.md) for full research.

---

## License

MIT

---

Built for those who believe knowledge should live, breathe, and grow.
