<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# thinking

## Purpose

Tests for the innovation thinking frameworks. Covers the 11 structured frameworks used by Innolaval for proposal generation.

## Key Files

| File | Description |
|------|-------------|
| `test_frameworks.py` | Individual framework analyzer tests (TRIZ, SCAMPER, etc.) |
| `test_integration.py` | Thinking-to-DIKIWI integration tests |
| `test_models.py` | KnowledgePayload, FrameworkInsight model tests |
| `test_orchestrator.py` | ThinkingOrchestrator pipeline tests |
| `test_synthesis.py` | Synthesis engine cross-framework tests |

## For AI Agents

### Working In This Directory
- Framework tests are typically in the framework module directories
- This directory serves as the root for thinking-related test collection
- Each framework (TRIZ, SCAMPER, etc.) should have corresponding tests

### Testing Requirements
- Run with: `pytest tests/thinking/ -xvs`

## Dependencies

### Internal
- `aily/thinking/` — Innovation frameworks under test

<!-- MANUAL: -->
