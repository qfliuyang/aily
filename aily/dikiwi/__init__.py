"""DIKIWI - Multi-agent knowledge system with institutional review.

Re-architected with:
- Event-driven coordination (EventBus)
- Skill-based capabilities (SkillRegistry)
- Institutional review gates (门下省 Menxia, CVO)
- Audit trail (Memorials)
- Three-layer architecture (Model/Tool/Platform)

Usage:
    from aily.dikiwi import DikiwiOrchestrator, PipelineConfig

    orchestrator = DikiwiOrchestrator(llm_client, graph_db)
    pipeline = await orchestrator.start_pipeline(content_id, source)
"""

from aily.dikiwi.events import (
    ContentPromotedEvent,
    Event,
    EventBus,
    GateDecisionEvent,
    ImpactGeneratedEvent,
    InMemoryEventBus,
    InsightDiscoveredEvent,
    MemorialCreatedEvent,
    StageCompletedEvent,
    StageRejectedEvent,
    WisdomSynthesizedEvent,
)
from aily.dikiwi.gates import (
    ApprovalDecision,
    ApprovalDecisionType,
    CVOGate,
    MenxiaGate,
    PendingApproval,
    ReviewDecision,
    ReviewDecisionType,
)
from aily.dikiwi.memorials import (
    GraphDBMemorialStore,
    Memorial,
    MemorialDecisionType,
    ObsidianMemorialStore,
)
from aily.dikiwi.orchestrator import (
    DikiwiOrchestrator,
    PipelineConfig,
    ProcessingPipeline,
)
from aily.dikiwi.skills import (
    Skill,
    SkillContext,
    SkillMetadata,
    SkillRegistry,
    SkillResult,
    get_skill_registry,
)
from aily.dikiwi.stages import (
    DikiwiStage,
    StageContext,
    StageState,
    StageStateMachine,
    can_transition,
)

# Agents (v2 agent system)
from aily.dikiwi.agents import (
    DikiwiAgent,
    AgentContext,
    ProducerAgent,
    ReviewerAgent,
    DataAgent,
    InformationAgent,
    KnowledgeAgent,
    InsightAgent,
    WisdomAgent,
    ImpactAgent,
    ResidualAgent,
    ObsidianCLI,
)

__all__ = [
    # Core orchestrator
    "DikiwiOrchestrator",
    "PipelineConfig",
    "ProcessingPipeline",
    # Stages
    "DikiwiStage",
    "StageContext",
    "StageState",
    "StageStateMachine",
    "can_transition",
    # Events
    "Event",
    "EventBus",
    "InMemoryEventBus",
    "StageCompletedEvent",
    "StageRejectedEvent",
    "ContentPromotedEvent",
    "InsightDiscoveredEvent",
    "WisdomSynthesizedEvent",
    "ImpactGeneratedEvent",
    "MemorialCreatedEvent",
    "GateDecisionEvent",
    # Gates
    "MenxiaGate",
    "ReviewDecision",
    "ReviewDecisionType",
    "CVOGate",
    "ApprovalDecision",
    "ApprovalDecisionType",
    "PendingApproval",
    # Skills
    "Skill",
    "SkillContext",
    "SkillResult",
    "SkillMetadata",
    "SkillRegistry",
    "get_skill_registry",
    # Memorials
    "Memorial",
    "MemorialDecisionType",
    "GraphDBMemorialStore",
    "ObsidianMemorialStore",
    # Agents
    "DikiwiAgent",
    "AgentContext",
    "ProducerAgent",
    "ReviewerAgent",
    "DataAgent",
    "InformationAgent",
    "KnowledgeAgent",
    "InsightAgent",
    "WisdomAgent",
    "ImpactAgent",
    "ResidualAgent",
    "ObsidianCLI",
]

__version__ = "2.0.0"
