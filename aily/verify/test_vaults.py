"""Helpers for locating human-visible test Obsidian vaults."""

from __future__ import annotations

from pathlib import Path


DEFAULT_TEST_VAULTS_DIR = Path.home() / "Documents" / "Aily Test Vaults"


def resolve_test_vault_path(run_id: str, requested: Path | None = None) -> Path:
    """Return a non-hidden Obsidian vault path for evidence/test runs."""
    path = (requested if requested is not None else DEFAULT_TEST_VAULTS_DIR / run_id).expanduser().resolve()
    _reject_hidden_vault_path(path)
    return path


def _reject_hidden_vault_path(path: Path) -> None:
    home = Path.home().resolve()
    documents = home / "Documents"
    parts = path.parts
    hidden_parts = [part for part in parts if part.startswith(".") and part not in {".", ".."}]
    if hidden_parts:
        raise ValueError(f"Test vault path must not be in a hidden directory: {path}")
    try:
        path.relative_to(documents)
    except ValueError:
        raise ValueError(f"Test vault path must be under {documents}: {path}")
