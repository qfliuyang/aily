"""Tests for DIKIWI memorial storage.

Tests:
- GraphDB storage with retry
- Obsidian storage with index
- Dual storage
- Dead-letter queue
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from aily.dikiwi.memorials import (
    GraphDBMemorialStore,
    Memorial,
    MemorialDecisionType,
    ObsidianMemorialStore,
)


class TestGraphDBMemorialStore:
    """Test GraphDB memorial storage with retry."""

    async def test_save_with_retry_success(self, mock_graph_db, sample_memorial):
        """Save succeeds on first attempt."""
        store = GraphDBMemorialStore(mock_graph_db)

        await store.save(sample_memorial)

        mock_graph_db.query.assert_called_once()

    async def test_save_with_retry_eventually_succeeds(self, mock_graph_db, sample_memorial):
        """Save retries and eventually succeeds."""
        # Fail twice, succeed on third
        mock_graph_db.query = AsyncMock(side_effect=[
            Exception("DB Error"),
            Exception("DB Error"),
            [],  # Success
        ])

        store = GraphDBMemorialStore(mock_graph_db)

        await store.save(sample_memorial)

        assert mock_graph_db.query.call_count == 3

    async def test_save_adds_to_dlq_after_max_retries(self, mock_graph_db, sample_memorial):
        """Failed saves are added to dead-letter queue."""
        mock_graph_db.query = AsyncMock(side_effect=Exception("Persistent DB Error"))

        store = GraphDBMemorialStore(mock_graph_db)

        with pytest.raises(Exception):
            await store.save(sample_memorial)

        dlq = store.get_dead_letter_queue()
        assert len(dlq) == 1
        assert dlq[0].memorial.memorial_id == sample_memorial.memorial_id
        assert dlq[0].operation == "save"

    async def test_get_with_retry(self, mock_graph_db):
        """Get retries on failure."""
        mock_graph_db.query = AsyncMock(side_effect=[
            Exception("DB Error"),
            [{"m": {"id": "test", "correlation_id": "corr"}}],
        ])

        store = GraphDBMemorialStore(mock_graph_db)
        result = await store.get("test-id")

        assert mock_graph_db.query.call_count == 2
        assert result is not None

    async def test_get_returns_none_on_failure(self, mock_graph_db):
        """Get returns None if all retries fail."""
        mock_graph_db.query = AsyncMock(side_effect=Exception("Persistent Error"))

        store = GraphDBMemorialStore(mock_graph_db)
        result = await store.get("test-id")

        assert result is None

    async def test_query_with_retry(self, mock_graph_db):
        """Query retries on failure."""
        mock_graph_db.query = AsyncMock(side_effect=[
            Exception("DB Error"),
            [],  # Success with empty results
        ])

        store = GraphDBMemorialStore(mock_graph_db)
        results = await store.query(correlation_id="corr-001")

        assert mock_graph_db.query.call_count == 2
        assert results == []

    def test_get_health_metrics(self, mock_graph_db, sample_memorial):
        """Health metrics include DLQ status."""
        store = GraphDBMemorialStore(mock_graph_db)

        # Add to DLQ manually
        from aily.dikiwi.memorials.storage import FailedMemorialEntry
        store._dead_letter_queue.append(
            FailedMemorialEntry(
                memorial=sample_memorial,
                operation="save",
                error="Test error",
            )
        )

        metrics = store.get_health_metrics()

        assert metrics["dead_letter_queue_size"] == 1
        assert metrics["health_status"] == "degraded"

    def test_clear_dlq(self, mock_graph_db, sample_memorial):
        """Can clear dead-letter queue."""
        store = GraphDBMemorialStore(mock_graph_db)

        from aily.dikiwi.memorials.storage import FailedMemorialEntry
        store._dead_letter_queue.append(
            FailedMemorialEntry(
                memorial=sample_memorial,
                operation="save",
                error="Test error",
            )
        )

        count = store.clear_dead_letter_queue()

        assert count == 1
        assert len(store.get_dead_letter_queue()) == 0


class TestObsidianMemorialStore:
    """Test Obsidian memorial storage with index."""

    async def test_save_creates_markdown_file(self, temp_vault_path, sample_memorial):
        """Save creates markdown file in correct location."""
        store = ObsidianMemorialStore(temp_vault_path)

        await store.save(sample_memorial)

        # Check file was created
        month_dir = temp_vault_path / "Memorials" / sample_memorial.timestamp.strftime("%Y-%m")
        file_path = month_dir / f"{sample_memorial.memorial_id}.md"

        assert file_path.exists()
        content = file_path.read_text()
        assert sample_memorial.memorial_id in content

    async def test_save_updates_index(self, temp_vault_path, sample_memorial):
        """Save updates in-memory index."""
        store = ObsidianMemorialStore(temp_vault_path)

        await store.save(sample_memorial)

        assert sample_memorial.memorial_id in store._index
        assert sample_memorial.correlation_id in store._correlation_index
        assert sample_memorial.pipeline_id in store._pipeline_index

    async def test_get_uses_index(self, temp_vault_path, sample_memorial):
        """Get uses index for fast lookup."""
        store = ObsidianMemorialStore(temp_vault_path)
        await store.save(sample_memorial)

        # Reset index built flag to test index building
        store._index_built = False

        result = await store.get(sample_memorial.memorial_id)

        assert result is not None
        assert result.memorial_id == sample_memorial.memorial_id
        assert store._index_built

    async def test_query_uses_correlation_index(self, temp_vault_path):
        """Query uses correlation index for fast lookup."""
        store = ObsidianMemorialStore(temp_vault_path)

        # Create two memorials with same correlation
        m1 = Memorial(
            memorial_id="m1",
            correlation_id="corr-001",
            pipeline_id="p1",
            stage="KNOWLEDGE",
            decision=MemorialDecisionType.PROMOTED,
            input_hash="h1",
            output_hash="h2",
            reasoning="R1",
            agent_id="a1",
            gate_name="menxia",
            timestamp=datetime.now(timezone.utc),
        )
        m2 = Memorial(
            memorial_id="m2",
            correlation_id="corr-001",
            pipeline_id="p2",
            stage="INSIGHT",
            decision=MemorialDecisionType.PROMOTED,
            input_hash="h1",
            output_hash="h2",
            reasoning="R2",
            agent_id="a1",
            gate_name="menxia",
            timestamp=datetime.now(timezone.utc),
        )

        await store.save(m1)
        await store.save(m2)

        results = await store.query(correlation_id="corr-001")

        assert len(results) == 2

    async def test_query_uses_pipeline_index(self, temp_vault_path):
        """Query uses pipeline index for fast lookup."""
        store = ObsidianMemorialStore(temp_vault_path)

        m1 = Memorial(
            memorial_id="m1",
            correlation_id="c1",
            pipeline_id="pipe-001",
            stage="KNOWLEDGE",
            decision=MemorialDecisionType.PROMOTED,
            input_hash="h1",
            output_hash="h2",
            reasoning="R",
            agent_id="a1",
            gate_name="menxia",
            timestamp=datetime.now(timezone.utc),
        )

        await store.save(m1)

        results = await store.query(pipeline_id="pipe-001")

        assert len(results) == 1

    def test_get_index_stats(self, temp_vault_path, sample_memorial):
        """Index stats report correctly."""
        store = ObsidianMemorialStore(temp_vault_path)

        # Manually populate index
        store._index[sample_memorial.memorial_id] = temp_vault_path
        store._correlation_index[sample_memorial.correlation_id] = [sample_memorial.memorial_id]
        store._pipeline_index[sample_memorial.pipeline_id] = [sample_memorial.memorial_id]
        store._index_built = True

        stats = store.get_index_stats()

        assert stats["indexed_memorials"] == 1
        assert stats["correlation_entries"] == 1
        assert stats["pipeline_entries"] == 1
        assert stats["health_status"] == "healthy"

    async def test_build_index_from_existing_files(self, temp_vault_path, sample_memorial):
        """Index is built from existing files on first access."""
        # Save without building index
        store = ObsidianMemorialStore(temp_vault_path)
        await store.save(sample_memorial)

        # Clear index
        store._index.clear()
        store._index_built = False

        # Get should rebuild index
        result = await store.get(sample_memorial.memorial_id)

        assert result is not None
        assert store._index_built
        assert sample_memorial.memorial_id in store._index


class TestDualMemorialStore:
    """Test dual storage (GraphDB + Obsidian)."""

    async def test_save_to_both_stores(self, mock_graph_db, temp_vault_path, sample_memorial):
        """Save writes to both stores."""
        from aily.dikiwi.memorials import DualMemorialStore

        graph_store = GraphDBMemorialStore(mock_graph_db)
        obsidian_store = ObsidianMemorialStore(temp_vault_path)
        dual_store = DualMemorialStore(graph_store, obsidian_store)

        await dual_store.save(sample_memorial)

        # Check GraphDB was called
        mock_graph_db.query.assert_called()

        # Check Obsidian file was created
        month_dir = temp_vault_path / "Memorials" / sample_memorial.timestamp.strftime("%Y-%m")
        file_path = month_dir / f"{sample_memorial.memorial_id}.md"
        assert file_path.exists()

    async def test_obsidian_failure_doesnt_fail_operation(
        self, mock_graph_db, temp_vault_path, sample_memorial, caplog
    ):
        """Obsidian failure doesn't fail the whole operation."""
        from aily.dikiwi.memorials import DualMemorialStore

        graph_store = GraphDBMemorialStore(mock_graph_db)
        obsidian_store = ObsidianMemorialStore(temp_vault_path)

        # Make Obsidian save fail
        async def failing_save(*args, **kwargs):
            raise IOError("Disk full")

        obsidian_store.save = failing_save

        dual_store = DualMemorialStore(graph_store, obsidian_store)

        # Should not raise
        await dual_store.save(sample_memorial)

        # GraphDB should still be called
        mock_graph_db.query.assert_called()

    async def test_get_uses_graphdb(self, mock_graph_db, temp_vault_path):
        """Get uses GraphDB (faster)."""
        from aily.dikiwi.memorials import DualMemorialStore

        graph_store = GraphDBMemorialStore(mock_graph_db)
        obsidian_store = ObsidianMemorialStore(temp_vault_path)
        dual_store = DualMemorialStore(graph_store, obsidian_store)

        mock_graph_db.query = AsyncMock(return_value=[{"m": {"id": "test"}}])

        await dual_store.get("test-id")

        # Only GraphDB should be queried
        mock_graph_db.query.assert_called_once()

    def test_get_health_metrics(self, mock_graph_db, temp_vault_path):
        """Health metrics from both stores."""
        from aily.dikiwi.memorials import DualMemorialStore

        graph_store = GraphDBMemorialStore(mock_graph_db)
        obsidian_store = ObsidianMemorialStore(temp_vault_path)
        dual_store = DualMemorialStore(graph_store, obsidian_store)

        metrics = dual_store.get_health_metrics()

        assert "graphdb" in metrics
        assert "obsidian" in metrics
