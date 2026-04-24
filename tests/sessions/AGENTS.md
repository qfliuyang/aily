<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# sessions

## Purpose

Tests for the Three-Mind schedulers and session management. Covers DikiwiMind, InnolavalScheduler, EntrepreneurScheduler, and their supporting components.

## Key Files

| File | Description |
|------|-------------|
| `test_dikiwi_mind.py` | DIKIWI Mind pipeline orchestration tests |
| `test_dikiwi_layers.py` | Layer/budget management tests |
| `test_dikiwi_budget.py` | Token budget and reservation tests |
| `test_dikiwi_wisdom.py` | WISDOM stage-specific tests |
| `test_dikiwi_markdownize.py` | Markdown normalization tests |
| `test_dikiwi_prompt_registry.py` | Prompt template tests |
| `test_entrepreneur_scheduler.py` | Entrepreneur Mind scheduler tests |
| `test_reactor_scheduler.py` | Reactor/MAC loop scheduler tests |
| `test_models.py` | Session data model tests |
| `test_base.py` | Base session test utilities |
| `test_dikiwi_batch_mode.py` | Batch mode DIKIWI pipeline tests |
| `test_dikiwi_data_information.py` | DATA → INFORMATION stage tests |

## For AI Agents

### Working In This Directory
- Tests cover the most complex orchestration logic in Aily
- Budget tests verify token accounting across stages
- Scheduler tests may mock LLM calls for speed

### Testing Requirements
- Run with: `pytest tests/sessions/ -xvs`
- Some tests require API keys for full validation

## Dependencies

### Internal
- `aily/sessions/` — Mind schedulers under test

<!-- MANUAL: -->
