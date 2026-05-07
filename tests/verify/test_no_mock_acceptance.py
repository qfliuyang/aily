from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_DIR = REPO_ROOT / "tests" / "e2e"
TEST_DIR = REPO_ROOT / "tests"
FORBIDDEN_NAMES = {"Mock", "MagicMock", "AsyncMock", "patch"}


def acceptance_candidate_files() -> list[Path]:
    """Files that can provide acceptance evidence and must avoid mocks/fakes."""

    files = set(E2E_DIR.rglob("*.py"))
    for path in TEST_DIR.rglob("test_*.py"):
        if "tests/verify" in str(path.relative_to(REPO_ROOT)):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "pytest.mark.acceptance" in text or "pytestmark = pytest.mark.acceptance" in text:
            files.add(path)
    return sorted(files)

pytestmark = pytest.mark.contract


def test_e2e_tests_do_not_import_unittest_mock() -> None:
    offenders: list[str] = []
    for path in acceptance_candidate_files():
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
    for path in acceptance_candidate_files():
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


def test_global_acceptance_guard_is_autouse_and_marker_gated() -> None:
    conftest = REPO_ROOT / "tests" / "conftest.py"
    tree = ast.parse(conftest.read_text(encoding="utf-8"), filename=str(conftest))
    guard = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "enforce_acceptance_boundary_manifest"
    )

    decorator_calls = [decorator for decorator in guard.decorator_list if isinstance(decorator, ast.Call)]
    assert any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "fixture"
        and any(keyword.arg == "autouse" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in call.keywords)
        for call in decorator_calls
    )
    assert any(isinstance(node, ast.Constant) and node.value == "acceptance" for node in ast.walk(guard))
    assert any(isinstance(node, ast.Attribute) and node.attr == "get_closest_marker" for node in ast.walk(guard))
    assert any(isinstance(node, ast.Attribute) and node.attr == "getfixturevalue" for node in ast.walk(guard))


def test_acceptance_manifest_rejects_local_substitutions_behaviorally() -> None:
    from tests.support.acceptance import AcceptanceBoundaryManifest

    manifest = AcceptanceBoundaryManifest(
        real_llm=True,
        real_graph_db=True,
        real_queue_worker=True,
        real_writer_api=False,
        real_http=True,
        fake_components=["obsidian_writer"],
    )

    assert manifest.acceptance_ready is False


def test_acceptance_candidate_files_include_marker_global_tests() -> None:
    candidates = acceptance_candidate_files()

    assert any(path.name == "test_acceptance_manifest.py" for path in candidates)
