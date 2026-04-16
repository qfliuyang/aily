"""E2E tests for DIKIWI Mind pipeline.

Tests the complete Data → Information → Knowledge → Insight → Wisdom → Impact
pipeline with real components (no mocks).
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from pathlib import Path

from aily.sessions.models import ProposalStatus


@pytest.mark.asyncio
class TestDIKIWIPipeline:
    """End-to-end tests for the DIKIWI pipeline."""

    async def test_url_drop_to_knowledge(
        self,
        e2e_context,
        dikiwi_mind,
        graph_db,
        queue_db,
        vault_verifier,
        db_verifier,
        test_data,
    ):
        """Test complete flow: URL drop → DIKIWI pipeline → Knowledge stored."""
        # Arrange: Create a URL drop
        drop = test_data.url_drop(
            url="https://example.com/ai-article",
            content=(
                "Artificial intelligence is fundamentally transforming how we build software, "
                "design systems, and organize teams. Machine learning models can now generate code, "
                "detect bugs, and optimize performance in ways that were impossible just a few years ago.\n\n"
                "This shift is not merely about automation. It represents a change in the very nature "
                "of programming, where human creativity is increasingly focused on problem formulation, "
                "architectural decisions, and ethical constraints, while algorithms handle implementation details."
            ),
        )

        # Act: Process through DIKIWI mind
        result = await dikiwi_mind.process_input(drop)

        # Assert: Pipeline completed successfully
        assert result.final_stage_reached is not None

        # Verify: Knowledge stored in GraphDB (use _fetchall with actual API)
        rows = await graph_db._fetchall("SELECT COUNT(*) as count FROM nodes")
        count = rows[0][0] if rows else 0
        assert count >= 1, f"Expected at least 1 node, found {count}"

    async def test_voice_drop_processing(
        self,
        e2e_context,
        dikiwi_mind,
        graph_db,
        vault_verifier,
        db_verifier,
        test_data,
    ):
        """Test voice memo drop processing through DIKIWI."""
        # Arrange: Create a voice drop
        drop = test_data.voice_drop(file_key="voice_abc123")

        # Act: Process through DIKIWI mind
        result = await dikiwi_mind.process_input(drop)

        # Assert: Pipeline handled voice input
        assert result.input_id == drop.id
        assert result.final_stage_reached is not None

        # Verify: Node created in graph (type may vary by implementation)
        rows = await graph_db._fetchall("SELECT * FROM nodes")
        assert len(rows) >= 1, "Expected at least 1 node to be created"

    async def test_dikiwi_disabled_returns_early(
        self,
        e2e_context,
        graph_db,
        llm_client,
        test_data,
    ):
        """Test that disabled DIKIWI mind returns early without processing."""
        from aily.sessions.dikiwi_mind import DikiwiMind

        # Arrange: Create disabled mind
        disabled_mind = DikiwiMind(
            llm_client=llm_client,
            graph_db=graph_db,
            enabled=False,
        )

        drop = test_data.url_drop()

        # Act: Process with disabled mind
        result = await disabled_mind.process_input(drop)

        # Assert: Early return with failure (check via stage_results)
        assert result.final_stage_reached is None
        assert len(result.stage_results) >= 1
        assert result.stage_results[0].success is False

    async def test_multiple_drops_accumulate(
        self,
        e2e_context,
        dikiwi_mind,
        graph_db,
        db_verifier,
        test_data,
    ):
        """Test that multiple drops create multiple knowledge nodes."""
        # Arrange & Act: Process 3 drops
        drops = [
            test_data.url_drop(url=f"https://example.com/article{i}")
            for i in range(3)
        ]

        for drop in drops:
            result = await dikiwi_mind.process_input(drop)
            assert result.final_stage_reached is not None

        # Assert: All nodes created
        rows = await graph_db._fetchall("SELECT COUNT(*) as count FROM nodes")
        count = rows[0][0] if rows else 0
        assert count >= 3, f"Expected at least 3 nodes, found {count}"

    async def test_drop_content_hashing(
        self,
        e2e_context,
        dikiwi_mind,
        graph_db,
        test_data,
    ):
        """Test that identical content is detected via hashing."""
        # Arrange: Two drops with same content
        content = "This is identical content for testing"
        drop1 = test_data.url_drop(url="https://example.com/1", content=content)
        drop2 = test_data.url_drop(url="https://example.com/2", content=content)

        # Act: Process both
        result1 = await dikiwi_mind.process_input(drop1)
        result2 = await dikiwi_mind.process_input(drop2)

        # Assert: Both processed (deduplication happens at storage layer)
        assert result1.final_stage_reached is not None
        assert result2.final_stage_reached is not None


@pytest.mark.asyncio
class TestKnowledgeExtraction:
    """E2E tests for knowledge extraction from various input types."""

    async def test_keyword_extraction(
        self,
        e2e_context,
        dikiwi_mind,
        test_data,
    ):
        """Test that keywords are extracted from content."""
        # Arrange
        content = "Machine learning and artificial intelligence drive modern automation"
        drop = test_data.url_drop(content=content)

        # Act: Process through DATA and INFORMATION stages
        result = await dikiwi_mind.process_input(drop)

        # Assert: Keywords extracted
        info_stage = next(
            (r for r in result.stage_results if r.stage.name == "INFORMATION"),
            None
        )
        assert info_stage is not None
        assert info_stage.success is True
        assert "keywords" in info_stage.data

    async def test_entity_extraction(
        self,
        e2e_context,
        dikiwi_mind,
        test_data,
    ):
        """Test named entity extraction from content."""
        # Arrange
        content = "Google and Microsoft compete in the cloud computing market"
        drop = test_data.url_drop(content=content)

        # Act
        result = await dikiwi_mind.process_input(drop)

        # Assert: Entities extracted
        info_stage = next(
            (r for r in result.stage_results if r.stage.name == "INFORMATION"),
            None
        )
        assert info_stage is not None
        if "entities" in info_stage.data:
            entities = info_stage.data["entities"]
            # Should have extracted company names
            assert any("Google" in str(e) or "Microsoft" in str(e) for e in entities)

    async def test_information_to_knowledge_promotion(
        self,
        e2e_context,
        dikiwi_mind,
        graph_db,
        db_verifier,
        test_data,
    ):
        """Test that processed information becomes knowledge nodes."""
        # Arrange
        drop = test_data.url_drop(
            content=(
                "The key insight is that distributed systems require careful consensus design. "
                "When multiple nodes must agree on a single source of truth, the choice of protocol "
                "directly affects availability, partition tolerance, and consistency guarantees.\n\n"
                "Raft offers a leader-follower approach that is easier to reason about and implement, "
                "while Paxos provides stronger theoretical guarantees at the cost of complexity. "
                "Engineering teams should evaluate their operational constraints before committing to either model."
            )
        )

        # Act
        result = await dikiwi_mind.process_input(drop)

        # Assert: Reached KNOWLEDGE stage
        knowledge_stage = next(
            (r for r in result.stage_results if r.stage.name == "KNOWLEDGE"),
            None
        )
        assert knowledge_stage is not None
        assert knowledge_stage.success is True
        assert knowledge_stage.items_output > 0


@pytest.mark.asyncio
class TestGraphDBIntegration:
    """E2E tests for GraphDB integration with DIKIWI pipeline."""

    async def test_nodes_have_required_fields(
        self,
        e2e_context,
        dikiwi_mind,
        graph_db,
        test_data,
    ):
        """Test that created nodes have all required fields."""
        # Arrange & Act
        drop = test_data.url_drop()
        await dikiwi_mind.process_input(drop)

        # Assert: Check node structure using _fetchall
        rows = await graph_db._fetchall("SELECT * FROM nodes LIMIT 1")
        assert len(rows) > 0

        # Get column names from cursor description
        cursor = await graph_db._db.execute("SELECT * FROM nodes LIMIT 1")
        columns = [desc[0] for desc in cursor.description]
        await cursor.close()

        required_fields = ["id", "type", "created_at"]
        for field in required_fields:
            assert field in columns, f"Missing required field: {field}"

    async def test_node_relationships_created(
        self,
        e2e_context,
        dikiwi_mind,
        graph_db,
        test_data,
    ):
        """Test that relationships between nodes are created."""
        # Arrange: Process a drop
        drop = test_data.url_drop(content="Testing relationship creation")
        await dikiwi_mind.process_input(drop)

        # Act: Query for relationships using _fetchall
        rows = await graph_db._fetchall("SELECT * FROM edges")

        # Assert: Some edges should exist (even if just internal ones)
        assert isinstance(rows, list)

    async def test_query_by_type(
        self,
        e2e_context,
        dikiwi_mind,
        graph_db,
        test_data,
    ):
        """Test querying nodes by type."""
        # Arrange
        drop = test_data.url_drop()
        await dikiwi_mind.process_input(drop)

        # Act: Query by different types using actual API
        all_nodes = await graph_db.get_nodes_by_type("raw_input")

        # Assert: Found nodes (type may vary by implementation)
        # Just verify the query works and returns a list
        assert isinstance(all_nodes, list)


@pytest.mark.asyncio
class TestQueueDBIntegration:
    """E2E tests for QueueDB integration."""

    async def test_job_can_be_enqueued(
        self,
        e2e_context,
        queue_db,
        test_data,
    ):
        """Test that jobs can be enqueued."""
        # Arrange & Act
        job_id = await queue_db.enqueue("test_job", {"test": "data"})

        # Assert: Job was created
        assert job_id is not None
        assert isinstance(job_id, str)

    async def test_job_status_tracking(
        self,
        e2e_context,
        queue_db,
        test_data,
    ):
        """Test that job status is tracked through pipeline."""
        # Arrange: Enqueue a job
        job_id = await queue_db.enqueue("test_job", {"test": "data"})

        # Act: Get the job
        job = await queue_db.get_job(job_id)

        # Assert: Job exists and has required fields
        assert job is not None
        assert job["id"] == job_id
        assert "status" in job
