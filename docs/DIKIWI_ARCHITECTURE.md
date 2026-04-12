# DIKIWI Architecture Design & Implementation

**Version:** 2.0.0
**Last Updated:** 2026-04-10
**Status:** Mixed - current runtime plus experimental event-driven design

---

## 1. Overview

DIKIWI is a multi-agent knowledge processing system inspired by the Tang Dynasty's 三省六部 (Three Departments and Six Ministries) governance structure. It transforms raw data into actionable impact through six hierarchical stages, with institutional review gates ensuring quality at critical transitions.

> **Implementation Status**:
> - **`aily/sessions/dikiwi_mind.py`** — Simpler LLM-first pipeline (currently used in production)
> - **`aily/dikiwi/`** — Event-driven architecture with gates, skills, memorials (kept as experimental reference)
>
> This document covers DIKIWI concepts and the event-driven design that still exists in the repo. See `dikiwi_mind.py` for the current production implementation.

### 1.1 Core Philosophy

- **Hard Rails, Soft Power**: Enforced stage transitions (permission matrix) with autonomous agents within stages
- **Institutional Review**: Veto power at quality gates (封驳 - feng bo mechanism)
- **Human-in-the-Loop**: CVO (Chief Vision Officer) approval for high-impact decisions
- **Audit Trail**: Complete memorialization (奏折) of all decisions
- **Event-Driven**: Async coordination via EventBus with lineage tracking

### 1.2 DIKIWI Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                        DIKIWI HIERARCHY                         │
├─────────────────────────────────────────────────────────────────┤
│  DATA                                                            │
│   ↓                                                              │
│  INFORMATION ← 中书省 (Zhongshu) - Planning/Classification       │
│   ↓ [门下省 gate: can reject]                                    │
│  KNOWLEDGE ← 门下省 (Menxia) - Review/Veto (封驳)               │
│   ↓                                                              │
│  INSIGHT ← 尚书省 (Shangshu) - Dispatch/Pattern Detection       │
│   ↓ [CVO gate: human approval]                                   │
│  WISDOM ← 吏部 (Libu) - Quality/Grading                         │
│   ↓ [TTL auto-approve]                                           │
│  IMPACT ← 工部 (Gongbu) - Execution/Output                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Three-Layer Architecture

### 2.1 Layer Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  MODEL LAYER         - Reasoning (DIKIWI stage logic)               │
│  - Stage implementations (Zhongshu, Menxia, Shangshu, Libu, Gongbu) │
│  - Skill execution                                                   │
├─────────────────────────────────────────────────────────────────────┤
│  TOOL LAYER          - Capabilities (Skills, GraphDB, LLM)          │
│  - Skill registry and on-demand loading                              │
│  - LLM client for reasoning                                          │
│  - GraphDB for knowledge storage                                     │
├─────────────────────────────────────────────────────────────────────┤
│  PLATFORM LAYER      - Coordination (Orchestrator, Event Bus)       │
│  - EventBus for async communication                                  │
│  - State machine for transition enforcement                          │
│  - Gate scheduling and memorial creation                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Responsibilities

**Model Layer (aily/dikiwi/stages.py)**
- Defines DIKIWI stages (DATA through IMPACT)
- Implements stage transition logic
- Permission matrix enforcement

**Tool Layer (aily/dikiwi/skills/)**
- Skill base class (`Skill`)
- Skill registry for on-demand loading
- Built-in skills (tag extraction, pattern detection, synthesis)

**Platform Layer (aily/dikiwi/orchestrator.py)**
- `DikiwiOrchestrator` coordinates the pipeline
- Event handler registration
- Gate scheduling (Menxia, CVO)
- Memorial creation

---

## 3. Event-Driven Architecture

### 3.1 Event Types

```python
# Stage lifecycle events
StageCompletedEvent      # Stage finished, trigger next step
StageRejectedEvent       # 封驳 - content rejected at gate
ContentPromotedEvent     # Content advanced to next stage

# Content discovery events
InsightDiscoveredEvent   # Pattern detected
WisdomSynthesizedEvent   # Principles extracted
ImpactGeneratedEvent     # Actionable output created

# Gate and audit events
GateDecisionEvent        # Menxia/CVO decision
MemorialCreatedEvent     # Audit trail entry
```

### 3.2 Event Flow

```
Content Submitted
       ↓
StageCompletedEvent(DATA)
       ↓
[Zhongshu processes] → INFORMATION
       ↓
StageCompletedEvent(INFORMATION)
       ↓
GateDecisionEvent(menxia, pending)
       ↓
[Menxia review]
       ↓
├─ Reject → StageRejectedEvent → Back to INFORMATION
│
└─ Approve → ContentPromotedEvent → KNOWLEDGE
              ↓
        StageCompletedEvent(KNOWLEDGE)
              ↓
        [Shangshu processes] → INSIGHT
              ↓
        StageCompletedEvent(INSIGHT)
              ↓
        GateDecisionEvent(cvo, pending)
              ↓
        [CVO review with TTL]
              ↓
        ├─ Reject → Back to INSIGHT
        │
        └─ Approve/Auto → WISDOM → IMPACT
```

### 3.3 Correlation IDs

Every event includes a `correlation_id` enabling:
- Full lineage tracking from input to impact
- Debugging across async boundaries
- Audit trail reconstruction

```python
# Example: Tracing a content item
correlation_id = "abc123"
# DATA:abc123 → INFORMATION:abc123 → KNOWLEDGE:abc123 → ...
```

---

## 4. Stage State Machine

### 4.1 Permission Matrix

```python
PERMISSION_MATRIX: dict[DikiwiStage, list[DikiwiStage]] = {
    DikiwiStage.DATA: [DikiwiStage.INFORMATION],
    DikiwiStage.INFORMATION: [DikiwiStage.KNOWLEDGE],
    DikiwiStage.KNOWLEDGE: [
        DikiwiStage.INSIGHT,
        DikiwiStage.INFORMATION,  # Rejection loop
    ],
    DikiwiStage.INSIGHT: [DikiwiStage.WISDOM],
    DikiwiStage.WISDOM: [
        DikiwiStage.IMPACT,
        DikiwiStage.INSIGHT,  # CVO rejection
    ],
    DikiwiStage.IMPACT: [],  # Terminal
}
```

### 4.2 Stage Transitions

Valid transitions are enforced at the code level. Invalid transitions raise errors.

**Normal Flow:**
```
DATA → INFORMATION → KNOWLEDGE → INSIGHT → WISDOM → IMPACT
```

**Rejection Loops (封驳):**
```
KNOWLEDGE → INFORMATION  # Menxia rejection
WISDOM → INSIGHT         # CVO rejection
```

### 4.3 Stage Context

```python
@dataclass
class StageContext:
    context_id: str              # Unique ID for this journey
    correlation_id: str          # Links all related events
    content_id: str              # Original content
    current_stage: DikiwiStage   # Where we are now
    stage_state: StageState      # PENDING/PROCESSING/AWAITING_REVIEW/etc
    stage_history: list[dict]    # Complete audit trail
    rejection_count: dict        # Track rejections per stage
```

---

## 5. Skills System

### 5.1 Skill Interface

```python
class Skill(ABC):
    name: str = "base_skill"
    description: str = "Base skill class"
    version: str = "1.0.0"
    target_stages: list[str] = []
    content_types: list[str] = ["*"]

    requires_llm: bool = True
    requires_graph_db: bool = False

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        pass
```

### 5.2 Skill Registry

Skills are loaded on-demand based on stage and content type:

```python
# Mapping: (stage, content_type) -> [skill_names]
SKILL_MAP = {
    ("information", "tech_content"): [
        "tag_extraction",
        "tech_classification",
        "code_clustering",
    ],
    ("insight", "tech_content"): [
        "pattern_detection",
        "contradiction_analysis",
        "code_pattern_skill",
    ],
    ("wisdom", "tech_content"): [
        "synthesis",
        "framework_generation",
    ],
}
```

### 5.3 Content Type Classification

```python
async def classify_content_type(self, content: str) -> str:
    """Lightweight classification without LLM."""
    tech_indicators = ["code", "api", "database", "python", "github"]
    business_indicators = ["revenue", "customer", "market", "strategy"]

    tech_score = sum(1 for ind in tech_indicators if ind in content.lower())
    business_score = sum(1 for ind in business_indicators if ind in content.lower())

    if tech_score > business_score and tech_score > 1:
        return "tech_content"
    elif business_score > tech_score and business_score > 1:
        return "business_content"
    return "general"
```

### 5.4 Built-in Skills

| Skill | Stage | Purpose |
|-------|-------|---------|
| `TagExtractionSkill` | INFORMATION | Extract domain/topic/entity tags |
| `PatternDetectionSkill` | INSIGHT | Find patterns in knowledge network |
| `SynthesisSkill` | WISDOM | Combine insights into principles |

---

## 6. Institutional Gates

### 6.1 门下省 (Menxia) Gate

**Location:** INFORMATION → KNOWLEDGE transition
**Power:** Can reject (封驳) content, sending it back for re-processing

```python
class MenxiaGate:
    async def review(self, content: str, metadata: dict) -> ReviewDecision:
        quality_score = await self.assess_quality(content, metadata)

        if quality_score < self.rejection_threshold:
            return ReviewDecision(
                decision=ReviewDecisionType.REJECT,  # 封驳
                reason="Quality below threshold",
                send_back_to=DikiwiStage.INFORMATION,
            )

        return ReviewDecision(decision=ReviewDecisionType.APPROVE)
```

**Quality Criteria:**
1. Clarity - Is the content understandable?
2. Usefulness - Does it contain actionable information?
3. Accuracy - Is it factually sound?
4. Completeness - Is it self-contained?

### 6.2 CVO (Chief Vision Officer) Gate

**Location:** WISDOM → IMPACT transition
**Power:** Human approval required, with TTL auto-approval

```python
class CVOGate:
    DEFAULT_TTL_HOURS = 24

    async def await_approval(self, approval_id: str) -> ApprovalDecision:
        # Queue for human review
        pending = await self.request_approval(...)

        # Wait for human response or TTL
        while True:
            if pending.is_expired():
                return ApprovalDecision(
                    decision=ApprovalDecisionType.AUTO_APPROVED,
                    reasoning=f"Auto-approved after TTL ({self.ttl_hours}h)",
                )

            decision = await self._check_human_decision(approval_id)
            if decision:
                return decision

            await asyncio.sleep(check_interval)
```

**Human Role:**
- Express vision at high-impact gates
- Make decisions on proposals
- Shape culture through feedback
- Optional intervention (system runs autonomously if absent)

---

## 7. Memorials (奏折)

### 7.1 Memorial Structure

```python
@dataclass(frozen=True)
class Memorial:
    memorial_id: str          # Unique identifier
    correlation_id: str       # Links to input lineage
    pipeline_id: str          # Which pipeline
    stage: str                # Which stage
    decision: MemorialDecisionType  # PROMOTED/REJECTED/etc
    input_hash: str           # Content verification
    output_hash: str          # Output verification
    reasoning: str            # Why this decision
    agent_id: str             # Which agent decided
    gate_name: str            # menxia/cvo if applicable
    timestamp: datetime       # When it happened
    metadata: dict            # Additional context
```

### 7.2 Dual Storage

**GraphDB (Machine):**
- Fast queries
- Structured relationships
- Full lineage tracking

**Obsidian (Human):**
- Markdown format
- Git versioned
- Human readable
- Organized by month: `Memorials/2024-01/{id}.md`

### 7.3 Memorial Markdown Format

```markdown
# Memorial: mem-abc123

## Metadata
- **Pipeline**: `pipe-xyz789`
- **Correlation**: `corr-def456`
- **Stage**: KNOWLEDGE
- **Decision**: PROMOTED
- **Gate**: menxia
- **Timestamp**: 2024-01-15T08:30:00Z
- **Agent**: `menxia-agent-1`

## Verification
- **Input Hash**: `a1b2c3d4e5f6...`
- **Output Hash**: `f6e5d4c3b2a1...`

## Reasoning
Content passed quality review with score 0.82. Tags appropriate,
classification accurate. Approved for knowledge network entry.

## Additional Data

```json
{"quality_score": 0.82, "review_duration_ms": 1250}
```
```

---

## 8. Orchestrator

### 8.1 Responsibilities

The `DikiwiOrchestrator` (Platform Layer) handles:
- Event bus coordination
- Stage state machine enforcement
- Gate review scheduling
- Memorial creation
- Metrics collection

It does NOT:
- Content classification (Model Layer)
- Pattern detection (Model Layer)
- Wisdom synthesis (Model Layer)
- LLM calls (Tool Layer)
- GraphDB operations (Tool Layer)

### 8.2 Event Handlers

```python
def _setup_event_handlers(self) -> None:
    self.event_bus.subscribe(StageCompletedEvent, self._on_stage_completed)
    self.event_bus.subscribe(StageRejectedEvent, self._on_stage_rejected)
    self.event_bus.subscribe(ContentPromotedEvent, self._on_content_promoted)
    self.event_bus.subscribe(GateDecisionEvent, self._on_gate_decision)
```

### 8.3 Stage Completion Handler

```python
async def _on_stage_completed(self, event: StageCompletedEvent) -> None:
    if event.stage == DikiwiStage.INFORMATION:
        # Schedule 门下省 review
        await self._schedule_menxia_review(pipeline, event)

    elif event.stage == DikiwiStage.KNOWLEDGE:
        # Auto-promote to INSIGHT
        await self._promote_to_stage(pipeline, DikiwiStage.INSIGHT)

    elif event.stage == DikiwiStage.INSIGHT:
        # Schedule CVO review
        await self._schedule_cvo_review(pipeline, event)
```

### 8.4 CVO TTL Timer

```python
async def _cvo_ttl_timer(self, pipeline, content_ids) -> None:
    await asyncio.sleep(self.config.cvo_ttl_hours * 3600)

    if pipeline.status == "running" and \
       pipeline.context.current_stage == DikiwiStage.INSIGHT:

        await self.event_bus.publish(
            GateDecisionEvent(
                correlation_id=pipeline.correlation_id,
                gate_name="cvo",
                decision="approve",
                content_ids=content_ids,
                reasoning=f"Auto-approved after TTL",
            )
        )
```

---

## 9. Configuration

### 9.1 PipelineConfig

```python
@dataclass
class PipelineConfig:
    # Quality gates
    menxia_quality_threshold: float = 0.6
    cvo_ttl_hours: int = 24

    # Retry limits
    max_rejections: int = 3

    # Skills
    enable_skills: bool = True
    skill_timeout_seconds: int = 30

    # Memorials
    enable_memorials: bool = True

    # Gate decisions
    require_cvo_for_impact: bool = True
```

### 9.2 Usage Example

```python
from aily.dikiwi import DikiwiOrchestrator, PipelineConfig

# Configure
config = PipelineConfig(
    menxia_quality_threshold=0.7,  # Stricter review
    cvo_ttl_hours=48,               # Longer human window
    max_rejections=5,               # More retries
)

# Initialize
orchestrator = DikiwiOrchestrator(
    llm_client=llm_client,
    graph_db=graph_db,
    config=config,
)

# Start pipeline
pipeline = await orchestrator.start_pipeline(
    content_id="content-123",
    source="voice",
)

# Check metrics
metrics = orchestrator.get_metrics()
# {
#     "pipelines_started": 10,
#     "pipelines_completed": 8,
#     "pipelines_failed": 1,
#     "stage_rejections": 3,
#     "memorials_created": 45,
#     "active_pipelines": 1
# }
```

---

## 10. Production Implementation

### Current Production Code (`aily/sessions/dikiwi_mind.py`)

The production DIKIWI implementation uses a simpler LLM-first design:

```python
class DikiwiMind:
    """LLM-Powered Knowledge filtration and refinement pipeline."""

    async def process_input(self, drop: RainDrop) -> DikiwiResult:
        # Direct LLM-based stage progression
        # No EventBus overhead for single-user scale
        # Conversation memory across stages
        pass
```

**Differences from Full Architecture:**

| Aspect | Production (dikiwi_mind.py) | Full Architecture (aily/dikiwi/) |
|--------|---------------------------|----------------------------------|
| Coordination | Direct method calls | EventBus |
| Gates | Implicit in LLM prompts | Explicit Menxia/CVO gates |
| Skills | LLM handles all reasoning | Registry-loaded skills |
| Memorials | Basic logging | Full dual-storage (GraphDB + Obsidian) |
| Scale | Single-user optimized | Multi-user capable |

**When to use full architecture:**
- Multi-user deployments
- Need institutional audit trails
- Require explicit gate veto power
- Complex skill orchestration

### 10.1 Migration from v1

### 10.2 v1 vs v2 Comparison

| Aspect | v1 (Sequential) | v2 (Event-Driven) |
|--------|-----------------|-------------------|
| Architecture | Direct method calls | EventBus coordination |
| Gates | No review | 门下省 + CVO |
| Skills | Baked-in | On-demand loading |
| Audit | Obsidian outputs | Memorials (dual storage) |
| Human | Not involved | CVO approval |
| Extensibility | Hard | Easy via skills/events |

### 10.2 Migration Path

1. **Shadow Mode**: Run v2 alongside v1, compare outputs
2. **Menxia First**: Enable review at INFORMATION → KNOWLEDGE only
3. **Full Cutover**: Switch to v2 once memorials prove audit trail

---

## 11. Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Stage rejection rate | < 10% | `stage_rejections / pipelines_started` |
| Memorial coverage | 100% | All decisions archived |
| Human engagement | 50%+ | CVO response within 24h |
| Pipeline latency | < 2x | Compared to v1 despite overhead |

---

## 12. File Reference

```
aily/dikiwi/
├── __init__.py              # Package exports
├── stages.py                # Stage definitions, state machine
├── orchestrator.py          # Platform coordination
│
├── events/
│   ├── __init__.py
│   ├── models.py            # Event dataclasses
│   └── bus.py               # EventBus implementation
│
├── skills/
│   ├── __init__.py
│   ├── base.py              # Skill interface
│   ├── registry.py          # Skill loading
│   └── builtin/
│       ├── tag_extraction.py
│       ├── pattern_detection.py
│       └── synthesis.py
│
├── gates/
│   ├── __init__.py
│   ├── menxia.py            # 门下省 review gate
│   └── cvo.py               # CVO approval gate
│
└── memorials/
    ├── __init__.py
    ├── models.py            # Memorial dataclasses
    └── storage.py           # GraphDB + Obsidian storage
```

---

## 13. References

- **Clowder AI**: Hard rails + soft power, skill framework
- **Edict**: 三省六部 governance, institutional review
- **gstack**: Sequential sprints with quality gates
- **MCP**: Semantic tools, streaming context
- **Tang Dynasty**: Historical governance model inspiration

---

*DIKIWI: From Data to Impact, with wisdom.*
