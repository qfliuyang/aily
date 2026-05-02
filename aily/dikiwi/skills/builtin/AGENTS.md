<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# builtin

## Purpose

Built-in skills for the DIKIWI skill framework. Auto-registered skills that provide core capabilities: pattern detection, synthesis, and tag extraction.

## Key Files

| File | Description |
|------|-------------|
| `pattern_detection.py` | Detects recurring patterns across knowledge nodes |
| `synthesis.py` | Synthesizes multiple nodes into higher-level insights |
| `tag_extraction.py` | Extracts and normalizes tags from content |

## For AI Agents

### Working In This Directory
- Built-in skills are loaded automatically by `SkillRegistry`
- Each skill extends the `Skill` base class from `aily/dikiwi/skills/base.py`
- Skills are pure functions: input `SkillContext`, output `SkillResult`

### Common Patterns
- Pattern detection uses GraphDB queries to find recurring structures
- Synthesis calls LLM with multiple source nodes
- Tag extraction normalizes tags to a controlled vocabulary

## Dependencies

### Internal
- `aily/dikiwi/skills/base.py` — Skill base class
- `aily/graph/` — GraphDB for pattern queries
- `aily/llm/` — LLM for synthesis

<!-- MANUAL: -->
