<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# skills

## Purpose

Skill framework for DIKIWI. Skills are modular, versioned capabilities that can be loaded on-demand by agents. Provides a plugin-like architecture for extending agent behavior.

## Key Files

| File | Description |
|------|-------------|
| `base.py` | `Skill` abstract base, `SkillContext`, `SkillResult` |
| `registry.py` | `SkillRegistry` — discovery and loading of skills |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `builtin/` | Built-in skills: pattern detection, synthesis, tag extraction |

## For AI Agents

### Working In This Directory
- New skills: extend `Skill` base class and register in `SkillRegistry`
- Skills receive `SkillContext` with LLM, GraphDB, and content access
- Built-in skills are auto-registered; custom skills can be loaded dynamically

### Common Patterns
- Skills declare `name`, `version`, and `required_capabilities`
- `execute(ctx) → SkillResult` is the main entry point
- Skills can call other skills via the registry

## Dependencies

### Internal
- `aily/llm/` — LLM for skill reasoning
- `aily/graph/` — GraphDB for skill state

<!-- MANUAL: -->
