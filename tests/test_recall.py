import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from aily.learning.recall import RecallQuestionGenerator, RecallPrompt, ClozeDeletion


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.chat_json = AsyncMock()
    return llm


@pytest.fixture
def mock_graph_db():
    db = MagicMock()
    db.insert_node = AsyncMock()
    db.insert_edge = AsyncMock()
    db.get_nodes_by_type = AsyncMock(return_value=[])
    return db


@pytest.fixture
def generator(mock_llm, mock_graph_db):
    return RecallQuestionGenerator(llm_client=mock_llm, graph_db=mock_graph_db)


@pytest.mark.asyncio
async def test_generate_questions_open_type(generator, mock_llm):
    """Test generating open-ended questions."""
    mock_llm.chat_json.return_value = {
        "questions": [
            {
                "question_text": "Explain the concept of active recall.",
                "answer_text": "Active recall is a learning technique...",
                "question_type": "open",
            },
            {
                "question_text": "How does spaced repetition work?",
                "answer_text": "Spaced repetition schedules reviews...",
                "question_type": "open",
            },
        ]
    }

    note_content = "Active recall is a powerful learning technique. Spaced repetition schedules reviews at optimal intervals."
    questions = await generator.generate_questions(note_content, "note-123", question_types=["open"])

    assert len(questions) == 2
    assert all(q.question_type == "open" for q in questions)
    assert questions[0].question_text == "Explain the concept of active recall."
    assert questions[0].answer_text == "Active recall is a learning technique..."
    assert questions[0].note_id == "note-123"
    assert questions[0].review_count == 0


@pytest.mark.asyncio
async def test_generate_questions_cloze_type(generator, mock_llm):
    """Test generating cloze questions."""
    mock_llm.chat_json.return_value = {
        "questions": [
            {
                "question_text": "The [[Ebbinghaus]] curve shows memory decays exponentially.",
                "answer_text": "Ebbinghaus",
                "question_type": "cloze",
            }
        ]
    }

    note_content = "The Ebbinghaus forgetting curve shows that memory decays exponentially over time."
    questions = await generator.generate_questions(note_content, "note-456", question_types=["cloze"])

    assert len(questions) == 1
    assert questions[0].question_type == "cloze"
    assert "[[Ebbinghaus]]" in questions[0].question_text
    assert questions[0].answer_text == "Ebbinghaus"


@pytest.mark.asyncio
async def test_generate_questions_choice_type(generator, mock_llm):
    """Test generating multiple choice questions."""
    mock_llm.chat_json.return_value = {
        "questions": [
            {
                "question_text": "What percentage more effective is active recall than passive review?",
                "answer_text": "50-100%",
                "question_type": "choice",
                "distractors": ["10-20%", "25-50%", "200-300%"],
            }
        ]
    }

    note_content = "Active recall strengthens memory 50-100% more than passive review."
    questions = await generator.generate_questions(note_content, "note-789", question_types=["choice"])

    assert len(questions) == 1
    assert questions[0].question_type == "choice"
    assert questions[0].answer_text == "50-100%"
    assert questions[0].metadata.get("distractors") == ["10-20%", "25-50%", "200-300%"]


@pytest.mark.asyncio
async def test_generate_questions_filters_by_type(generator, mock_llm):
    """Test that questions are filtered by requested type."""
    mock_llm.chat_json.return_value = {
        "questions": [
            {
                "question_text": "Question 1",
                "answer_text": "Answer 1",
                "question_type": "open",
            },
            {
                "question_text": "Question 2",
                "answer_text": "Answer 2",
                "question_type": "cloze",
            },
        ]
    }

    questions = await generator.generate_questions("content", "note-1", question_types=["open"])

    assert len(questions) == 1
    assert questions[0].question_type == "open"


@pytest.mark.asyncio
async def test_generate_questions_stores_in_graph_db(generator, mock_llm, mock_graph_db):
    """Test that generated questions are stored in the graph database."""
    mock_llm.chat_json.return_value = {
        "questions": [
            {
                "question_text": "Test question?",
                "answer_text": "Test answer.",
                "question_type": "open",
            }
        ]
    }

    await generator.generate_questions("content", "note-123")

    mock_graph_db.insert_node.assert_called_once()
    mock_graph_db.insert_edge.assert_called_once()

    # Check edge has correct relation type
    call_kwargs = mock_graph_db.insert_edge.call_args.kwargs
    assert call_kwargs.get("relation_type") == "tests_knowledge_of"


@pytest.mark.asyncio
async def test_generate_questions_llm_error(generator, mock_llm):
    """Test handling of LLM errors."""
    mock_llm.chat_json.side_effect = Exception("LLM error")

    questions = await generator.generate_questions("content", "note-1")

    assert questions == []


@pytest.mark.asyncio
async def test_generate_cloze(generator, mock_llm):
    """Test generating cloze deletions."""
    mock_llm.chat_json.return_value = {
        "clozes": [
            {
                "full_text": "The Ebbinghaus forgetting curve shows memory decays exponentially.",
                "cloze_text": "The [[Ebbinghaus]] forgetting curve shows memory decays exponentially.",
                "answer": "Ebbinghaus",
                "hint": "German psychologist",
            },
            {
                "full_text": "Spaced repetition optimizes review intervals.",
                "cloze_text": "[[Spaced repetition]] optimizes review intervals.",
                "answer": "Spaced repetition",
                "hint": "",
            },
        ]
    }

    note_content = "The Ebbinghaus forgetting curve shows memory decays exponentially. Spaced repetition optimizes review intervals."
    clozes = await generator.generate_cloze(note_content, "note-abc")

    assert len(clozes) == 2
    assert clozes[0].answer == "Ebbinghaus"
    assert clozes[0].hint == "German psychologist"
    assert "[[Ebbinghaus]]" in clozes[0].cloze_text
    assert clozes[0].note_id == "note-abc"


@pytest.mark.asyncio
async def test_generate_cloze_stores_in_graph_db(generator, mock_llm, mock_graph_db):
    """Test that cloze deletions are stored as recall prompts."""
    mock_llm.chat_json.return_value = {
        "clozes": [
            {
                "full_text": "Test sentence.",
                "cloze_text": "[[Test]] sentence.",
                "answer": "Test",
                "hint": "",
            }
        ]
    }

    await generator.generate_cloze("content", "note-456")

    mock_graph_db.insert_node.assert_called_once()
    mock_graph_db.insert_edge.assert_called_once()


@pytest.mark.asyncio
async def test_generate_cloze_llm_error(generator, mock_llm):
    """Test handling of LLM errors during cloze generation."""
    mock_llm.chat_json.side_effect = Exception("LLM error")

    clozes = await generator.generate_cloze("content", "note-1")

    assert clozes == []


@pytest.mark.asyncio
async def test_get_due_questions(generator, mock_graph_db):
    """Test retrieving due questions from graph database."""
    mock_graph_db.get_nodes_by_type.return_value = [
        {
            "id": "prompt-1",
            "type": "recall_prompt",
            "label": '{"note_id": "note-1", "question_text": "Q1", "answer_text": "A1", "question_type": "open", "review_count": 0}',
            "created_at": "2024-01-01T00:00:00+00:00",
        },
        {
            "id": "prompt-2",
            "type": "recall_prompt",
            "label": '{"note_id": "note-2", "question_text": "Q2", "answer_text": "A2", "question_type": "cloze", "review_count": 2}',
            "created_at": "2024-01-02T00:00:00+00:00",
        },
    ]

    questions = await generator.get_due_questions(limit=10)

    assert len(questions) == 2
    mock_graph_db.get_nodes_by_type.assert_called_once_with("recall_prompt")

    # Should be sorted by review_count (fewer reviews first)
    assert questions[0].review_count == 0
    assert questions[1].review_count == 2


@pytest.mark.asyncio
async def test_get_due_questions_respects_limit(generator, mock_graph_db):
    """Test that get_due_questions respects the limit parameter."""
    mock_graph_db.get_nodes_by_type.return_value = [
        {
            "id": f"prompt-{i}",
            "type": "recall_prompt",
            "label": f'{{"note_id": "note-{i}", "question_text": "Q{i}", "answer_text": "A{i}", "question_type": "open", "review_count": {i}}}',
            "created_at": f"2024-01-0{i}T00:00:00+00:00",
        }
        for i in range(1, 6)
    ]

    questions = await generator.get_due_questions(limit=3)

    assert len(questions) == 3


@pytest.mark.asyncio
async def test_get_due_questions_invalid_json(generator, mock_graph_db):
    """Test handling of invalid JSON in graph database."""
    mock_graph_db.get_nodes_by_type.return_value = [
        {
            "id": "prompt-1",
            "type": "recall_prompt",
            "label": "invalid json",
            "created_at": "2024-01-01T00:00:00+00:00",
        },
        {
            "id": "prompt-2",
            "type": "recall_prompt",
            "label": '{"note_id": "note-2", "question_text": "Q2", "answer_text": "A2", "question_type": "open", "review_count": 0}',
            "created_at": "2024-01-01T00:00:00+00:00",
        },
    ]

    questions = await generator.get_due_questions()

    assert len(questions) == 1
    assert questions[0].id == "prompt-2"


def test_add_recall_section(generator):
    """Test adding recall section template to digest."""
    digest = "# Daily Digest\n\nSome content here."

    result = generator.add_recall_section(digest)

    assert "## Active Recall" in result
    assert "Test your understanding" in result
    assert "retrieval practice strengthens memory" in result
    assert "Some content here." in result


@pytest.mark.asyncio
async def test_format_recall_section(generator):
    """Test formatting recall questions as markdown."""
    questions = [
        RecallPrompt(
            id="p1",
            note_id="n1",
            question_text="What is active recall?",
            answer_text="A learning technique.",
            question_type="open",
            created_at=datetime.now(timezone.utc).isoformat(),
            review_count=0,
        ),
        RecallPrompt(
            id="p2",
            note_id="n2",
            question_text="The [[Ebbinghaus]] curve shows memory decay.",
            answer_text="Ebbinghaus",
            question_type="cloze",
            created_at=datetime.now(timezone.utc).isoformat(),
            review_count=1,
            metadata={"hint": "German psychologist"},
        ),
    ]

    markdown = await generator.format_recall_section(questions)

    assert "## Active Recall" in markdown
    assert "Q1: OPEN" in markdown
    assert "Q2: CLOZE" in markdown
    assert "What is active recall?" in markdown
    assert "Click to reveal answer" in markdown
    assert "A learning technique." in markdown
    assert "Hint: German psychologist" in markdown


@pytest.mark.asyncio
async def test_format_recall_section_empty(generator):
    """Test formatting with empty questions list."""
    markdown = await generator.format_recall_section([])

    assert markdown == ""


@pytest.mark.asyncio
async def test_format_recall_section_with_choice(generator):
    """Test formatting multiple choice questions."""
    questions = [
        RecallPrompt(
            id="p1",
            note_id="n1",
            question_text="How much more effective is active recall?",
            answer_text="50-100%",
            question_type="choice",
            created_at=datetime.now(timezone.utc).isoformat(),
            review_count=0,
            metadata={"distractors": ["10-20%", "25-50%", "200-300%"]},
        ),
    ]

    markdown = await generator.format_recall_section(questions)

    assert "CHOICE" in markdown
    assert "Distractors:" in markdown
    assert "10-20%" in markdown


def test_recall_prompt_dataclass():
    """Test RecallPrompt dataclass creation."""
    prompt = RecallPrompt(
        id="test-id",
        note_id="note-1",
        question_text="Test question?",
        answer_text="Test answer.",
        question_type="open",
        created_at="2024-01-01T00:00:00+00:00",
    )

    assert prompt.id == "test-id"
    assert prompt.note_id == "note-1"
    assert prompt.question_text == "Test question?"
    assert prompt.answer_text == "Test answer."
    assert prompt.question_type == "open"
    assert prompt.review_count == 0
    assert prompt.metadata == {}


def test_cloze_deletion_dataclass():
    """Test ClozeDeletion dataclass creation."""
    cloze = ClozeDeletion(
        id="test-id",
        note_id="note-1",
        full_text="The quick brown fox.",
        cloze_text="The [[quick]] brown fox.",
        answer="quick",
        hint="opposite of slow",
    )

    assert cloze.id == "test-id"
    assert cloze.note_id == "note-1"
    assert cloze.full_text == "The quick brown fox."
    assert cloze.cloze_text == "The [[quick]] brown fox."
    assert cloze.answer == "quick"
    assert cloze.hint == "opposite of slow"
    assert cloze.created_at is not None
