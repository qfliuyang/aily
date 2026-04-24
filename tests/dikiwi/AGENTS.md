<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# dikiwi

## Purpose

Unit and integration tests for the DIKIWI pipeline and agents. Covers all 6 stages, events, gates, memorials, skills, and the residual agent.

## Key Files

| File | Description |
|------|-------------|
| `test_stages.py` | Tests for DIKIWI stage enum and stage transitions |
| `test_integration.py` | Integration tests for full agent pipeline |
| `test_events.py` | Event bus publish/subscribe tests |
| `test_gates.py` | CVO/Menxia gating logic tests |
| `test_memorials.py` | Persistent memory storage tests |
| `test_skills.py` | Skill registry and built-in skill tests |
| `test_residual_agent.py` | Residual/MAC loop agent tests |
| `test_network_synthesis.py` | Network/graph-triggered synthesis tests |
| `test_graph_synthesis_agents.py` | Graph-driven synthesis agent tests |
| `conftest.py` | Shared fixtures for DIKIWI tests |

## For AI Agents

### Working In This Directory
- `conftest.py` provides mock LLM clients and test contexts
- Integration tests may be slow (they call real LLMs if configured)
- Use `pytest -m "not slow"` to skip LLM-dependent tests

### Testing Requirements
- Run with: `pytest tests/dikiwi/ -xvs`
- Some tests require `KIMI_API_KEY` or `ZHIPU_API_KEY`

## Dependencies

### Internal
- `aily/dikiwi/` — DIKIWI pipeline under test

<!-- MANUAL: -->
