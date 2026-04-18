<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# processors

## Purpose

Document extraction engines. Each processor handles a specific file type or extraction backend, converting raw files into `ExtractedContentMultimodal`.

## Key Files

| File | Description |
|------|-------------|
| `base.py` | `ContentProcessor` abstract base class |
| `pdf.py` | `PDFProcessor` — MinerU → Docling → OCR → pdfplumber fallback chain |
| `mineru_processor.py` | `MinerUProcessor` — local MinerU CLI/API for PDF/Office docs |
| `docling_processor.py` | `DoclingProcessor` — Docling for rich document understanding |
| `document.py` | `TextProcessor`, `GenericDocumentProcessor` — markdown/text normalization |
| `image.py` | `ImageProcessor` — OCR and visual analysis |
| `video.py` | `VideoProcessor` — frame extraction + Whisper transcription |
| `pptx.py` | `PPTXProcessor` — PowerPoint slide extraction |

## For AI Agents

### Working In This Directory
- New processors extend `ContentProcessor` and implement `process()` and `can_process()`
- Return `ExtractedContentMultimodal` with text, title, source_type, metadata
- Processors may use LLM client for visual analysis (images, video frames)
- `TextProcessor` is the common normalizer — used by all backends

### Common Patterns
- Fallback chains: primary → secondary → fallback (e.g., PDFProcessor)
- MinerU uses cache directory keyed by file hash
- Image processor bundles multiple images into "sessions"

## Dependencies

### Internal
- `aily/chaos/types.py` — `ExtractedContentMultimodal`
- `aily/llm/` — LLM client for visual analysis

### External
- `pdfplumber` — PDF text fallback
- `pdf2image` — PDF to image
- `PIL` — Image processing
- `docling` — Rich document extraction
- `mineru` — Local document parser

<!-- MANUAL: -->
