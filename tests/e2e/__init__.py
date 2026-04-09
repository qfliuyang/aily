"""End-to-end tests for Aily.

These tests exercise complete user workflows:
1. Real database operations (SQLite on disk)
2. Real file system operations (temp directories)
3. Real LLM calls (when configured)
4. Real network calls (when configured)

NO MOCKS. Tests expose problems, not hide them.
"""
