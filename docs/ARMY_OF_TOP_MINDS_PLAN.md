# ARMY OF TOP MINDS — Implementation Plan

**Plan ID:** autopilot-impl
**Created:** 2026-04-09
**Status:** Ready for Execution
**Estimated Duration:** 2-3 weeks
**Complexity:** HIGH

---

## 1. Executive Summary

This plan implements the **ARMY OF TOP MINDS** multi-agent thinking system for Aily — a parallel analysis framework combining TRIZ (inventive problem solving), McKinsey (structured business analysis), and GStack (product/startup methodology) to transform raw knowledge into compelling, insight-rich outputs.

### Key Deliverables
- 3 framework analyzers with LLM-powered analysis
- Synthesis engine for cross-framework insight merging
- Hypnosis-driven output formatter
- Full Aily integration (QueueDB, GraphDB, Obsidian, Feishu)
- Comprehensive test suite (unit, integration, e2e)

---

## 2. Current State Analysis

### Existing Aily Infrastructure (Available for Integration)

| Component | Status | Integration Point |
|-----------|--------|-------------------|
| `QueueDB` | Implemented | New job types: `thinking_analysis`, `thinking_quick`, `thinking_batch` |
| `GraphDB` | Implemented | New tables: `thinking_insights`, `framework_analyses`, `insight_relationships` |
| `LLMClient` | Implemented | Extend with `ThinkingLLMClient` wrapper for structured output |
| `AgentRegistry` | Implemented | Register 4 new agents: `triz_analyzer`, `mckinsey_analyzer`, `gstack_analyzer`, `thinking_orchestrator` |
| `ObsidianWriter` | Implemented | New output folder: `Aily Drafts/Thinking/` |
| `FeishuPusher` | Implemented | Summary delivery with confidence scores |
| `JobWorker` | Implemented | Extend processor to handle thinking job types |

### Configuration Extensions Needed
- `ThinkingConfig` class with framework enablement flags
- Separate LLM config for thinking (higher quality model, lower temperature)
- Output formatting preferences

---

## 3. Task Breakdown

### Phase 1: Foundation (Week 1)

#### Task 1.1: Data Models & Configuration
**Files:**
- `aily/thinking/__init__.py`
- `aily/thinking/models.py`
- `aily/thinking/config.py`

**Implementation:**
```python
# Core enums
FrameworkType(Enum): TRIZ, MCKINSEY, GSTACK
InsightPriority(Enum): CRITICAL=4, HIGH=3, MEDIUM=2, LOW=1

# Dataclasses
KnowledgePayload, FrameworkInsight, SynthesizedInsight, ThinkingResult

# Pydantic models for LLM outputs
Contradiction, PrincipleRecommendation, EvolutionAnalysis
MeceStructure, HypothesisTree, FrameworkApplication
PMFAnalysis, ShippingAssessment, GrowthLoop
```

**Acceptance Criteria:**
- [ ] All models have proper type hints and validation
- [ ] Models serialize/deserialize correctly to JSON
- [ ] Config loads from environment with `AILY_THINKING_` prefix
- [ ] Unit tests for model validation

**Dependencies:** None
**Estimated Effort:** 1 day

---

#### Task 1.2: LLM Integration Layer
**Files:**
- `aily/thinking/integration/llm_integration.py`

**Implementation:**
```python
class ThinkingLLMClient:
    - __init__(base_client: LLMClient, config: dict)
    - analyze_with_schema(system_prompt, user_content, output_schema, temperature) -> T
    - handle validation errors with automatic retry (max 3)
    - use JSON mode for structured output
```

**Acceptance Criteria:**
- [ ] Wraps existing LLMClient with thinking-specific retry logic
- [ ] Validates LLM output against Pydantic schema
- [ ] Retries on validation failure with error context
- [ ] Unit tests with mocked LLM responses

**Dependencies:** Task 1.1
**Estimated Effort:** 1 day

---

#### Task 1.3: Framework Base Class
**Files:**
- `aily/thinking/frameworks/__init__.py`
- `aily/thinking/frameworks/base.py`

**Implementation:**
```python
class FrameworkAnalyzer(ABC):
    framework_type: FrameworkType

    __init__(llm_client: ThinkingLLMClient, config: dict | None)
    @abstractmethod analyze(payload: KnowledgePayload) -> FrameworkInsight
    @abstractmethod get_system_prompt() -> str
```

**Acceptance Criteria:**
- [ ] Abstract base class defines clear interface
- [ ] All framework analyzers can be instantiated polymorphically
- [ ] Unit tests for base class behavior

**Dependencies:** Task 1.1, Task 1.2
**Estimated Effort:** 0.5 day

---

### Phase 2: Framework Analyzers (Week 1-2)

#### Task 2.1: TRIZ Analyzer
**Files:**
- `aily/thinking/frameworks/triz.py`

**Implementation:**
```python
class TrizAnalyzer(FrameworkAnalyzer):
    framework_type = FrameworkType.TRIZ

    async def analyze(payload) -> FrameworkInsight:
        # 1. Detect contradictions (technical, physical, administrative)
        # 2. Match to 40 TRIZ principles
        # 3. Analyze evolution trends (S-curve position)
        # 4. Define Ideal Final Result (IFR)

    async def detect_contradictions(text: str) -> list[Contradiction]
    async def match_principles(contradictions) -> list[PrincipleRecommendation]
    async def analyze_evolution(text: str) -> EvolutionAnalysis
```

**System Prompt:** See spec section 7.1 (TRIZ System Prompt)

**Acceptance Criteria:**
- [ ] Detects at least 1 contradiction in test inputs
- [ ] Recommends valid TRIZ principles (1-40)
- [ ] Returns confidence score 0.0-1.0
- [ ] Unit tests with sample technical/business texts
- [ ] Integration test with real LLM

**Dependencies:** Task 1.3
**Estimated Effort:** 2 days

---

#### Task 2.2: McKinsey Analyzer
**Files:**
- `aily/thinking/frameworks/mckinsey.py`

**Implementation:**
```python
class McKinseyAnalyzer(FrameworkAnalyzer):
    framework_type = FrameworkType.MCKINSEY

    async def analyze(payload) -> FrameworkInsight:
        # 1. Build MECE structure
        # 2. Generate hypothesis tree
        # 3. Apply relevant business frameworks (7S, 3C, Porter 5 Forces, etc.)
        # 4. Prioritize issues by impact/effort

    async def build_mece_structure(problem: str) -> MeceStructure
    async def generate_hypothesis_tree(structure) -> HypothesisTree
    async def apply_framework(framework, context) -> FrameworkApplication
```

**System Prompt:** See spec section 7.2 (McKinsey System Prompt)

**Acceptance Criteria:**
- [ ] Creates valid MECE structure (no overlaps, exhaustive)
- [ ] Generates testable hypotheses
- [ ] Applies at least one business framework
- [ ] Unit tests with sample business cases
- [ ] Integration test with real LLM

**Dependencies:** Task 1.3
**Estimated Effort:** 2 days

---

#### Task 2.3: GStack Analyzer
**Files:**
- `aily/thinking/frameworks/gstack.py`

**Implementation:**
```python
class GStackAnalyzer(FrameworkAnalyzer):
    framework_type = FrameworkType.GSTACK

    async def analyze(payload) -> FrameworkInsight:
        # 1. Analyze product-market fit indicators
        # 2. Assess shipping discipline and velocity
        # 3. Identify growth loops (viral, paid, UGC, SEO)
        # 4. Evaluate AARRR metrics
        # 5. Generate actionable recommendations

    async def analyze_product_market_fit(text: str) -> PMFAnalysis
    async def assess_shipping_discipline(text: str) -> ShippingAssessment
    async def identify_growth_loops(text: str) -> list[GrowthLoop]
```

**System Prompt:** See spec section 7.3 (GStack System Prompt)

**Acceptance Criteria:**
- [ ] Scores PMF 0-100 with supporting signals
- [ ] Identifies at least one growth loop
- [ ] Provides prioritized action items
- [ ] Unit tests with sample startup/product texts
- [ ] Integration test with real LLM

**Dependencies:** Task 1.3
**Estimated Effort:** 2 days

---

### Phase 3: Synthesis Engine (Week 2)

#### Task 3.1: Conflict Resolution
**Files:**
- `aily/thinking/synthesis/__init__.py`
- `aily/thinking/synthesis/conflict.py`

**Implementation:**
```python
class ConflictResolver:
    def detect_conflicts(insights: list[SynthesizedInsight]) -> list[Conflict]
    def resolve_conflicts(conflicts: list[Conflict]) -> Resolution
    # Resolution strategies:
    # - Higher confidence wins
    # - Synthesize both perspectives
    # - Flag for human review
```

**Acceptance Criteria:**
- [ ] Detects when frameworks contradict each other
- [ ] Applies resolution strategies correctly
- [ ] Unit tests with artificial conflict scenarios

**Dependencies:** Task 2.1, Task 2.2, Task 2.3
**Estimated Effort:** 1 day

---

#### Task 3.2: Pattern Matching
**Files:**
- `aily/thinking/synthesis/pattern.py`

**Implementation:**
```python
class PatternMatcher:
    def find_reinforcing_patterns(insights: list[SynthesizedInsight]) -> list[Pattern]
    def calculate_cross_framework_confidence(insights) -> float
    # Pattern types:
    # - Convergent (all frameworks agree)
    # - Complementary (different aspects)
    # - Tension (conflicting but valid)
```

**Acceptance Criteria:**
- [ ] Identifies when multiple frameworks support same insight
- [ ] Scores confidence based on cross-framework agreement
- [ ] Unit tests with pattern scenarios

**Dependencies:** Task 2.1, Task 2.2, Task 2.3
**Estimated Effort:** 1 day

---

#### Task 3.3: Synthesis Engine
**Files:**
- `aily/thinking/synthesis/engine.py`

**Implementation:**
```python
class InsightSynthesizer:
    __init__(llm_client, conflict_resolver, pattern_matcher)

    async def synthesize(framework_insights, payload) -> list[SynthesizedInsight]:
        # 1. Normalize insights to common format
        # 2. Detect and resolve conflicts
        # 3. Identify reinforcing patterns
        # 4. Score confidence and rank by priority
        # 5. Generate unified recommendations

    async def resolve_conflicts(insights) -> list[SynthesizedInsight]
    def calculate_confidence(framework_insights, insight) -> float
```

**Acceptance Criteria:**
- [ ] Combines 3 framework outputs into unified insights
- [ ] Resolves conflicts between frameworks
- [ ] Ranks insights by confidence and priority
- [ ] Generates actionable recommendations
- [ ] Unit tests with mock framework outputs
- [ ] Integration test with real LLM

**Dependencies:** Task 3.1, Task 3.2
**Estimated Effort:** 2 days

---

### Phase 4: Output Formatter (Week 2)

#### Task 4.1: Persuasive Output Formatter
**Files:**
- `aily/thinking/output/__init__.py`
- `aily/thinking/output/formatter.py`

**Implementation:**
```python
class PersuasiveOutputFormatter:
    __init__(llm_client, style_config)

    async def format(insights, payload, format_type) -> FormattedOutput:
        # Apply hypnosis-driven formatting:
        # - Logical structure (premise -> evidence -> conclusion)
        # - Narrative arc (problem -> struggle -> insight -> resolution)
        # - Evidence weaving (data, examples, authority)
        # - Action catalyst (clear next steps)

    async def format_for_obsidian(result: ThinkingResult) -> str
    async def format_for_feishu(result: ThinkingResult) -> str
```

**Output Structure for Obsidian:**
```markdown
# Thinking Analysis - {timestamp}

## Executive Summary
{High-level synthesis}

## Key Insights (Confidence: {score})
1. **{Title}** ({priority}, {confidence}%)
   - {Description}
   - Evidence: {supporting points}

## Framework Perspectives
### TRIZ Perspective
{Contradictions, principles, evolution}

### McKinsey Perspective
{MECE structure, hypotheses, priorities}

### GStack Perspective
{PMF analysis, growth loops, recommendations}

## Synthesis & Recommendations
{Unified recommendations with cross-framework support}

## Action Items
- [ ] {Immediate action}
- [ ] {Short-term action}
- [ ] {Strategic action}
```

**Feishu Summary Format:**
```
Thinking Analysis Complete

Key Findings ({confidence}% confidence):
1. {Top insight}
2. {Second insight}
3. {Third insight}

Recommended Actions:
- {Top action item}

Full analysis saved to Obsidian: {path}
```

**Acceptance Criteria:**
- [ ] Generates properly formatted markdown for Obsidian
- [ ] Generates concise summary for Feishu (< 2000 chars)
- [ ] Includes confidence scores and priority levels
- [ ] Unit tests for formatting logic

**Dependencies:** Task 3.3
**Estimated Effort:** 2 days

---

### Phase 5: Orchestration Layer (Week 2-3)

#### Task 5.1: Thinking Orchestrator
**Files:**
- `aily/thinking/orchestrator.py`

**Implementation:**
```python
class ThinkingOrchestrator:
    __init__(graph_db, llm_client, registry, config)

    async def think(payload, options) -> ThinkingResult:
        # 1. Build context from GraphDB
        # 2. Launch 3 framework analyzers in parallel
        # 3. Run synthesis engine
        # 4. Format output
        # 5. Return ThinkingResult

    async def think_parallel(payloads) -> list[ThinkingResult]

    async def _build_context(payload) -> KnowledgePayload:
        # Fetch related nodes from GraphDB (last 24h, related topics)
        # Add context_nodes to payload
```

**Acceptance Criteria:**
- [ ] Executes full pipeline end-to-end
- [ ] Runs 3 frameworks in parallel (asyncio.gather)
- [ ] Completes within 10 seconds for typical inputs
- [ ] Handles errors gracefully with partial results
- [ ] Unit tests with mocked dependencies
- [ ] Integration test with real LLM

**Dependencies:** Task 2.1, Task 2.2, Task 2.3, Task 3.3, Task 4.1
**Estimated Effort:** 2 days

---

### Phase 6: Aily Integration (Week 3)

#### Task 6.1: GraphDB Extensions
**Files:**
- `aily/thinking/integration/graphdb_client.py`

**Implementation:**
```python
class ThinkingGraphClient:
    async def initialize_thinking_schema() -> None:
        # Create tables:
        # - thinking_insights
        # - framework_analyses
        # - insight_relationships

    async def store_insight(insight, request_id) -> None
    async def get_related_insights(node_id) -> list[dict]
    async def get_insight_history(hours=24) -> list[SynthesizedInsight]
```

**Acceptance Criteria:**
- [ ] Schema initializes correctly
- [ ] Insights stored with relationships to source nodes
- [ ] Can retrieve insights by time window
- [ ] Unit tests with in-memory SQLite

**Dependencies:** Task 5.1
**Estimated Effort:** 1 day

---

#### Task 6.2: Queue Integration
**Files:**
- `aily/thinking/integration/queue_integration.py`

**Implementation:**
```python
class ThinkingJobHandler:
    __init__(orchestrator, output_handler)

    async def handle_job(job) -> None:
        # Job types:
        # - "thinking_analysis": Full multi-framework analysis
        # - "thinking_quick": Fast single-framework analysis
        # - "thinking_batch": Batch process multiple items

    async def _handle_full_analysis(payload) -> None
    async def _handle_quick_analysis(payload) -> None
    async def _handle_batch_analysis(payload) -> None
```

**Acceptance Criteria:**
- [ ] Handles all 3 job types
- [ ] Enqueues to QueueDB with proper payload format
- [ ] Integrates with existing JobWorker
- [ ] Unit tests with mocked QueueDB

**Dependencies:** Task 5.1, Task 6.4
**Estimated Effort:** 1 day

---

#### Task 6.3: Agent Registration
**Files:**
- `aily/thinking/integration/agent_registration.py`

**Implementation:**
```python
async def register_thinking_agents(registry: AgentRegistry) -> None:
    # Register:
    # - triz_analyzer
    # - mckinsey_analyzer
    # - gstack_analyzer
    # - thinking_orchestrator

async def triz_agent_handler(context, text) -> str
async def mckinsey_agent_handler(context, text) -> str
async def gstack_agent_handler(context, text) -> str
async def orchestrator_agent_handler(context, text) -> str
```

**Acceptance Criteria:**
- [ ] All 4 agents registered with descriptions
- [ ] Handlers work with existing AgentRegistry
- [ ] Can be invoked via existing agent pipeline
- [ ] Unit tests for registration

**Dependencies:** Task 5.1
**Estimated Effort:** 0.5 day

---

#### Task 6.4: Output Integration
**Files:**
- `aily/thinking/integration/output_integration.py`

**Implementation:**
```python
class ThinkingOutputHandler:
    __init__(obsidian_writer, feishu_pusher)

    async def deliver(result, options) -> DeliveryResult:
        # Write full analysis to Obsidian (Aily Drafts/Thinking/)
        # Send summary to Feishu (if configured)

    async def _write_to_obsidian(result) -> str
    async def _send_to_feishu(result, open_id) -> bool
```

**Acceptance Criteria:**
- [ ] Writes to Obsidian with proper frontmatter
- [ ] Sends Feishu summary with key insights
- [ ] Handles delivery failures gracefully
- [ ] Unit tests with mocked writers

**Dependencies:** Task 4.1
**Estimated Effort:** 1 day

---

#### Task 6.5: Main Integration
**Files:**
- `aily/config.py` (extend)
- `aily/main.py` (extend)

**Implementation:**
```python
# In config.py - add to Settings:
thinking: ThinkingConfig = ThinkingConfig()

# In main.py:
# - Initialize ThinkingGraphClient
# - Register thinking agents
# - Add thinking job handler to worker
```

**Acceptance Criteria:**
- [ ] Config loads thinking settings from env
- [ ] Thinking system initializes on startup
- [ ] Job worker processes thinking jobs
- [ ] E2E test: full flow from webhook to output

**Dependencies:** Task 6.1, Task 6.2, Task 6.3, Task 6.4
**Estimated Effort:** 1 day

---

### Phase 7: Testing (Week 3)

#### Task 7.1: Unit Tests
**Files:**
- `tests/thinking/test_models.py`
- `tests/thinking/test_triz.py`
- `tests/thinking/test_mckinsey.py`
- `tests/thinking/test_gstack.py`
- `tests/thinking/test_synthesis.py`
- `tests/thinking/test_formatter.py`
- `tests/thinking/test_orchestrator.py`

**Test Coverage Requirements:**
- [ ] All models validate correctly
- [ ] Each framework analyzer produces valid output
- [ ] Synthesis engine resolves conflicts
- [ ] Formatter generates correct markdown
- [ ] Orchestrator coordinates parallel execution

**Dependencies:** All implementation tasks
**Estimated Effort:** 2 days

---

#### Task 7.2: Integration Tests
**Files:**
- `tests/thinking/integration/test_llm_integration.py`
- `tests/thinking/integration/test_graphdb_integration.py`
- `tests/thinking/integration/test_queue_integration.py`

**Test Coverage Requirements:**
- [ ] LLM client retries on validation failure
- [ ] GraphDB stores and retrieves insights
- [ ] Queue handler processes thinking jobs
- [ ] Full pipeline with mocked external services

**Dependencies:** Task 7.1
**Estimated Effort:** 1 day

---

#### Task 7.3: E2E Tests
**Files:**
- `tests/thinking/test_e2e_thinking.py`

**Test Scenarios:**
- [ ] Feishu URL -> Thinking analysis -> Obsidian note + Feishu summary
- [ ] Batch analysis of multiple URLs
- [ ] Error handling: LLM timeout, invalid input
- [ ] Performance: Analysis completes within 10 seconds

**Dependencies:** Task 7.2
**Estimated Effort:** 1 day

---

## 4. Dependencies & Execution Order

```
Phase 1: Foundation
├── Task 1.1: Data Models & Config (START)
├── Task 1.2: LLM Integration Layer (depends: 1.1)
└── Task 1.3: Framework Base Class (depends: 1.1, 1.2)

Phase 2: Framework Analyzers (PARALLEL after Phase 1)
├── Task 2.1: TRIZ Analyzer (depends: 1.3) ──┐
├── Task 2.2: McKinsey Analyzer (depends: 1.3) ├─► All 3 can run in parallel
└── Task 2.3: GStack Analyzer (depends: 1.3) ──┘

Phase 3: Synthesis Engine
├── Task 3.1: Conflict Resolution (depends: 2.1, 2.2, 2.3)
├── Task 3.2: Pattern Matching (depends: 2.1, 2.2, 2.3)
└── Task 3.3: Synthesis Engine (depends: 3.1, 3.2)

Phase 4: Output (depends: 3.3)
└── Task 4.1: Persuasive Output Formatter

Phase 5: Orchestration (depends: 2.x, 3.3, 4.1)
└── Task 5.1: Thinking Orchestrator

Phase 6: Integration (PARALLEL after Phase 5)
├── Task 6.1: GraphDB Extensions (depends: 5.1)
├── Task 6.2: Queue Integration (depends: 5.1, 6.4)
├── Task 6.3: Agent Registration (depends: 5.1)
├── Task 6.4: Output Integration (depends: 4.1)
└── Task 6.5: Main Integration (depends: 6.1, 6.2, 6.3, 6.4)

Phase 7: Testing
├── Task 7.1: Unit Tests (depends: all impl)
├── Task 7.2: Integration Tests (depends: 7.1)
└── Task 7.3: E2E Tests (depends: 7.2)
```

---

## 5. Parallelization Opportunities

### Can Run in Parallel

1. **Phase 2: Framework Analyzers**
   - TRIZ, McKinsey, GStack analyzers are independent
   - Each needs base class (Task 1.3) completed
   - Parallel execution saves ~4 days

2. **Phase 6: Integration Tasks**
   - GraphDB Extensions (6.1)
   - Agent Registration (6.3)
   - Output Integration (6.4)
   - All depend on orchestrator but not each other
   - Parallel execution saves ~2 days

3. **Testing Tasks**
   - Unit tests for each component can be written as components complete
   - Integration tests need all components

### Must Run Sequentially

1. Synthesis Engine (3.3) needs all 3 analyzers
2. Output Formatter (4.1) needs synthesis
3. Orchestrator (5.1) needs all previous
4. Main Integration (6.5) needs all integration tasks

---

## 6. File Structure

```
aily/
├── thinking/
│   ├── __init__.py
│   ├── models.py                    # Task 1.1
│   ├── config.py                    # Task 1.1
│   ├── orchestrator.py              # Task 5.1
│   ├── frameworks/
│   │   ├── __init__.py
│   │   ├── base.py                  # Task 1.3
│   │   ├── triz.py                  # Task 2.1
│   │   ├── mckinsey.py              # Task 2.2
│   │   └── gstack.py                # Task 2.3
│   ├── synthesis/
│   │   ├── __init__.py
│   │   ├── engine.py                # Task 3.3
│   │   ├── conflict.py              # Task 3.1
│   │   └── pattern.py               # Task 3.2
│   ├── output/
│   │   ├── __init__.py
│   │   └── formatter.py             # Task 4.1
│   └── integration/
│       ├── __init__.py
│       ├── llm_integration.py       # Task 1.2
│       ├── graphdb_client.py        # Task 6.1
│       ├── queue_integration.py     # Task 6.2
│       ├── agent_registration.py    # Task 6.3
│       └── output_integration.py    # Task 6.4
├── config.py                        # Task 6.5 (extend)
├── main.py                          # Task 6.5 (extend)
└── ...

tests/
├── thinking/
│   ├── __init__.py
│   ├── test_models.py               # Task 7.1
│   ├── test_triz.py                 # Task 7.1
│   ├── test_mckinsey.py             # Task 7.1
│   ├── test_gstack.py               # Task 7.1
│   ├── test_synthesis.py            # Task 7.1
│   ├── test_formatter.py            # Task 7.1
│   ├── test_orchestrator.py         # Task 7.1
│   └── integration/
│       ├── __init__.py
│       ├── test_llm_integration.py  # Task 7.2
│       ├── test_graphdb_integration.py  # Task 7.2
│       ├── test_queue_integration.py    # Task 7.2
│       └── test_e2e_thinking.py     # Task 7.3
└── ...
```

---

## 7. Test Strategy

### Unit Tests (Task 7.1)

| Component | Test File | Coverage Target |
|-----------|-----------|-----------------|
| Models | `test_models.py` | 100% validation paths |
| TRIZ | `test_triz.py` | Contradiction detection, principle matching |
| McKinsey | `test_mckinsey.py` | MECE structure, hypothesis generation |
| GStack | `test_gstack.py` | PMF analysis, growth loop identification |
| Synthesis | `test_synthesis.py` | Conflict resolution, pattern matching |
| Formatter | `test_formatter.py` | Markdown generation, Feishu summary |
| Orchestrator | `test_orchestrator.py` | Parallel execution, error handling |

### Integration Tests (Task 7.2)

| Integration | Test File | Test Scenario |
|-------------|-----------|---------------|
| LLM | `test_llm_integration.py` | Retry logic, validation, JSON repair |
| GraphDB | `test_graphdb_integration.py` | Schema init, insight storage, retrieval |
| Queue | `test_queue_integration.py` | Job handling, payload parsing |

### E2E Tests (Task 7.3)

| Scenario | Test File | Success Criteria |
|----------|-----------|------------------|
| Full Flow | `test_e2e_thinking.py` | URL -> Analysis -> Obsidian + Feishu |
| Batch | `test_e2e_thinking.py` | Multiple URLs processed |
| Error Recovery | `test_e2e_thinking.py` | Graceful degradation on LLM timeout |
| Performance | `test_e2e_thinking.py` | < 10s for typical input |

### Validation Criteria

1. **Functional:** All 3 frameworks produce valid insights
2. **Integration:** Synthesis correctly resolves conflicts
3. **Output:** Delivered to both Obsidian and Feishu
4. **Performance:** Analysis completes within 10 seconds
5. **Quality:** Insight relevance > 80% (user rating 4+/5)

---

## 8. Risk Mitigation

### Open Questions from Requirements

| Question | Risk Level | Mitigation Strategy |
|----------|------------|---------------------|
| LLM output schema validation | HIGH | Implement `ThinkingLLMClient` with automatic retry on validation failure. Use Pydantic for strict validation. Add `json_repair` fallback. |
| Framework contradiction detection | MEDIUM | Start with simple string similarity for conflict detection. Iterate based on real outputs. |
| Confidence scoring accuracy | MEDIUM | Use cross-framework agreement as primary signal. Allow manual override via config. |
| Performance with parallel LLM calls | MEDIUM | Use `asyncio.gather` for parallel execution. Add timeout handling (5s per framework). |
| Prompt engineering quality | HIGH | Include example outputs in system prompts. A/B test different prompt versions. |

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM rate limiting | Medium | High | Implement exponential backoff in `ThinkingLLMClient`. Cache similar analyses. |
| LLM output inconsistency | High | Medium | Lower temperature (0.3). Add validation retry loop. Use JSON mode. |
| SQLite concurrency issues | Low | Medium | Use WAL mode. Single-writer is acceptable for single-user system. |
| Framework analyzer timeout | Medium | Medium | 5s timeout per framework. Return partial results if one fails. |

### Fallback Strategies

```python
# In ThinkingOrchestrator.think_with_fallback()
async def think_with_fallback(payload):
    try:
        # Try full parallel analysis
        return await self.think(payload)
    except TimeoutError:
        # Fall back to single framework (McKinsey - most general)
        logger.warning("Timeout, falling back to McKinsey only")
        return await self.think_single_framework(payload, FrameworkType.MCKINSEY)
    except LLMError as e:
        # Return error result with actionable message
        return self._create_error_result(payload, str(e))
```

---

## 9. Configuration Reference

### Environment Variables

```bash
# Framework enablement
AILY_THINKING_TRIZ_ENABLED=true
AILY_THINKING_MCKINSEY_ENABLED=true
AILY_THINKING_GSTACK_ENABLED=true

# Analysis settings
AILY_THINKING_MIN_CONFIDENCE_THRESHOLD=0.6
AILY_THINKING_MAX_INSIGHTS_PER_ANALYSIS=10
AILY_THINKING_PARALLEL_ANALYSIS=true

# LLM settings (override base LLM for thinking)
AILY_THINKING_LLM_MODEL=gpt-4o
AILY_THINKING_TEMPERATURE=0.3
AILY_THINKING_MAX_TOKENS=4000

# Output settings
AILY_THINKING_OBSIDIAN_FOLDER="Aily Drafts/Thinking"
AILY_THINKING_FEISHU_MAX_LENGTH=2000
AILY_THINKING_INCLUDE_FRAMEWORK_DETAILS=true

# Storage settings
AILY_THINKING_STORE_INSIGHTS=true
AILY_THINKING_INSIGHT_RETENTION_DAYS=90
```

---

## 10. Success Criteria

### Functional Requirements

- [ ] All three frameworks produce valid insights
- [ ] Synthesis correctly resolves conflicts between frameworks
- [ ] Output is delivered to both Obsidian and Feishu
- [ ] Analysis completes within 10 seconds
- [ ] System handles errors gracefully with partial results

### Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Insight relevance | >80% | User rating 4+ / 5 |
| Framework accuracy | >90% | Expert review of sample outputs |
| Output clarity | >85% | User comprehension test |
| System availability | >99% | Uptime monitoring |
| Test coverage | >80% | pytest-cov report |

### Completion Checklist

- [ ] All 21 tasks completed
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] E2E tests passing
- [ ] Documentation updated
- [ ] Code review completed
- [ ] Performance benchmarks met

---

## 11. Appendix

### A. LLM Prompt Templates

See spec file `.omc/autopilot/army_of_top_minds_spec.md` sections 7.1-7.3 for complete system prompts:
- TRIZ System Prompt (lines 1258-1323)
- McKinsey System Prompt (lines 1325-1393)
- GStack System Prompt (lines 1395-1470)

### B. TRIZ 40 Principles Reference

See spec file `.omc/autopilot/army_of_top_minds_spec.md` section 12.1 (lines 1613-1654)

### C. McKinsey Frameworks Reference

See spec file `.omc/autopilot/army_of_top_minds_spec.md` section 12.2 (lines 1656-1662)

### D. GStack Metrics Reference

See spec file `.omc/autopilot/army_of_top_minds_spec.md` section 12.3 (lines 1664-1668)

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | 5 scope proposals, 5 accepted, 0 deferred, 3 critical gaps |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 3 | issues_open | 10 issues, 1 critical gap |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**UNRESOLVED:** 0 decisions
**VERDICT:** Eng Review issues_open — 10 issues found, all accepted. 1 critical gap (output escaping/truncation tests). Ready to implement with recorded fixes.

### Accepted Fixes Summary

| Issue | Task | Fix |
|-------|------|-----|
| 1A | 5.1 | `asyncio.gather(return_exceptions=True)` for partial failure handling |
| 1B | 1.2 | Use Instructor library for LLM validation/retry |
| 1C | 3.3 | Design synthesizer for N frameworks (1-3) |
| 2A | 2.1-2.3 | Centralize LLM calls in base class |
| 2B | 3.1-3.3 | Start conflict/pattern as functions, extract if needed |
| 2C | All | Add structured logging with correlation IDs |
| 3A | 7.1 | Add regression test for partial framework failure |
| 3B | 2.1-2.3 | Add LLM quality eval tests |
| 4A | 5.1 | Specify batched GraphDB query |
| 4B | 2.1-2.3 | Add content hash caching (1-hour TTL) |

### Critical Gap
- **Output escaping/truncation:** Add tests for special character escaping in Obsidian and truncation in Feishu output

*End of Implementation Plan*
