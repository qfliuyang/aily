# DIKIWI Monolith-to-Agent Refactoring Plan

## Executive Summary

Transform the 1,940-line monolithic `DikiwiMind.process_input()` into an event-driven agent system by introducing `StageAgent`s, `ProducerAgent`, `ReviewerAgent`, and wiring them through the existing `DikiwiOrchestrator` + `EventBus`. Preserve all invariants: 6-stage order, dataclass shapes, budget enforcement, batching, GraphDB writes, producer-reviewer pattern, memory propagation, Obsidian output, and E2E guarantees.

---

## Phase 1: Design Agent ABC & Context Model

**New file:** `aily/dikiwi/agents/base.py`

```python
@dataclass
class AgentContext:
    """Shared context passed to every agent execution."""
    pipeline_id: str
    correlation_id: str
    drop: RainDrop
    memory: ConversationMemory
    budget: LLMUsageBudget
    stage_results: list[StageResult] = field(default_factory=list)
    artifact_store: dict[str, Any] = field(default_factory=dict)
```

```python
class DikiwiAgent(ABC):
    """Base class for all DIKIWI agents."""
    name: str = "base_agent"
    target_stage: DikiwiStage | None = None

    def __init__(
        self,
        llm_client: Any,
        graph_db: GraphDB | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.graph_db = graph_db
        self.event_bus = event_bus

    @abstractmethod
    async def execute(self, ctx: AgentContext) -> StageResult:
        pass

    async def emit_stage_completed(
        self,
        ctx: AgentContext,
        output_content_ids: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self.event_bus:
            await self.event_bus.publish(
                StageCompletedEvent(
                    correlation_id=ctx.correlation_id,
                    stage=self.target_stage,
                    output_content_ids=output_content_ids,
                    metadata=metadata or {},
                )
            )
```

**Reuse from existing code:**
- `DikiwiStage`, `StageResult` from `aily/sessions/dikiwi_mind.py` (keep existing imports).
- `EventBus`, `StageCompletedEvent` from `aily/dikiwi/events/`.

---

## Phase 2: Implement 6 StageAgents

**New directory:** `aily/dikiwi/agents/`
**New files:** `data_agent.py`, `information_agent.py`, `knowledge_agent.py`, `insight_agent.py`, `wisdom_agent.py`, `impact_agent.py`

### 2.1 DataAgent (`data_agent.py`)

```python
class DataAgent(DikiwiAgent):
    target_stage = DikiwiStage.DATA

    async def execute(self, ctx: AgentContext) -> StageResult:
        # 1. Markdownize drop (reuse _markdownize_drop logic)
        # 2. Chunk if needed (reuse _chunk_content, _LONG_DOC_THRESHOLD)
        # 3. LLM extract per chunk via _llm_extract_chunk
        # 4. Fallback extraction if empty
        # 5. Write data note via dikiwi_obsidian_writer if available
        # 6. Populate ctx.artifact_store["data_points"] and ["doc_title"]
        # 7. Return StageResult + emit StageCompletedEvent
```

**Key preservation:**
- Keep chunking thresholds and max-chunks logic identical.
- Keep `memory.add_assistant()` call after extraction.

### 2.2 InformationAgent (`information_agent.py`)

```python
class InformationAgent(DikiwiAgent):
    target_stage = DikiwiStage.INFORMATION

    async def execute(self, ctx: AgentContext) -> StageResult:
        data_points = ctx.artifact_store["data_points"]
        # 1. Batch classification via _llm_classify_batch
        # 2. Build InformationNode list
        # 3. GraphDB insert_node + _store_node_metadata per node
        # 4. Write information notes via writer
        # 5. Store info_nodes in ctx.artifact_store
        # 6. Emit StageCompletedEvent
```

**Key preservation:**
- Must use the existing `_llm_classify_batch` prompt/registry.
- GraphDB writes happen here, one per node.

### 2.3 KnowledgeAgent (`knowledge_agent.py`)

```python
class KnowledgeAgent(DikiwiAgent):
    target_stage = DikiwiStage.KNOWLEDGE

    async def execute(self, ctx: AgentContext) -> StageResult:
        info_nodes = ctx.artifact_store["information_nodes"]
        if len(info_nodes) < 2:
            return StageResult(stage=DikiwiStage.KNOWLEDGE, success=True, ...)
        # 1. Batch relation mapping via _llm_map_relations_batch
        # 2. GraphDB insert_edge per link
        # 3. Write knowledge notes via writer
        # 4. Store links in ctx.artifact_store
        # 5. Emit StageCompletedEvent
```

**Key preservation:**
- Single batched LLM call (`_llm_map_relations_batch`).
- Edge writes to GraphDB.

### 2.4 InsightAgent (`insight_agent.py`)

```python
class InsightAgent(DikiwiAgent):
    target_stage = DikiwiStage.INSIGHT

    async def execute(self, ctx: AgentContext) -> StageResult:
        info_nodes = ctx.artifact_store["information_nodes"]
        links = ctx.artifact_store.get("links", [])
        # 1. Producer: _llm_detect_patterns (pattern_insights)
        # 2. Reviewer: optional validation pass (reuse reviewer logic from _multi_agent_json)
        # 3. Write insight notes via writer
        # 4. Store insights, emit StageCompletedEvent
```

**Key preservation:**
- Producer-reviewer pattern becomes explicit `ProducerAgent` + `ReviewerAgent` (see Phase 3).
- `InsightAgent` orchestrates them internally.

### 2.5 WisdomAgent (`wisdom_agent.py`)

```python
class WisdomAgent(DikiwiAgent):
    target_stage = DikiwiStage.WISDOM

    async def execute(self, ctx: AgentContext) -> StageResult:
        insights = ctx.artifact_store.get("insights", [])
        info_nodes = ctx.artifact_store["information_nodes"]
        # 1. Producer: _llm_synthesize_wisdom (Zettelkasten notes)
        # 2. Reviewer: slip-box editor review
        # 3. Write wisdom/Zettelkasten notes via writer
        # 4. Store zettels, emit StageCompletedEvent
```

### 2.6 ImpactAgent (`impact_agent.py`)

```python
class ImpactAgent(DikiwiAgent):
    target_stage = DikiwiStage.IMPACT

    async def execute(self, ctx: AgentContext) -> StageResult:
        zettels = ctx.artifact_store.get("zettels", [])
        insights = ctx.artifact_store.get("insights", [])
        # 1. Producer: _llm_generate_impacts
        # 2. Reviewer: action editor review
        # 3. Write impact notes via writer
        # 4. Store impacts, emit StageCompletedEvent
```

---

## Phase 3: ProducerAgent + ReviewerAgent Pattern

**New files:** `aily/dikiwi/agents/producer.py`, `aily/dikiwi/agents/reviewer.py`

### ProducerAgent

```python
class ProducerAgent:
    """Produces a draft LLM response for a given prompt."""

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client

    async def produce(
        self,
        ctx: AgentContext,
        stage: str,
        stage_key: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> Any:
        budget = ctx.budget
        budget.reserve(stage_key or stage)
        return await self.llm_client.chat_json(
            messages=messages, temperature=temperature
        )
```

### ReviewerAgent

```python
class ReviewerAgent:
    """Reviews a draft JSON and returns corrected output."""

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client

    async def review(
        self,
        ctx: AgentContext,
        stage: str,
        stage_key: str,
        draft: dict[str, Any],
        review_messages: list[dict[str, str]],
        temperature: float,
    ) -> dict[str, Any]:
        budget = ctx.budget
        budget.reserve(stage_key or stage)
        try:
            reviewed = await self.llm_client.chat_json(
                messages=review_messages,
                temperature=max(0.1, temperature - 0.05),
            )
            if isinstance(reviewed, dict):
                return reviewed
        except Exception:
            pass
        return draft
```

### Integration

Inside `InsightAgent`, `WisdomAgent`, `ImpactAgent`:

```python
producer = ProducerAgent(self.llm_client)
reviewer = ReviewerAgent(self.llm_client)

draft = await producer.produce(ctx, stage="insight", ...)
reviewed = await reviewer.review(
    ctx, stage="insight", draft=draft,
    review_messages=DikiwiPromptRegistry.review(...),
    ...
)
```

This replaces the implicit `_multi_agent_json` method entirely.

---

## Phase 4: Orchestrator Integration

**Modified file:** `aily/dikiwi/orchestrator.py` (extend, not replace)

Extend `DikiwiOrchestrator` to:
1. Maintain an `agent_registry: dict[DikiwiStage, DikiwiAgent]`.
2. Subscribe to `StageCompletedEvent` and dispatch to the next agent.
3. Subscribe to `ContentPromotedEvent` to promote artifacts through `AgentContext`.

```python
class DikiwiOrchestrator:
    def __init__(...):
        # existing init
        self.agents: dict[DikiwiStage, DikiwiAgent] = {}
        self._contexts: dict[str, AgentContext] = {}

    def register_agent(self, stage: DikiwiStage, agent: DikiwiAgent) -> None:
        self.agents[stage] = agent
        agent.event_bus = self.event_bus

    async def start_pipeline_with_drop(
        self,
        drop: RainDrop,
        memory: ConversationMemory,
        budget: LLMUsageBudget,
    ) -> ProcessingPipeline:
        pipeline = await self.start_pipeline(drop.id, drop.source)
        self._contexts[pipeline.correlation_id] = AgentContext(
            pipeline_id=pipeline.pipeline_id,
            correlation_id=pipeline.correlation_id,
            drop=drop,
            memory=memory,
            budget=budget,
        )
        return pipeline
```

Modify `_on_stage_completed` to dispatch the next agent:

```python
async def _on_stage_completed(self, event: StageCompletedEvent) -> None:
    # existing pipeline lookup + state machine completion
    ...

    # Determine next stage
    next_stage = self._get_next_stage(event.stage)
    if next_stage and next_stage in self.agents:
        ctx = self._contexts.get(event.correlation_id)
        if ctx:
            agent = self.agents[next_stage]
            result = await agent.execute(ctx)
            ctx.stage_results.append(result)
            if result.success:
                await agent.emit_stage_completed(ctx, output_content_ids=[...])
            else:
                await self._fail_pipeline(pipeline, result.error_message)
    elif event.stage == DikiwiStage.IMPACT:
        await self._complete_pipeline(pipeline)
```

**Gate wiring remains unchanged.** The existing `_schedule_menxia_review` and `_schedule_cvo_review` already emit `GateDecisionEvent`s; the orchestrator already handles them. Agents simply emit `StageCompletedEvent` when done, and the orchestrator applies gates before invoking the next agent.

---

## Phase 5: Context/State Passing

**New file:** `aily/dikiwi/agents/context.py`

```python
@dataclass
class AgentContext:
    pipeline_id: str
    correlation_id: str
    drop: RainDrop
    memory: ConversationMemory
    budget: LLMUsageBudget
    stage_results: list[StageResult] = field(default_factory=list)
    artifact_store: dict[str, Any] = field(default_factory=dict)

    def get_artifact(self, key: str, default: Any = None) -> Any:
        return self.artifact_store.get(key, default)

    def set_artifact(self, key: str, value: Any) -> None:
        self.artifact_store[key] = value
```

`ConversationMemory` and `LLMUsageBudget` are created once per pipeline in `DikiwiMind.process_input()` (or in the new adapter) and passed into `AgentContext`. Each agent can read/write memory and the budget is enforced inside `ProducerAgent` and `ReviewerAgent`.

---

## Phase 6: Preserve Batching in INFORMATION / KNOWLEDGE

**No architectural change needed.** The `InformationAgent` calls `_llm_classify_batch(data_points, source, memory)` exactly as the monolith does. The `KnowledgeAgent` calls `_llm_map_relations_batch(info_nodes, source, memory)`.

To keep code DRY, extract these LLM helpers into a new shared module:

**New file:** `aily/dikiwi/agents/llm_tools.py`

```python
async def llm_classify_batch(
    data_points: list[DataPoint],
    source: str,
    memory: ConversationMemory,
    producer: ProducerAgent,
    ctx: AgentContext,
) -> list[dict[str, Any]]:
    ...

async def llm_map_relations_batch(
    info_nodes: list[InformationNode],
    source: str,
    memory: ConversationMemory,
    producer: ProducerAgent,
    ctx: AgentContext,
) -> list[KnowledgeLink]:
    ...
```

These are thin wrappers around `DikiwiPromptRegistry` + `ProducerAgent.produce()`.

---

## Phase 7: Budget Tracking in Agent System

`LLMUsageBudget.reserve()` is called in exactly two places:
1. `ProducerAgent.produce()`
2. `ReviewerAgent.review()`

This centralizes budget tracking. The `_chat_json` helper in `DikiwiMind` can be deleted. Any direct LLM calls outside producer/reviewer (e.g., DATA extraction without reviewer) use `ProducerAgent.produce()`.

**Logging:** Keep the existing `logger.info(...)` call inside `produce()` so metrics remain visible.

---

## Phase 8: Migration Strategy — Backward Compatibility

**Refactoring rule:** Do NOT delete `DikiwiMind` or its tests during the migration. Instead, make `DikiwiMind.process_input()` a **thin adapter** over the new agent system.

### Step 8.1: Build agents underneath (new code)

Create all new files under `aily/dikiwi/agents/` without touching `dikiwi_mind.py`.

### Step 8.2: Adapter method in `DikiwiMind`

Modify `process_input()` to:

```python
async def process_input(self, drop: "RainDrop") -> DikiwiResult:
    if not self.enabled:
        return DikiwiResult(...)

    self._total_inputs += 1
    pipeline_id = f"dikiwi_{drop.id[:12]}_{int(time.time())}"
    memory = self._get_or_create_memory(pipeline_id)
    budget = LLMUsageBudget(
        max_calls=SETTINGS.dikiwi_max_llm_calls_per_source,
        stage_round_limit=SETTINGS.dikiwi_stage_round_limit,
    )
    self._llm_budgets[pipeline_id] = budget

    # Create orchestrator + register agents
    orchestrator = DikiwiOrchestrator(
        llm_client=self.llm_client,
        graph_db=self.graph_db,
        event_bus=InMemoryEventBus(),
    )
    orchestrator.register_agent(DikiwiStage.DATA, DataAgent(self.llm_client, ...))
    orchestrator.register_agent(DikiwiStage.INFORMATION, InformationAgent(...))
    orchestrator.register_agent(DikiwiStage.KNOWLEDGE, KnowledgeAgent(...))
    orchestrator.register_agent(DikiwiStage.INSIGHT, InsightAgent(...))
    orchestrator.register_agent(DikiwiStage.WISDOM, WisdomAgent(...))
    orchestrator.register_agent(DikiwiStage.IMPACT, ImpactAgent(...))

    # Start pipeline
    pipeline = await orchestrator.start_pipeline_with_drop(
        drop=drop, memory=memory, budget=budget
    )

    # Wait for completion via polling (simplest E2E guarantee)
    result = DikiwiResult(input_id=drop.id, pipeline_id=pipeline_id)
    ctx = orchestrator._contexts[pipeline.correlation_id]
    result.stage_results = list(ctx.stage_results)
    result.completed_at = datetime.now(timezone.utc)

    # Cleanup
    self._cleanup_memory(pipeline_id)
    self._llm_budgets.pop(pipeline_id, None)

    if result.final_stage_reached == DikiwiStage.IMPACT:
        self._successful_pipelines += 1
    else:
        self._failed_pipelines += 1

    return result
```

### Step 8.3: Gradual internal migration

Move `_stage_*` method bodies into the agents. Keep the old method signatures in `DikiwiMind` for test compatibility but have them delegate to the agents (or vice versa). Since the tests call `mind._stage_data()`, `mind._stage_information()`, etc., we can keep thin wrapper methods:

```python
async def _stage_data(self, drop, memory=None):
    """Backward-compatible wrapper."""
    agent = DataAgent(self.llm_client, self.graph_db)
    ctx = AgentContext(...)
    return await agent.execute(ctx)
```

After all tests pass with the adapter, the old `_stage_*`, `_llm_*`, and `_write_*` helpers can be deleted in a follow-up PR.

---

## Phase 9: Testing Approach

1. **Unit tests for each StageAgent**
   - `tests/dikiwi/agents/test_data_agent.py`
   - `tests/dikiwi/agents/test_information_agent.py`
   - ... etc.
   - Mock `ProducerAgent` and `ReviewerAgent`, assert correct artifact store mutations.

2. **Unit tests for ProducerAgent + ReviewerAgent**
   - `tests/dikiwi/agents/test_producer_agent.py`
   - Assert budget is decremented on each call.
   - Assert reviewer returns draft on failure.

3. **Integration tests for orchestrator wiring**
   - `tests/dikiwi/test_orchestrator_agents.py`
   - Start pipeline, spy on `event_bus.publish`, verify sequential stage events.

4. **Backward compatibility tests (existing)**
   - `tests/sessions/test_dikiwi_mind.py` must continue to pass unchanged.
   - `tests/sessions/test_dikiwi_budget.py` must continue to pass.
   - `tests/e2e/test_dikiwi_pipeline.py` must continue to pass.

5. **Regression checklist**
   - Count LLM calls per pipeline: should not increase.
   - INFORMATION and KNOWLEDGE must remain 1 batch call each.
   - INSIGHT, WISDOM, IMPACT must remain 2 calls each (producer + reviewer).
   - GraphDB should have same number of nodes/edges as before.
   - Obsidian notes should have identical `dikiwi_level` frontmatter.

---

## Phase 10: File Inventory

### Files to CREATE
1. `aily/dikiwi/agents/__init__.py`
2. `aily/dikiwi/agents/base.py` — `DikiwiAgent`, `AgentContext`
3. `aily/dikiwi/agents/context.py` — `AgentContext` dataclass
4. `aily/dikiwi/agents/producer.py` — `ProducerAgent`
5. `aily/dikiwi/agents/reviewer.py` — `ReviewerAgent`
6. `aily/dikiwi/agents/data_agent.py` — `DataAgent`
7. `aily/dikiwi/agents/information_agent.py` — `InformationAgent`
8. `aily/dikiwi/agents/knowledge_agent.py` — `KnowledgeAgent`
9. `aily/dikiwi/agents/insight_agent.py` — `InsightAgent`
10. `aily/dikiwi/agents/wisdom_agent.py` — `WisdomAgent`
11. `aily/dikiwi/agents/impact_agent.py` — `ImpactAgent`
12. `aily/dikiwi/agents/llm_tools.py` — extracted batch helpers
13. `aily/dikiwi/agents/writer_tools.py` — extracted Obsidian writer helpers (optional)

### Files to MODIFY
1. `aily/dikiwi/orchestrator.py` — add agent registry, `start_pipeline_with_drop`, dispatch in `_on_stage_completed`
2. `aily/sessions/dikiwi_mind.py` — replace `process_input()` with adapter, keep `_stage_*` wrappers for backward compatibility
3. `aily/dikiwi/__init__.py` — export new public classes

### Files to REUSE (no changes)
- `aily/dikiwi/events/bus.py` — `EventBus`, `InMemoryEventBus`
- `aily/dikiwi/events/models.py` — `StageCompletedEvent`, etc.
- `aily/dikiwi/stages.py` — `DikiwiStage`, `StageStateMachine`
- `aily/dikiwi/gates/menxia.py` — `MenxiaGate`
- `aily/dikiwi/skills/base.py` — `Skill`, `SkillContext`, `SkillResult`
- `aily/llm/prompt_registry.py` — `DikiwiPromptRegistry`
- `aily/thinking/orchestrator.py` — reference pattern for fan-out/fan-in (no direct import needed)
