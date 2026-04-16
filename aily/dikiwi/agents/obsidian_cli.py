"""ObsidianCLI helper - wraps the official obsidian-cli tool."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ObsidianCLI:
    """Wrapper for the official obsidian-cli command-line tool.

    Gracefully degrades to empty results + warnings if obsidian-cli
    is not installed or the Obsidian desktop app is not running.
    """

    def __init__(self, cli_path: str | None = None, vault_name: str | None = None) -> None:
        self._cli_path = cli_path or "obsidian-cli"
        self._vault_name = vault_name
        self._available: bool | None = None

    @staticmethod
    def _sanitize_path(path: str) -> str:
        """Validate and normalize a vault path.

        Rejects directory traversal, absolute paths, null bytes, and backslashes.
        """
        if not path or not isinstance(path, str):
            raise ValueError("Path must be a non-empty string")
        if "\x00" in path:
            raise ValueError("Path contains null bytes")
        if ".." in path:
            raise ValueError("Path contains directory traversal")
        if path.startswith("/"):
            raise ValueError("Path must be relative (no leading slash)")
        if "\\" in path:
            raise ValueError("Path contains backslashes")
        return path

    @staticmethod
    def _escape_js_string(value: str) -> str:
        """Escape a string for safe use in single-quoted JavaScript literals."""
        return value.replace("\\", "\\\\").replace("'", "\\'")

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

        cmd = [self._cli_path]
        if self._vault_name:
            cmd.extend(["--vault", self._vault_name])
        cmd.extend(args)
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
        """Search vault notes matching *query*.

        First tries ``search-content`` with ``--no-interactive --format json``.
        If the installed ``obsidian-cli`` is too old to support those flags
        (e.g. v0.2.x), it falls back to ``eval`` with a JavaScript vault scan.
        """
        ok, out = self._run(
            "search-content", query, "--no-interactive", "--format", "json"
        )
        if ok and out:
            try:
                matches = json.loads(out)
                results: list[dict[str, Any]] = []
                for match in matches[:limit]:
                    if not isinstance(match, dict):
                        continue
                    path = match.get("file") or match.get("path") or ""
                    results.append({"path": path, "label": Path(path).stem if path else ""})
                return results
            except json.JSONDecodeError:
                logger.warning("[ObsidianCLI] Failed to parse search-content JSON output")

        # Fallback for older obsidian-cli versions without --no-interactive
        if "unknown flag" in out.lower() or "no-interactive" in out.lower():
            logger.info("[ObsidianCLI] search-content lacks --no-interactive; falling back to eval")

        safe_query = self._escape_js_string(query)
        script = (
            "const files = app.vault.getFiles(); "
            "const results = []; "
            "const limit = " + str(int(limit)) + "; "
            f"const query = '{safe_query}'.toLowerCase(); "
            "for (const file of files) { "
            "  if (results.length >= limit) break; "
            "  const cache = app.metadataCache.getFileCache(file); "
            "  const fm = cache && cache.frontmatter; "
            "  if (query.endsWith(':') && fm) { "
            "    const key = query.replace(':', ''); "
            "    if (fm[key] !== undefined) { "
            "      results.push({file: file.path}); "
            "      continue; "
            "    } "
            "  } "
            "  const content = app.vault.cachedRead(file); "
            "  if (content && content.toLowerCase().includes(query)) { "
            "    results.push({file: file.path}); "
            "  } "
            "} "
            "JSON.stringify(results)"
        )
        eval_result = self.eval_javascript(script)
        if isinstance(eval_result, str):
            try:
                eval_result = json.loads(eval_result)
            except json.JSONDecodeError:
                logger.warning("[ObsidianCLI] Failed to parse eval JSON output")
                return []
        if isinstance(eval_result, list):
            return [
                {"path": item.get("file", ""), "label": Path(item.get("file", "")).stem}
                for item in eval_result[:limit]
                if item.get("file")
            ]
        return []

    def read_note(self, path: str) -> str:
        """Read a note by vault path via obsidian-cli read."""
        try:
            self._sanitize_path(path)
        except ValueError as exc:
            logger.warning("[ObsidianCLI] Invalid path: %s", exc)
            return ""
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
        try:
            self._sanitize_path(path)
        except ValueError as exc:
            logger.warning("[ObsidianCLI] Invalid path: %s", exc)
            return []
        safe_path = self._escape_js_string(path)
        script = (
            f"const file = app.vault.getAbstractFileByPath('{safe_path}'); "
            "if (!file) return []; "
            "const cache = app.metadataCache.getFileCache(file); "
            "(cache && cache.links || []).map(l => l.link)"
        )
        result = self.eval_javascript(script)
        if isinstance(result, list):
            return [str(r) for r in result if r]
        return []
