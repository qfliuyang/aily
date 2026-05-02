<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# frameworks

## Purpose

Individual innovation framework implementations. Each framework extends `FrameworkAnalyzer` and implements `analyze(payload) -> FrameworkInsight`. Used by `ReactorScheduler` to generate innovation proposals from DIKIWI context.

## Key Files

| File | Description |
|------|-------------|
| `base.py` | `FrameworkAnalyzer` ABC — `analyze()`, `get_system_prompt()`, `framework_type` |
| `triz.py` | TRIZ — systematic inventive problem solving (40 principles, contradictions) |
| `first_principles.py` | First Principles — deconstruct to fundamentals, rebuild from ground up |
| `blue_ocean.py` | Blue Ocean Strategy — Four Actions + Six Paths for market creation |
| `scamper.py` | SCAMPER — Substitute, Combine, Adapt, Modify, Put, Eliminate, Reverse |
| `six_hats.py` | Six Thinking Hats — parallel thinking (white, red, black, yellow, green, blue) |
| `sit.py` | Systematic Inventive Thinking — five patterns (subtraction, multiplication, etc.) |
| `biomimicry.py` | Biomimicry — nature-inspired innovation patterns |
| `morphological.py` | Morphological Analysis — multi-dimensional solution space mapping |
| `mckinsey.py` | McKinsey-style structured analysis (MECE, issue trees) |
| `gstack.py` | GStack framework — builder-focused innovation methodology |

## For AI Agents

### Working In This Directory
- New frameworks: extend `FrameworkAnalyzer`, implement `analyze()` and `get_system_prompt()`
- Register in `ReactorScheduler._get_analyzer()` to be picked up
- Each framework makes 1-7 internal LLM calls (e.g., Blue Ocean runs 4 actions + 3 paths)
- Frameworks run in parallel via `asyncio.gather()` in the Reactor scheduler

### Common Patterns
- Input: `KnowledgePayload` or dict with `focus_areas`, `recent_insights`
- Output: `FrameworkInsight` with proposals, confidence scores, metadata
- LLM calls use the shared `llm_client` passed at init
- Exceptions caught per-method to allow other methods to continue

## Dependencies

### Internal
- `aily/thinking/models.py` — `FrameworkInsight`, `FrameworkType`, `KnowledgePayload`
- `aily/sessions/reactor_scheduler.py` — `InnovationMethod`, `MethodResult`
- `aily/sessions/models.py` — `Proposal`, `ProposalType`

<!-- MANUAL: -->
