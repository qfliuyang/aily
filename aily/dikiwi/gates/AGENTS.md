<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# gates

## Purpose

Gating subsystem for DIKIWI — controls the flow of content through validation checkpoints. Named after ancient Chinese gatekeeping offices (CVO/Menxia) for content quality control.

## Key Files

| File | Description |
|------|-------------|
| `cvo.py` | Content validation and quality gating |
| `menxia.py` | Menxia gate — secondary review checkpoint |

## For AI Agents

### Working In This Directory
- Gates intercept content between DIKIWI stages
- `CVO` validates content meets quality thresholds before passing
- `Menxia` provides secondary review for edge cases
- Gates can block, modify, or approve content

### Common Patterns
- Gate checks return `Pass`, `Block`, or `Modify`
- Each gate has configurable thresholds
- Failed gates log reasons for audit

## Dependencies

### Internal
- `aily/dikiwi/agents/` — Agent stage results feed into gates
- `aily/llm/` — LLM-based quality scoring

<!-- MANUAL: -->
