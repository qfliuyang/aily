<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# tagger

## Purpose

Content tagging engine for Chaos-processed documents. Assigns tags based on content analysis (LLM-based or rule-based) to enable vault organization and retrieval.

## Key Files

| File | Description |
|------|-------------|
| `engine.py` | `TaggingEngine` — orchestrates tagging strategies |
| `llm_based.py` | LLM-driven tag extraction from document content |
| `content_based.py` | Rule-based / heuristic tag assignment |

## For AI Agents

### Working In This Directory
- New tagging strategies: add to engine and register
- LLM-based tagging uses the app's configured LLM client
- Content-based uses keyword matching and heuristics

### Common Patterns
- Tagging engine runs after document extraction, before DIKIWI ingestion
- Tags are written to note frontmatter

## Dependencies

### Internal
- `aily/llm/` — LLM client for tag extraction
- `aily/chaos/types.py` — `ExtractedContentMultimodal`

<!-- MANUAL: -->
