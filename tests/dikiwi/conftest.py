"""Pytest fixtures for DIKIWI tests."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from aily.dikiwi.skills.base import Skill, SkillContext, SkillResult

from aily.dikiwi import (
    CVOGate,
    DikiwiOrchestrator,
    InMemoryEventBus,
    MenxiaGate,
    PipelineConfig,
    SkillRegistry,
    StageContext,
    StageStateMachine,
)
from aily.dikiwi.events.models import (
    ContentPromotedEvent,
    GateDecisionEvent,
    StageCompletedEvent,
)
from aily.dikiwi.gates import ReviewDecision, ReviewDecisionType
from aily.dikiwi.memorials import Memorial, MemorialDecisionType
from aily.dikiwi.skills.base import Skill, SkillContext, SkillResult
from aily.dikiwi.stages import DikiwiStage, StageState


@pytest.fixture
def event_loop():
    """Create an event loop for tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    client = MagicMock()
    client.complete = AsyncMock(return_value="""
        Decision: APPROVE
        Quality Score: 0.8
        Reason: Good quality content
    """)
    return client


@pytest.fixture
def mock_graph_db():
    """Mock GraphDB for testing."""
    db = MagicMock()
    db.query = AsyncMock(return_value=[])
    return db


@pytest.fixture
def event_bus():
    """Create an in-memory event bus."""
    return InMemoryEventBus()


@pytest.fixture
def pipeline_config():
    """Create a test pipeline config."""
    return PipelineConfig(
        menxia_quality_threshold=0.6,
        cvo_ttl_hours=1,  # Short TTL for testing
        max_rejections=3,
    )


@pytest.fixture
def menxia_gate(mock_llm_client):
    """Create a Menxia gate for testing."""
    return MenxiaGate(
        llm_client=mock_llm_client,
        quality_threshold=0.6,
    )


@pytest.fixture
def cvo_gate():
    """Create a CVO gate for testing."""
    return CVOGate(ttl_hours=1)


@pytest.fixture
def skill_registry():
    """Create a skill registry for testing."""
    registry = SkillRegistry(max_cache_size=10)
    return registry


@pytest.fixture
def temp_vault_path():
    """Create a temporary vault path for Obsidian tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_memorial():
    """Create a sample memorial for testing."""
    return Memorial(
        memorial_id="test-memorial-001",
        correlation_id="corr-001",
        pipeline_id="pipe-001",
        stage="KNOWLEDGE",
        decision=MemorialDecisionType.PROMOTED,
        input_hash="a1b2c3",
        output_hash="d4e5f6",
        reasoning="Test reasoning",
        agent_id="test-agent",
        gate_name="menxia",
        timestamp=datetime.now(timezone.utc),
        metadata={"test": True},
    )


@pytest.fixture
def stage_context():
    """Create a stage context for testing."""
    return StageContext(
        context_id="ctx-001",
        correlation_id="corr-001",
        content_id="content-001",
        current_stage=DikiwiStage.INFORMATION,
        stage_state=StageState.PROCESSING,
        stage_history=[],
        rejection_count={},
    )


class TestSkill(Skill):
    """Test skill for unit tests."""

    name = "test_skill"
    description = "A test skill"
    version = "1.0.0"
    target_stages = ["information"]
    content_types = ["*"]

    async def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult.success_result(
            skill_name=self.name,
            output={"test": True},
            processing_time_ms=0.0,
        )


@pytest.fixture
def test_skill():
    """Create a test skill instance."""
    return TestSkill()
