<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# llm

## Purpose

Tests for the LLM abstraction layer. Verifies provider routing, client initialization, and prompt formatting across different LLM backends.

## Key Files

| File | Description |
|------|-------------|
| `test_provider_routes.py` | Tests for `PrimaryLLMRoute` and provider selection |

## For AI Agents

### Working In This Directory
- Tests verify correct provider selection based on settings
- Mock responses avoid real API calls in unit tests
- Provider routing tests cover Kimi, Zhipu, and fallback logic

### Testing Requirements
- Run with: `pytest tests/llm/ -xvs`

## Dependencies

### Internal
- `aily/llm/` — LLM layer under test

<!-- MANUAL: -->
