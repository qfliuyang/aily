<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# chaos

## Purpose

Chaos is the file-watching and document extraction subsystem. It monitors `~/aily_chaos/` for dropped files (PDF, images, video, documents), extracts their content using the appropriate processor, tags them, and bridges the results into the DIKIWI pipeline.

## Key Files

| File | Description |
|------|-------------|
| `config.py` | `ChaosConfig` dataclass — all chaos settings including MinerU config |
| `processor.py` | `ChaosProcessor` — main orchestrator: validate → detect → extract → tag → save |
| `types.py` | `ExtractedContentMultimodal`, `ProcessingJob`, `ProcessingStatus`, `VisualElement` |
| `watcher.py` | `FileWatcher` — uses `watchfiles` to detect new files |
| `dikiwi_bridge.py` | `ChaosDikiwiBridge` — connects extracted content to DIKIWI pipeline |
| `mineru_batch.py` | `MinerUChaosBatchRunner` — batch ingest folder through MinerU → DIKIWI |
| `queue_processor.py` | Queue-based processing for daemon mode |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `processors/` | Document extraction engines — PDF, image, video, MinerU, Docling (see `processors/AGENTS.md`) |
| `tagger/` | Content tagging engine — content-based + LLM-based |

## For AI Agents

### Working In This Directory
- Processors must implement `ContentProcessor` base class from `processors/base.py`
- `can_process()` gates which processor handles a file
- Extraction results are `ExtractedContentMultimodal` with text, title, visual elements, metadata
- The `ChaosProcessor` routes by MIME type; `mineru_processor.py` handles Office docs

### Testing Requirements
- `tests/chaos/` has processor tests
- MinerU tests need `mineru` CLI installed or mock the API

### Common Patterns
- Processors are instantiated per-call with config + optional LLM client
- `TextProcessor` normalizes markdown output from all extraction backends
- Cache directory keyed by file path + size + mtime hash

## Dependencies

### Internal
- `aily/dikiwi/` — bridge feeds into DIKIWI pipeline
- `aily/llm/` — LLM client for tagging and visual analysis
- `aily/graph/` — GraphDB for knowledge graph entries

### External
- `watchfiles` — File system watching
- `pdfplumber` — PDF text extraction fallback
- `pdf2image` — PDF page to image conversion
- `magic` / `python-magic` — MIME type detection

<!-- MANUAL: -->
