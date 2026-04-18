<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# e2e

## Purpose

End-to-end tests for the full Aily system. Tests complete document-to-vault pipelines and Obsidian integration with real or near-real components.

## Key Files

| File | Description |
|------|-------------|
| `test_dikiwi_pipeline.py` | Full DIKIWI pipeline e2e tests |
| `test_obsidian_integration.py` | Obsidian vault write/read tests |
| `conftest.py` | E2E-specific fixtures and helpers |
| `pytest.ini` | E2E test configuration |

## For AI Agents

### Working In This Directory
- E2E tests are the slowest but most comprehensive
- They exercise the full pipeline: document → chaos → DIKIWI → vault
- May use real LLM calls (configurable via env var)
- Vault output is validated for structure and content quality

### Testing Requirements
- Run with: `pytest tests/e2e/ -xvs` (slow)
- Requires valid API keys and Obsidian vault path
- Use `scripts/run_test_suite.py` for batch e2e runs

## Dependencies

### Internal
- `aily/dikiwi/` — Full pipeline
- `aily/writer/` — Obsidian output

<!-- MANUAL: -->
