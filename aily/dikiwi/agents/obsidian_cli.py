"""ObsidianCLI helper - wraps the official obsidian-cli tool."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class ObsidianCLI:
    """Wrapper for the official obsidian-cli command-line tool.

    Gracefully degrades to empty results + warnings if obsidian-cli
    is not installed or the Obsidian desktop app is not running.
    """

    def __init__(self, cli_path: str | None = None) -> None:
        self._cli_path = cli_path or "obsidian-cli"
        self._available: bool | None = None

    def _is_available(self) -> bool:
        if self._available is None:
            self._available = shutil.which(self._cli_path) is not None
            if not self._available:
                logger.warning(
                    "[ObsidianCLI] obsidian-cli not found at '%s'. "
                    "Vault-dependent features will be disabled.",
                    self._cli_path,
                )
        return self._available

    def _run(self, *args: str) -> tuple[bool, str]:
        if not self._is_available():
            return False, "obsidian-cli not available"

        cmd = [self._cli_path, *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                err = result.stderr.strip() or f"exit code {result.returncode}"
                logger.warning("[ObsidianCLI] Command failed: %s -> %s", " ".join(cmd), err)
                return False, err
            return True, result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.warning("[ObsidianCLI] Command timed out: %s", " ".join(cmd))
            return False, "timeout"
        except Exception as exc:
            logger.warning("[ObsidianCLI] Command error: %s -> %s", " ".join(cmd), exc)
            return False, str(exc)

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Run obsidian-cli search and parse JSON results."""
        ok, out = self._run("search", query, "--limit", str(limit), "--json")
        if not ok:
            return []
        try:
            data = json.loads(out)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("results", []) or data.get("data", [])
            return []
        except json.JSONDecodeError:
            logger.warning("[ObsidianCLI] Failed to parse search JSON")
            return []

    def read_note(self, path: str) -> str:
        """Read a note by vault path via obsidian-cli read."""
        ok, out = self._run("read", path)
        return out if ok else ""

    def eval_javascript(self, script: str) -> Any:
        """Run arbitrary JavaScript inside Obsidian via obsidian-cli eval."""
        ok, out = self._run("eval", script, "--json")
        if not ok:
            return None
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return out

    def list_tags(self) -> list[str]:
        """List all tags in the vault via obsidian-cli eval."""
        script = (
            "const tags = app.metadataCache.getTags(); "
            "Object.keys(tags).map(t => t.replace('#', ''))"
        )
        result = self.eval_javascript(script)
        if isinstance(result, list):
            return [str(t).strip("#") for t in result if t]
        return []

    def get_backlinks(self, path: str) -> list[str]:
        """Get backlink paths for a given note via obsidian-cli eval."""
        script = (
            f"const file = app.vault.getAbstractFileByPath('{path}'); "
            "if (!file) return []; "
            "const cache = app.metadataCache.getFileCache(file); "
            "(cache && cache.links || []).map(l => l.link)"
        )
        result = self.eval_javascript(script)
        if isinstance(result, list):
            return [str(r) for r in result if r]
        return []
