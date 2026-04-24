<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# learning

## Purpose

Continuous learning subsystem. Watches the Obsidian vault for changes, generates spaced-repetition prompts from notes, and manages an SRS (spaced repetition system) for knowledge retention.

## Key Files

| File | Description |
|------|-------------|
| `loop.py` | `LearningLoop` — vault watcher + card generator |
| `srs.py` | SRS scheduler and card review logic |
| `recall.py` | Recall prompt generation from note content |

## For AI Agents

### Working In This Directory
- Uses `watchfiles` to detect vault changes
- Cards are generated from atomic notes and insights
- SRS intervals follow standard SM-2 algorithm

### Common Patterns
- Vault watcher runs in background alongside main app
- New notes trigger card generation asynchronously
- Review schedule persisted in GraphDB

## Dependencies

### Internal
- `aily/graph/` — GraphDB for card scheduling
- `aily/llm/` — LLM for prompt generation
- `aily/writer/` — Obsidian writer for card output

### External
- `watchfiles` — File system watching

<!-- MANUAL: -->
