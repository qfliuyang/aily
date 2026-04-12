import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from aily.processing.atomicizer import (
    AtomicNote,
    AtomicNoteGenerator,
    ConnectionSuggestion,
)


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.chat_json = AsyncMock()
    client.chat = AsyncMock()
    return client


@pytest.fixture
def mock_graph_db():
    db = MagicMock()
    db.insert_node = AsyncMock()
    db.insert_occurrence = AsyncMock()
    db.insert_edge = AsyncMock()
    db.get_nodes_by_type = AsyncMock(return_value=[])
    return db


@pytest.fixture
def generator(mock_llm_client, mock_graph_db):
    return AtomicNoteGenerator(llm_client=mock_llm_client, graph_db=mock_graph_db)


class TestAtomicNote:
    def test_atomic_note_creation(self):
        note = AtomicNote(
            content="Test content",
            source_url="https://example.com",
            raw_log_id="log-123",
            tags=["test", "example"],
        )
        assert note.content == "Test content"
        assert note.source_url == "https://example.com"
        assert note.raw_log_id == "log-123"
        assert note.tags == ["test", "example"]
        assert note.id is not None
        assert isinstance(note.created_at, datetime)

    def test_atomic_note_default_values(self):
        note = AtomicNote()
        assert note.content == ""
        assert note.tags == []
        assert note.id is not None


class TestConnectionSuggestion:
    def test_connection_suggestion_creation(self):
        suggestion = ConnectionSuggestion(
            target_node_id="node-456",
            relationship_type="related_to",
            confidence_score=0.85,
            explanation="Shared concepts: AI, machine learning",
        )
        assert suggestion.target_node_id == "node-456"
        assert suggestion.relationship_type == "related_to"
        assert suggestion.confidence_score == 0.85
        assert suggestion.explanation == "Shared concepts: AI, machine learning"


class TestAtomicNoteGeneratorAtomize:
    @pytest.mark.asyncio
    async def test_atomize_empty_content(self, generator):
        result = await generator.atomize("", "https://example.com", "log-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_atomize_whitespace_content(self, generator):
        result = await generator.atomize("   \n\t  ", "https://example.com", "log-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_atomize_success(self, generator, mock_llm_client, mock_graph_db):
        mock_llm_client.chat_json.return_value = {
            "notes": [
                {"content": "First atomic idea.", "tags": ["idea", "first"]},
                {"content": "Second atomic idea with more detail.", "tags": ["idea"]},
            ]
        }

        result = await generator.atomize(
            "Some long content with multiple ideas.",
            "https://example.com/article",
            "log-456",
        )

        assert len(result) == 2
        assert result[0].content == "First atomic idea."
        assert result[0].tags == ["idea", "first"]
        assert result[0].source_url == "https://example.com/article"
        assert result[0].raw_log_id == "log-456"

        assert result[1].content == "Second atomic idea with more detail."
        assert result[1].tags == ["idea"]

        # Verify GraphDB storage calls
        assert mock_graph_db.insert_node.call_count == 2
        assert mock_graph_db.insert_occurrence.call_count == 2

    @pytest.mark.asyncio
    async def test_atomize_string_notes(self, generator, mock_llm_client, mock_graph_db):
        """Test handling when LLM returns notes as strings instead of objects."""
        mock_llm_client.chat_json.return_value = {
            "notes": [
                "Simple string note one.",
                "Simple string note two.",
            ]
        }

        result = await generator.atomize(
            "Content with ideas.",
            "https://example.com",
            "log-789",
        )

        assert len(result) == 2
        assert result[0].content == "Simple string note one."
        assert result[0].tags == []
        assert result[1].content == "Simple string note two."

    @pytest.mark.asyncio
    async def test_atomize_empty_notes_filtered(self, generator, mock_llm_client, mock_graph_db):
        """Test that empty note content is filtered out."""
        mock_llm_client.chat_json.return_value = {
            "notes": [
                {"content": "Valid note.", "tags": []},
                {"content": "", "tags": []},
                {"content": "   ", "tags": []},
                {"content": "Another valid note.", "tags": []},
            ]
        }

        result = await generator.atomize(
            "Content with mixed ideas.",
            "https://example.com",
            "log-abc",
        )

        assert len(result) == 2
        assert result[0].content == "Valid note."
        assert result[1].content == "Another valid note."

    @pytest.mark.asyncio
    async def test_atomize_llm_error_fallback(self, generator, mock_llm_client, mock_graph_db):
        """Test fallback to single note when LLM fails."""
        mock_llm_client.chat_json.side_effect = Exception("LLM error")

        result = await generator.atomize(
            "Some content that failed to parse.",
            "https://example.com",
            "log-error",
        )

        assert len(result) == 1
        assert result[0].content == "Some content that failed to parse."
        assert result[0].source_url == "https://example.com"
        assert result[0].raw_log_id == "log-error"

        mock_graph_db.insert_node.assert_called_once()
        mock_graph_db.insert_occurrence.assert_called_once()

    @pytest.mark.asyncio
    async def test_atomize_malformed_response_fallback(self, generator, mock_llm_client, mock_graph_db):
        """Test fallback when LLM returns malformed response."""
        mock_llm_client.chat_json.return_value = {"invalid_key": "no notes here"}

        result = await generator.atomize(
            "Content with no proper notes.",
            "https://example.com",
            "log-malformed",
        )

        assert len(result) == 1
        assert result[0].content == "Content with no proper notes."

    @pytest.mark.asyncio
    async def test_atomize_non_dict_response(self, generator, mock_llm_client, mock_graph_db):
        """Test fallback when LLM returns non-dict response."""
        mock_llm_client.chat_json.return_value = "not a dict"

        result = await generator.atomize(
            "Content with invalid response.",
            "https://example.com",
            "log-invalid",
        )

        assert len(result) == 1
        assert result[0].content == "Content with invalid response."


class TestAtomicNoteGeneratorSuggestConnections:
    @pytest.mark.asyncio
    async def test_suggest_connections_no_existing_nodes(self, generator, mock_graph_db):
        mock_graph_db.get_nodes_by_type.return_value = []

        note = AtomicNote(content="Test note about AI", raw_log_id="log-1")
        result = await generator.suggest_connections(note)

        assert result == []

    @pytest.mark.asyncio
    async def test_suggest_connections_with_matches(self, generator, mock_graph_db):
        mock_graph_db.get_nodes_by_type.return_value = [
            {"id": "node-1", "label": "AI and machine learning concepts"},
            {"id": "node-2", "label": "Cooking recipes for beginners"},
            {"id": "node-3", "label": "Artificial intelligence applications"},
        ]

        note = AtomicNote(content="AI technology is advancing rapidly", raw_log_id="log-1")
        result = await generator.suggest_connections(note)

        # Should find at least one connection to AI-related nodes (node-1 or node-3)
        # The exact count depends on similarity threshold calculations
        assert len(result) >= 1
        target_ids = {s.target_node_id for s in result}
        assert target_ids.issubset({"node-1", "node-3"})  # Only AI-related nodes, not cooking
        assert result[0].relationship_type == "suggested_link"
        assert 0 < result[0].confidence_score <= 1.0
        assert result[0].explanation != ""

        # Verify edges were stored for each suggestion
        assert mock_graph_db.insert_edge.call_count == len(result)

    @pytest.mark.asyncio
    async def test_suggest_connections_self_excluded(self, generator, mock_graph_db):
        """Test that the note itself is excluded from suggestions."""
        note = AtomicNote(
            id="self-node",
            content="AI technology",
            raw_log_id="log-1",
        )
        mock_graph_db.get_nodes_by_type.return_value = [
            {"id": "self-node", "label": "AI technology"},  # Same ID as note
            {"id": "other-node", "label": "Different topic"},
        ]

        result = await generator.suggest_connections(note)

        # Should not suggest connection to itself
        for suggestion in result:
            assert suggestion.target_node_id != "self-node"

    @pytest.mark.asyncio
    async def test_suggest_connections_top_5_limit(self, generator, mock_graph_db):
        """Test that only top 5 suggestions are returned."""
        # Create 10 nodes with varying similarity
        nodes = [
            {"id": f"node-{i}", "label": f"AI and machine learning topic {i}"}
            for i in range(10)
        ]
        mock_graph_db.get_nodes_by_type.return_value = nodes

        note = AtomicNote(content="AI technology and machine learning", raw_log_id="log-1")
        result = await generator.suggest_connections(note)

        # Should return at most 5 suggestions
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_suggest_connections_minimum_threshold(self, generator, mock_graph_db):
        """Test that low-similarity connections are filtered out."""
        mock_graph_db.get_nodes_by_type.return_value = [
            {"id": "node-1", "label": "Completely unrelated topic about cooking"},
            {"id": "node-2", "label": "Another different subject matter"},
        ]

        note = AtomicNote(content="Quantum physics principles", raw_log_id="log-1")
        result = await generator.suggest_connections(note)

        # No significant word overlap, so no suggestions
        assert result == []

    @pytest.mark.asyncio
    async def test_suggest_connections_empty_label_skipped(self, generator, mock_graph_db):
        """Test that nodes with empty labels are skipped."""
        mock_graph_db.get_nodes_by_type.return_value = [
            {"id": "node-1", "label": ""},
            {"id": "node-2", "label": "Valid label about AI"},
        ]

        note = AtomicNote(content="AI technology", raw_log_id="log-1")
        result = await generator.suggest_connections(note)

        # Should only suggest connection to node-2
        assert len(result) == 1
        assert result[0].target_node_id == "node-2"


class TestAtomicNoteGeneratorIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow(self, generator, mock_llm_client, mock_graph_db):
        """Test the full atomize + suggest_connections workflow."""
        # Setup LLM response for atomization
        mock_llm_client.chat_json.return_value = {
            "notes": [
                {"content": "AI is transforming industries.", "tags": ["AI"]},
                {"content": "Machine learning requires data.", "tags": ["ML"]},
            ]
        }

        # Setup existing nodes for connection suggestions
        mock_graph_db.get_nodes_by_type.return_value = [
            {"id": "existing-1", "label": "AI applications in healthcare"},
            {"id": "existing-2", "label": "Data science fundamentals"},
        ]

        # Step 1: Atomize content
        notes = await generator.atomize(
            "AI is transforming industries. Machine learning requires data.",
            "https://example.com/ai-article",
            "log-integration",
        )

        assert len(notes) == 2

        # Step 2: Get connection suggestions for first note
        suggestions = await generator.suggest_connections(notes[0])

        # Should find connection to existing-1 (both about AI)
        assert len(suggestions) >= 1
        assert any(s.target_node_id == "existing-1" for s in suggestions)

        # Verify all database operations were called
        assert mock_graph_db.insert_node.call_count == 2  # Two atomic notes
        assert mock_graph_db.insert_occurrence.call_count == 2
        assert mock_graph_db.insert_edge.call_count >= 1
