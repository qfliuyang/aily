<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# thinking

## Purpose

Innovation framework engine. Provides 11 structured thinking frameworks (TRIZ, First Principles, Blue Ocean, SCAMPER, Biomimicry, McKinsey, SIT, Six Hats, Morphological, GStack) that the Innolaval scheduler runs on DIKIWI context to generate proposals.

## Key Files

| File | Description |
|------|-------------|
| `config.py` | `ThinkingConfig` — framework weights and thresholds |
| `models.py` | `KnowledgePayload`, `FrameworkInsight`, `SynthesisResult` |
| `orchestrator.py` | `ThinkingOrchestrator` — runs all frameworks, scores, ranks |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `frameworks/` | Individual framework implementations — 11 strategies |
| `integration/` | GraphDB, LLM, queue, output integration layers |
| `synthesis/` | `SynthesisEngine` — combines framework outputs into final report |

## For AI Agents

### Working In This Directory
- New frameworks: extend `BaseFramework` in `frameworks/base.py`
- Each framework implements `analyze(payload) -> FrameworkInsight`
- `ThinkingOrchestrator` runs all frameworks in parallel
- Synthesis engine scores and ranks insights by confidence

### Common Patterns
- Frameworks are pure functions: input `KnowledgePayload`, output `FrameworkInsight`
- Confidence scores range 0.0–1.0
- Top insights feed into Residual agent for proposal drafting

## Dependencies

### Internal
- `aily/llm/` — LLM client for framework analysis
- `aily/graph/` — GraphDB for context queries

<!-- MANUAL: -->
