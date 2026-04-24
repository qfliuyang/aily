<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# synthesis

## Purpose

Synthesis engine that merges insights from multiple innovation frameworks into cross-framework synthesized proposals. Adaptive: pass-through for 1 framework, cross-validation for 2, full synthesis for 3+.

## Key Files

| File | Description |
|------|-------------|
| `engine.py` | `SynthesisEngine` — merges `FrameworkInsight` outputs, resolves conflicts, ranks by confidence |

## For AI Agents

### Working In This Directory
- `SynthesisEngine` takes a list of `FrameworkInsight` from different frameworks
- Adaptive behavior: 1 framework → normalize, 2 → cross-validate & resolve conflicts, 3+ → full synthesis
- Outputs `SynthesizedInsight` with merged proposals, confidence scores, and supporting framework citations
- Conflict detection: identifies contradictory proposals across frameworks and resolves via LLM

### Common Patterns
- Priority ranking: cross-framework consensus > single-framework high-confidence
- Redundancy removal: deduplicates similar proposals from different frameworks
- Confidence scoring: combines individual framework scores with cross-validation signals

## Dependencies

### Internal
- `aily/thinking/models.py` — `FrameworkInsight`, `SynthesizedInsight`, `InsightPriority`
- `aily/thinking/frameworks/` — Framework outputs feed into synthesis
- `aily/llm/` — LLM for conflict resolution and synthesis

<!-- MANUAL: -->
