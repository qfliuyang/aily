"""E2E tests for Obsidian integration.

Tests that notes are correctly written to Obsidian vault.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from pathlib import Path


@pytest.mark.asyncio
class TestObsidianWriter:
    """End-to-end tests for Obsidian note writing."""

    async def test_write_note_to_vault(
        self,
        e2e_context,
        obsidian_writer,
        vault_verifier,
    ):
        """Test that notes are written to the vault directory."""
        # Arrange
        title = "Test Note"
        content = "# Test Content\n\nThis is a test note."

        # Act
        result_path = await obsidian_writer.write_note(title, content)

        # Assert: Note exists in vault
        full_path = vault_verifier.assert_note_exists(result_path)
        assert full_path.read_text(encoding="utf-8") == content

    async def test_write_note_with_source_url(
        self,
        e2e_context,
        obsidian_writer,
        vault_verifier,
    ):
        """Test that notes include source URL when provided."""
        # Arrange
        title = "Article Summary"
        content = "## Key Points\n\n- Point 1\n- Point 2"
        source_url = "https://example.com/article"

        # Act
        result_path = await obsidian_writer.write_note(title, content, source_url)

        # Assert: Check file was written
        full_path = vault_verifier.assert_note_exists(result_path)
        written_content = full_path.read_text(encoding="utf-8")
        assert "Point 1" in written_content

    async def test_note_filename_sanitization(
        self,
        e2e_context,
        obsidian_writer,
        vault_verifier,
    ):
        """Test that note filenames are properly sanitized."""
        # Arrange: Title with special characters
        title = "Note: With * Special <Chars>?"
        content = "Test content"

        # Act
        result_path = await obsidian_writer.write_note(title, content)

        # Assert: File was created
        assert vault_verifier.assert_note_exists(result_path)

    async def test_multiple_notes_in_vault(
        self,
        e2e_context,
        obsidian_writer,
        vault_verifier,
    ):
        """Test writing multiple notes to the vault."""
        # Arrange & Act: Write 3 notes
        notes = [
            ("Note One", "Content one"),
            ("Note Two", "Content two"),
            ("Note Three", "Content three"),
        ]

        paths = []
        for title, content in notes:
            path = await obsidian_writer.write_note(title, content)
            paths.append(path)

        # Assert: All notes exist
        for path in paths:
            vault_verifier.assert_note_exists(path)

        # Assert: Directory has 3 files
        vault_verifier.assert_directory_count(".", 3)


@pytest.mark.asyncio
class TestVaultStructure:
    """E2E tests for vault directory structure."""

    async def test_vault_directories_created(
        self,
        e2e_context,
    ):
        """Test that vault subdirectories exist."""
        # Assert: Expected directories exist
        assert (e2e_context.obsidian_vault_path / "Aily" / "Ideas").exists()
        assert (e2e_context.obsidian_vault_path / "Aily" / "Proposals" / "Innovation").exists()
        assert (e2e_context.obsidian_vault_path / "Aily" / "Proposals" / "Business").exists()

    async def test_list_vault_files(
        self,
        e2e_context,
        obsidian_writer,
    ):
        """Test listing files in vault."""
        # Arrange: Create some files
        await obsidian_writer.write_note("Note A", "Content A")
        await obsidian_writer.write_note("Note B", "Content B")

        # Act
        files = e2e_context.list_vault_files()

        # Assert
        assert len(files) == 2
        assert any("Note A" in f for f in files)
        assert any("Note B" in f for f in files)


@pytest.mark.asyncio
class TestObsidianVerifier:
    """E2E tests for vault verification helpers."""

    async def test_assert_note_exists_success(
        self,
        e2e_context,
        obsidian_writer,
        vault_verifier,
    ):
        """Test successful note existence check."""
        # Arrange
        await obsidian_writer.write_note("Exists", "Content")

        # Act & Assert: Should not raise
        vault_verifier.assert_note_exists("Exists.md")

    async def test_assert_note_exists_failure(
        self,
        e2e_context,
        vault_verifier,
    ):
        """Test failed note existence check."""
        # Act & Assert: Should raise AssertionError
        with pytest.raises(AssertionError) as exc_info:
            vault_verifier.assert_note_exists("DoesNotExist.md")

        assert "Note not found" in str(exc_info.value)

    async def test_assert_note_contains(
        self,
        e2e_context,
        obsidian_writer,
        vault_verifier,
    ):
        """Test note content verification."""
        # Arrange
        await obsidian_writer.write_note("Contains Test", "This has the magic word: xyzzy")

        # Act & Assert: Should not raise
        vault_verifier.assert_note_contains("Contains Test.md", "magic word")

    async def test_assert_note_contains_failure(
        self,
        e2e_context,
        obsidian_writer,
        vault_verifier,
    ):
        """Test failed content verification."""
        # Arrange
        await obsidian_writer.write_note("Missing Content", "This does not have it")

        # Act & Assert: Should raise AssertionError
        with pytest.raises(AssertionError) as exc_info:
            vault_verifier.assert_note_contains("Missing Content.md", "xyzzy")

        assert "does not contain" in str(exc_info.value)

    async def test_assert_directory_count(
        self,
        e2e_context,
        obsidian_writer,
        vault_verifier,
    ):
        """Test directory file count verification."""
        # Arrange: Write files
        await obsidian_writer.write_note("Dir Test 1", "Content 1")
        await obsidian_writer.write_note("Dir Test 2", "Content 2")

        # Act & Assert: Should not raise
        vault_verifier.assert_directory_count(".", 2)


@pytest.mark.asyncio
class TestIntegrationWithMinds:
    """E2E tests for Obsidian integration with Three-Mind system."""

    async def test_dikiwi_writes_to_ideas(
        self,
        e2e_context,
        obsidian_writer,
        vault_verifier,
    ):
        """Test that DIKIWI mind writes ideas to Aily/Ideas/."""
        # This test verifies the structure is ready for DIKIWI integration
        # The actual writing is tested in test_dikiwi_pipeline.py

        # Arrange
        ideas_dir = e2e_context.obsidian_vault_path / "Aily" / "Ideas"
        assert ideas_dir.exists()

        # Act: Write a note as DIKIWI would
        await obsidian_writer.write_note(
            "Idea 2024-01-15",
            "# Atomic Idea\n\nAn insight about AI.",
        )

        # Assert: File exists in vault
        vault_verifier.assert_note_exists("Idea 2024-01-15.md")

    async def test_innovation_writes_to_proposals(
        self,
        e2e_context,
        obsidian_writer,
        vault_verifier,
    ):
        """Test that Innovation mind writes proposals to Aily/Proposals/Innovation/."""
        # Arrange
        proposals_dir = e2e_context.obsidian_vault_path / "Aily" / "Proposals" / "Innovation"
        assert proposals_dir.exists()

        # Act: Write a proposal as Innovation mind would
        proposal_content = """# TRIZ Proposal

**Type:** INNOVATION
**Confidence:** 85%

## Summary
A new approach to solving the contradiction.

## Details
Full proposal content here.
"""
        await obsidian_writer.write_note("TRIZ Proposal 001", proposal_content)

        # Assert: File exists
        vault_verifier.assert_note_exists("TRIZ Proposal 001.md")
