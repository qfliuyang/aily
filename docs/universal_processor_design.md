# Universal Content Processor Design

> Aily should process **anything** — links, PDFs, images, documents, markdown — without relying on specific parsers like Kimi/Monica.

---

## Philosophy

**Input agnostic**: The user shouldn't think about "what type is this?" They just send it to Aily.

**Unified pipeline**: Everything becomes text → atomic notes → knowledge graph.

**Pluggable processors**: New content types can be added without changing the core flow.

---

## Content Type Detection

Instead of URL regex patterns, detect by:

1. **HTTP Content-Type header** (for URLs)
2. **File extension** (for uploads)
3. **Magic bytes** (file signatures)
4. **Content sniffing** (first N bytes analysis)

```python
# Detection order (fastest to slowest)
ContentTypeDetector.detect(bytes_or_url):
  1. Check magic bytes (pdf: %PDF, png: \x89PNG, etc)
  2. Check file extension
  3. Check HTTP Content-Type
  4. Sniff content (is it HTML? Markdown? Text?)
```

---

## Processor Registry

```python
# Registry pattern - like current parser registry but for content types
processors = {
    "text/html": WebProcessor(),           # Browser/Playwright
    "application/pdf": PDFProcessor(),     # pdfplumber/pymupdf
    "image/*": ImageProcessor(),           # OCR (tesseract/easyocr)
    "text/markdown": MarkdownProcessor(),  # Direct parse
    "application/vnd.openxmlformats-officedocument": DocxProcessor(),
    "text/plain": TextProcessor(),         # Direct pass-through
}
```

---

## The Universal Pipeline

```
User Input (URL, file, text)
        ↓
[Content Type Detector]
        ↓
[Router] → [Specific Processor]
        ↓
Extracted Text (unified format)
        ↓
[Atomicizer] → one idea per note
        ↓
[Connection Suggester] → link to existing notes
        ↓
[GraphDB] + [Obsidian Drafts]
```

---

## Processor Implementations

### 1. WebProcessor (existing browser fetcher)
- Handles: `text/html`, `application/xhtml+xml`
- Method: Playwright/Browser Use
- Output: Clean markdown text

### 2. PDFProcessor (new)
- Handles: `application/pdf`
- Libraries: `pdfplumber` (best for text) or `pymupdf` (faster)
- Output: Extracted text with page numbers
- Features: Table extraction, preserves structure

### 3. ImageProcessor (new)
- Handles: `image/png`, `image/jpeg`, `image/webp`, `image/gif`
- Libraries: `easyocr` or `tesseract` via `pytesseract`
- Output: OCR text + optional image description
- Features: Multi-language OCR (critical for Chinese)

### 4. MarkdownProcessor (new)
- Handles: `text/markdown`, `.md` files
- Method: Direct parse with `markdown` or `mistune`
- Output: Structured text with headings
- Features: Extract frontmatter separately

### 5. DocumentProcessor (new)
- Handles: `.docx`, `.odt`, `.rtf`
- Libraries: `python-docx` for docx, `pypandoc` for others
- Output: Plain text with structure hints

### 6. TextProcessor (fallback)
- Handles: `text/plain`, unknown types
- Method: Direct pass-through
- Output: As-is

---

## Feishu Integration

Feishu supports multiple message types:

| Feishu Type | Aily Handler | Processor |
|-------------|--------------|-----------|
| `text` (with URL) | Extract URL, fetch | WebProcessor |
| `image` | Download, OCR | ImageProcessor |
| `file` | Download, detect type | Auto-detect by extension |
| `voice` | Existing flow | WhisperTranscriber |

---

## Implementation Plan

### Phase 1: Content Detection Layer
- Create `aily/processing/detector.py`
- Magic bytes database for common formats
- Extension-to-mime mapping

### Phase 2: Processor Implementations
- Create `aily/processing/processors.py`
- Implement each processor with unified interface
- `process(content: bytes | str) -> ExtractedContent`

### Phase 3: Router
- Create `aily/processing/router.py`
- Routes to correct processor based on detection
- Fallback chain: specific → generic → error

### Phase 4: Feishu Integration
- Update `ws_client.py` to handle file/image messages
- Download attachments via Feishu API
- Pass to router

---

## Dependencies

```bash
# PDF processing
pip install pdfplumber pymupdf

# OCR
pip install easyocr Pillow
# OR for tesseract: pip install pytesseract

# Document formats
pip install python-docx pypandoc

# Markdown
pip install mistune
```

---

## Example Usage

```python
# User sends PDF in Feishu
file_key = "lfn..."  # Feishu file key
file_bytes = await download_feishu_file(file_key)

# Aily processes
content_type = detector.detect(file_bytes, filename="paper.pdf")
# → "application/pdf"

text = await router.process(file_bytes, content_type)
# → Extracted text from PDF

notes = await atomicizer.atomize(text, source_url="feishu://file/...")
# → Atomic notes saved to graph + Obsidian
```

---

## Key Design Decisions

1. **Bytes-in, text-out**: All processors accept raw bytes, return clean text
2. **No external dependencies for core**: Optional processors fail gracefully
3. **Chinese-first OCR**: EasyOCR handles Chinese better than tesseract
4. **Preserve source context**: Always track original file/URL for verification
5. **Async everywhere**: All processors are async for concurrency

---

## Success Criteria

- [ ] Send any PDF → Extracted text → Obsidian note
- [ ] Send any image with text → OCR → Obsidian note
- [ ] Send markdown file → Parsed → Obsidian note
- [ ] Send Word doc → Extracted text → Obsidian note
- [ ] All routes through same atomicizer/connection pipeline
- [ ] No Kimi/Monica-specific code in main flow
