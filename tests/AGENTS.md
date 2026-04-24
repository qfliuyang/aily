<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# tests

## Purpose

Test suite for Aily. Organized by subsystem with unit, integration, and end-to-end tests. pytest.ini configures `asyncio_mode = auto` so async tests run without decorators.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `chaos/` | Chaos processor tests (PDF, image, MinerU, Docling) |
| `dikiwi/` | DIKIWI stage and agent tests |
| `e2e/` | End-to-end pipeline tests — full DIKIWI flow |
| `integration/` | Integration tests with real/external services |
| `llm/` | LLM client and router tests |
| `sessions/` | Scheduler and Three-Mind tests |
| `thinking/` | Innovation framework tests |
| `writer/` | Obsidian writer tests |

## For AI Agents

### Working In This Directory
- Run `pytest -xvs` for verbose, stop-on-first-failure mode
- Skip integration tests with `-k "not integration"`
- Skip slow tests with `-k "not slow"`
- `conftest.py` provides shared fixtures

### Testing Requirements
- Unit tests mock LLM calls
- E2E tests need real API keys (KIMI_API_KEY)
- Integration tests need service dependencies (Feishu, browser service)

## Dependencies

### Internal
- `aily/` — everything under test

### External
- `pytest`, `pytest-asyncio`, `faker`

<!-- MANUAL: -->
