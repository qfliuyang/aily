from __future__ import annotations

import json
from pathlib import Path

from aily.llm.prompt_registry import DikiwiPromptRegistry


ARTIFACT_DIR = Path("test-artifacts/prompt-regression")


def _save_case(name: str, messages: list[dict[str, str]], rubric: dict[str, int]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / f"{name}.json").write_text(
        json.dumps({"messages": messages, "rubric": rubric}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _score_prompt(text: str) -> dict[str, int]:
    checks = {
        "schema_contract": int("JSON" in text),
        "evidence_grounding": int("evidence" in text.lower() or "source" in text.lower()),
        "graph_grounding": int("graph" in text.lower() or "node" in text.lower() or "edge" in text.lower()),
        "innovation_quality": int("innovation" in text.lower() or "proposal" in text.lower() or "impact" in text.lower()),
    }
    checks["total"] = sum(checks.values())
    return checks


def test_prompt_regression_saves_input_output_pair_for_impact() -> None:
    messages = DikiwiPromptRegistry.impact(
        zettels_desc="Long-path wisdom connects EDA verification bottlenecks with evidence-backed agent workflows and graph center node n1.",
        memory_context="",
    )
    text = "\n\n".join(message["content"] for message in messages)
    score = _score_prompt(text)
    _save_case("impact", messages, score)

    assert score["schema_contract"] == 1
    assert score["evidence_grounding"] == 1
    assert score["graph_grounding"] == 1
    assert score["innovation_quality"] == 1


def test_prompt_regression_saves_input_output_pair_for_residual() -> None:
    messages = DikiwiPromptRegistry.residual_synthesis(
        vault_excerpts="06-Impact contains a central EDA agent workflow opportunity.",
        graph_nodes="impact:n1 -> wisdom:n2",
        reactor_proposals="TRIZ and GStack both found contradiction pressure.",
        memory_context="",
    )
    text = "\n\n".join(message["content"] for message in messages)
    score = _score_prompt(text)
    _save_case("residual", messages, score)

    assert score["total"] >= 3
