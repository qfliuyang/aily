# Aily Gating Architecture: The Hydrological System

## Concept: Information as Water

```
Rain (inputs) → Streams (routing) → Reservoir (enrichment) → Dam (gating) → Rivers (outputs)
```

Your information flows like water through Aily. Only the strongest insights break through the dam.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           🌧️ RAIN (All Inputs)                                  │
│                                                                                 │
│  • Feishu messages          • Clipboard captures         • File uploads        │
│  • URLs                     • Voice messages             • Images (OCR)        │
│  • Claude sessions          • Manual inputs                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      🚰 DRAINAGE SYSTEM (aily/gating/drainage.py)               │
│                                                                                 │
│   Every drop enters here. No leaks. No bypass. All information is captured.    │
│                                                                                 │
│   Streams (by type):                                                            │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│   │ DIRECT      │  │ FETCH_      │  │ TRANSCRIBE_ │  │ EXTRACT_    │          │
│   │ Chat → fast │  │ ANALYZE     │  │ ANALYZE     │  │ ANALYZE     │          │
│   │ response    │  │ URL → fetch │  │ Voice → text│  │ Doc → text  │          │
│   └─────────────┘  │ → analyze   │  │ → analyze   │  │ → analyze   │          │
│                    └─────────────┘  └─────────────┘  └─────────────┘          │
│                                                                                 │
│   Intent Detection: Classifies rain type → routes to stream                     │
│   "analyze this URL" → FETCH_ANALYZE stream                                     │
│   "just save this"   → DIRECT stream (bypasses dam)                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      🌊 RESERVOIR (aily/gating/reservoir.py)                    │
│                                                                                 │
│   Content pools accumulate depth through enrichment:                            │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  Pool Formation: Multiple drops merge into pools                       │  │
│   │                                                                         │  │
│   │  Depth Metrics (what makes content "deep"):                            │  │
│   │  • Keywords extracted        • Entities identified                     │  │
│   │  • GraphDB connections       • Novelty score                           │  │
│   │  • Context nodes linked      • Cross-references found                  │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│   When pool.depth ≥ 1.0 → Forms a RIVER with momentum                          │
│                                                                                 │
│   Rivers have MOMENTUM = pool depth (0.0 to ∞)                                 │
│   Only rivers with momentum ≥ 0.5 can reach the dam                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         🚧 DAM (aily/gating/dam.py)                             │
│                                                                                 │
│   Four gates control breakthrough. All must pass for output.                    │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  GATE 1: CONFIDENCE (weight: 2.0x)                                     │  │
│   │  Result confidence ≥ 60%                                               │  │
│   │  └─→ ARMY analysis produces confidence score                           │  │
│   │                                                                         │  │
│   │  GATE 2: NOVELTY (weight: 1.0x)                                        │  │
│   │  Content novelty ≥ 30% (vs existing knowledge)                         │  │
│   │  └─→ Reservoir calculates novelty score                                │  │
│   │                                                                         │  │
│   │  GATE 3: IMPACT (weight: 1.5x)                                         │  │
│   │  Actionable insights with priority                                     │  │
│   │  └─→ Critical/High priority insights = higher impact                   │  │
│   │                                                                         │  │
│   │  GATE 4: SYNTHESIS (weight: 1.0x)                                      │  │
│   │  Must combine ≥2 framework perspectives                                │  │
│   │  └─→ TRIZ + McKinsey + GStack must all contribute                      │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│   BREAKTHROUGH FORCE = weighted_average(gate_scores)                           │
│   Required: ≥3 gates passed AND force ≥ 0.60                                   │
│                                                                                 │
│   🌊 BREAKTHROUGH! Content flows to output channels                            │
│   ✋ HELD BACK Content stays in reservoir for more enrichment                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      🏞️ RIVERS (Output Channels)                                │
│                                                                                 │
│   ┌──────────────────────────┐      ┌──────────────────────────┐               │
│   │   FEISHU CHANNEL         │      │   OBSIDIAN CHANNEL       │               │
│   │                          │      │                          │               │
│   │   • Immediate emoji ack  │      │   • Full markdown note   │               │
│   │   • Framework analysis   │      │   • YAML frontmatter     │               │
│   │   • Synthesized insights │      │   • All framework traces │               │
│   │   • Action items         │      │   • Action checklists    │               │
│   │                          │      │                          │               │
│   └──────────────────────────┘      └──────────────────────────┘               │
│                                                                                 │
│   Chain-of-custody: Every output traces back to input source                   │
│   Input ID → Drop ID → Pool ID → River ID → Breakthrough ID → Output           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Information Flow Examples

### Example 1: High-Quality URL Analysis

```
User sends: "analyze https://example.com/article"

🌧️ RAIN
   → URL detected with analysis keyword
   → Intent: THINKING_ANALYSIS

🚰 DRAINAGE
   → Stream: FETCH_ANALYZE
   → Enqueued for content fetching

🌊 RESERVOIR
   → Fetches article HTML
   → Parses content → markdown
   → Extracts keywords: ["startup", "growth", "PMF"]
   → Queries GraphDB for related nodes
   → Novelty score: 0.75 (new angle on known topic)
   → Pool depth: 1.2 → FORMS RIVER (momentum: 1.2)

🚧 DAM
   → ARMY analysis runs:
      • TRIZ: Finds contradiction (speed vs quality)
      • McKinsey: MECE structure of problem
      • GStack: PMF score 65/100, growth loop identified
   → Synthesizes 3 cross-framework insights
   → Confidence: 82%
   → Impact score: 0.78 (has action items)

   GATE CHECKS:
   ✓ Confidence: 0.82 ≥ 0.60
   ✓ Novelty: 0.75 ≥ 0.30
   ✓ Impact: 0.78 ≥ 0.50
   ✓ Synthesis: 3 frameworks used

   BREAKTHROUGH FORCE: 0.78
   🌊 BREAKTHROUGH! → Output channels

🏞️ OUTPUT
   → Feishu: Framework analysis + synthesized insights
   → Obsidian: Full note with all traces
```

### Example 2: Low-Quality Chat

```
User sends: "hi"

🌧️ RAIN
   → Intent: CHAT

🚰 DRAINAGE
   → Stream: DIRECT
   → Immediate response, bypasses dam

(No reservoir/dam - direct flow)
```

### Example 3: Weak Analysis (Held Back)

```
User sends: "analyze this: https://example.com/empty-page"

🌧️ RAIN → 🚰 DRAINAGE → 🌊 RESERVOIR
   → Fetches page
   → Content: "Under construction"
   → Pool depth: 0.3 (shallow)

🚧 DAM
   → ARMY analysis:
      • TRIZ: No contradictions found
      • McKinsey: No clear problem
      • GStack: No product data
   → Confidence: 35%
   → No actionable insights

   GATE CHECKS:
   ✗ Confidence: 0.35 < 0.60 (FAIL)
   ✓ Novelty: 0.50 ≥ 0.30
   ✗ Impact: 0.10 < 0.50 (FAIL)
   ✗ Synthesis: Only 1 framework useful (FAIL)

   Gates passed: 1/4
   ✋ HELD BACK → Stays in reservoir for enrichment
      (or user notified: "Not enough substance for analysis")
```

## Data Structure Chain

```
RainDrop (input)
    ↓
ContentPool (accumulation)
    ↓
River (formed flow)
    ↓
ThinkingResult (ARMY analysis)
    ↓
DamBreakthrough (gated output)
    ↓
Output delivery (Feishu/Obsidian)
```

Each stage maintains references to previous stages for full traceability.

## Configuration

```python
# Gate thresholds (tunable)
confidence_threshold = 0.60  # 60% confidence required
novelty_threshold = 0.30     # 30% novelty required
impact_threshold = 0.50      # 50% impact required

# Reservoir settings
enrichment_interval = 5      # seconds between enrichment cycles
flow_rate = 10               # drops per batch

# Stream routing
StreamType.DIRECT.flow_rate = 1        # Immediate
StreamType.FETCH_ANALYZE.flow_rate = 1 # Per URL
StreamType.BATCH_DIGEST.flow_rate = 50 # Daily digest batch
```

## Benefits of This Architecture

1. **No Information Loss**: All inputs captured in drainage
2. **Quality Control**: Only high-impact content breaks dam
3. **Traceability**: Full chain from input → output
4. **Flexibility**: Different streams for different content types
5. **Extensibility**: New gates/channels can be added
6. **Observability**: Stats at every stage

## Implementation Status

| Component | Status | File |
|-----------|--------|------|
| DrainageSystem | ✅ Implemented | `aily/gating/drainage.py` |
| ContentReservoir | ✅ Implemented | `aily/gating/reservoir.py` |
| InsightDam | ✅ Implemented | `aily/gating/dam.py` |
| InputChannels | ✅ Implemented | `aily/gating/channels.py` |
| OutputChannels | ✅ Implemented | `aily/gating/channels.py` |
| Integration with main.py | 🔄 Pending | - |

## Next Steps

1. Wire gating system into main.py
2. Replace existing WebSocket handler with FeishuInputChannel
3. Connect reservoir to GraphDB
4. Add observability dashboard
5. Tune gate thresholds based on usage
