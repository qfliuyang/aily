from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_DIR = REPO_ROOT / "tests" / "e2e"
FORBIDDEN_NAMES = {"Mock", "MagicMock", "AsyncMock", "patch"}


def test_e2e_tests_do_not_import_unittest_mock() -> None:
    offenders: list[str] = []
    for path in sorted(E2E_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "unittest.mock":
                offenders.append(f"{path.relative_to(REPO_ROOT)} imports unittest.mock")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "unittest.mock":
                        offenders.append(f"{path.relative_to(REPO_ROOT)} imports unittest.mock")

    assert offenders == []


def test_e2e_tests_do_not_use_mock_symbols_or_fake_fixtures() -> None:
    offenders: list[str] = []
    for path in sorted(E2E_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(REPO_ROOT)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
                offenders.append(f"{rel} uses {node.id}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                lowered = node.name.lower()
                if "mock" in lowered or "fake" in lowered:
                    offenders.append(f"{rel} defines {node.name}")

    assert offenders == []
