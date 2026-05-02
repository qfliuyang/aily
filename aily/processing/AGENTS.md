<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# processing

## Purpose

Universal content processing router and processors. Detects file/content types and routes to the appropriate processor (PDF, image, docx, markdown, CSV, web).

## Key Files

| File | Description |
|------|-------------|
| `router.py` | `ProcessingRouter` — detects type, dispatches to processor |
| `detector.py` | `ContentTypeDetector` — MIME-type and extension detection |
| `processors.py` | `ContentProcessor` implementations for each file type |
| `markdownize.py` | Converts various formats to normalized markdown |
| `atomicizer.py` | Splits large content into atomic chunks |

## For AI Agents

### Working In This Directory
- New file type: extend `ContentProcessor` and register in router
- `ProcessingRouter.route()` returns the right processor for a path/URL
- `atomicizer.py` is used by DIKIWI DATA stage for chunking

### Common Patterns
- Content type detection: extension → MIME → content sniffing
- Each processor implements `process(path) → ExtractedContent`
- Markdown is the common interchange format

## Dependencies

### Internal
- `aily/chaos/` — Chaos processors for complex document types
- `aily/parser/` — URL parsers for web content

### External
- `python-magic` — MIME type detection

<!-- MANUAL: -->
