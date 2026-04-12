# Aily Chaos: Multimodal Content Processing System

## Overview

**Aily Chaos** is a drop-folder based multimodal content ingestion system. Users drop files into `~/aily_chaos/` and the system automatically processes, tags, and converts them into Zettelkasten notes via DIKIWI.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FILE SYSTEM WATCHER                                  │
│  Watchdog (watchdog library) monitors /Users/luzi/aily_chaos/               │
│  - Detects: CREATE, MODIFY, MOVE events                                      │
│  - Ignores: Partial files (.crdownload, .tmp), hidden files                  │
│  - Debounce: 5-second delay to ensure file is fully written                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONTENT TYPE DETECTOR                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Extension   │  │ MIME Magic  │  │ Content     │  │ LLM-based           │ │
│  │ (.pdf,      │  │ (libmagic)  │  │ Sniffing    │  │ Classifier          │ │
│  │ .mp4)       │  │             │  │             │  │ (fallback)          │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MULTIMODAL PROCESSOR PIPELINE                             │
│                                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │   DOCUMENT   │ │    VIDEO     │ │    IMAGE     │ │    PRESENTATION      │ │
│  │              │ │              │ │              │ │                      │ │
│  │ • PDF        │ │ • Frame      │ │ • OCR        │ │ • PPTX extraction    │ │
│  │   - Text     │ │   extraction │ │ • Visual     │ │ • Slide notes        │ │
│  │   - Layout   │ │ • Audio      │ │   analysis   │ │ • Speaker notes      │ │
│  │   - OCR      │ │   extraction │ │ • Diagram    │ │ • Chart extraction   │ │
│  │   - Charts   │ │ • Whisper    │ │   understanding│ │                     │ │
│  │              │ │   transcript │ │              │ │                      │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────────────┘ │
│                                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │     URL      │ │   MARKDOWN   │ │    AUDIO     │ │    ARCHIVE          │ │
│  │              │ │              │ │              │ │                      │ │
│  │ • Web scrape │ │ • Frontmatter│ │ • Whisper    │ │ • ZIP/TAR           │ │
│  │ • Article    │ │ • Links      │ │   transcript │ │   extraction        │ │
│  │   extract    │ │ • Metadata   │ │ • Speaker ID │ │ • Recursive         │ │
│  │ • DOM parse  │ │              │ │ • Segments   │ │   processing        │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ENHANCED CONTENT STRUCTURE                                │
│                                                                              │
│  ExtractedContentMultimodal:                                                │
│  ├── text: str                    # Primary text content                     │
│  ├── title: str | None            # Document title                           │
│  ├── source_type: str             # mime category                            │
│  ├── metadata: dict               # File-specific metadata                   │
│  │   ├── page_count, duration, resolution, etc.                             │
│  │   ├── ocr_confidence, transcript_quality                                 │
│  │   └── extraction_method, processing_timestamp                            │
│  ├── visual_elements: list        # Images, charts, diagrams                 │
│  │   ├── element_id, type, description, base64_thumbnail                    │
│  ├── transcript: str | None       # For video/audio                          │
│  ├── segments: list               # Timestamped segments                     │
│  │   ├── start_time, end_time, text, summary                                │
│  └── tags: list[str]              # Auto-generated tags                      │
│      ├── content_type, domain, key_concepts, entities                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    INTELLIGENT TAGGING ENGINE                                │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  Content-Based   │  │   LLM-Based      │  │   Knowledge Graph        │   │
│  │  Tags            │  │   Tags           │  │   Tags                   │   │
│  │                  │  │                  │  │                          │   │
│  │ • File extension │  │ • Domain         │  │ • Similar documents      │   │
│  │ • MIME type      │  │   classification │  │ • Connected entities     │   │
│  │ • Text stats     │  │ • Key concepts   │  │ • Temporal patterns      │   │
│  │ • Language detect│  │ • Named entities │  │ • Co-occurrence          │   │
│  │ • Reading time   │  │ • Sentiment      │  │   patterns               │   │
│  │ • Complexity     │  │ • Technical level│  │                          │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
│                                                                              │
│  Tag Schema:                                                                 │
│  ├── type:document|video|image|audio|presentation                           │
│  ├── domain:eda|ai|semiconductor|architecture|...                           │
│  ├── format:pdf|mp4|pptx|md|...                                             │
│  ├── language:en|zh|...                                                     │
│  ├── entities:[company names, technologies, people]                         │
│  ├── concepts:[technical terms, methodologies]                              │
│  ├── status:raw|processing|processed|failed                                 │
│  └── quality:high|medium|low (based on extractability)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DIKIWI INTEGRATION                                        │
│                                                                              │
│  1. Create RainDrop with:                                                    │
│     ├── rain_type: FILE                                                      │
│     ├── content: ExtractedContentMultimodal.text                             │
│     ├── metadata: full extracted structure                                   │
│     ├── tags: combined from tagging engine                                   │
│     └── source: file_path                                                    │
│                                                                              │
│  2. Process through DIKIWI pipeline:                                         │
│     ├── DATA: Extract facts from content                                     │
│     ├── INFORMATION: Classify with multimodal context                        │
│     ├── KNOWLEDGE: Link to existing notes                                    │
│     ├── INSIGHT: Detect patterns                                             │
│     └── WISDOM: Generate 4 Zettelkasten notes                                │
│                                                                              │
│  3. Special handling for multimodal:                                         │
│     • Video transcripts → main text + timestamp references                   │
│     • Image descriptions → linked zettels                                    │
│     • Diagrams/Charts → separate "Figure" zettels                            │
│     • Code snippets → "Code-Example" zettels                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OUTPUT & ORGANIZATION                                     │
│                                                                              │
│  Chaos Dropzone → Processing → Zettelkasten                                  │
│                                                                              │
│  Original files:        Processed files:                                     │
│  /aily_chaos/           /aily_chaos/.processed/                              │
│  ├── raw files          ├── {date}/                                          │
│  ├── in progress        │   ├── {filename}.json    # extraction result      │
│  └── .processing/       │   ├── {filename}.md      # markdown version       │
│                         │   └── visual_elements/   # extracted images       │
│                         └── failed/                                          │
│                             └── {filename}.error.json                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Core Infrastructure
1. **File Watcher Service** (`aily/chaos/watcher.py`)
   - watchdog-based file system monitoring
   - Debouncing and file stability detection
   - Queue management for processing jobs

2. **Enhanced Type Detection** (`aily/chaos/detector.py`)
   - python-magic for MIME detection
   - Content sniffing for edge cases
   - LLM fallback for ambiguous files

### Phase 2: Multimodal Processors

#### Video Processor (`aily/chaos/processors/video.py`)
```python
class VideoProcessor(ContentProcessor):
    SUPPORTED_TYPES = ["video/mp4", "video/avi", "video/mkv", "video/mov"]

    Processing pipeline:
    1. ffmpeg extract audio → Whisper transcription
    2. Scene detection → Key frame extraction (every 5s or scene change)
    3. Frame analysis → GPT-4V description of key moments
    4. Combine: transcript + visual descriptions → unified text
```

#### Enhanced PDF Processor (`aily/chaos/processors/pdf_enhanced.py`)
```python
class EnhancedPDFProcessor(ContentProcessor):
    Processing pipeline:
    1. pdfplumber extract text + layout info
    2. pdf2image convert pages to images
    3. Detect visual elements (charts, diagrams, images)
    4. GPT-4V describe visual elements
    5. Combine: text + visual descriptions
```

#### PPTX Processor (`aily/chaos/processors/pptx.py`)
```python
class PPTXProcessor(ContentProcessor):
    SUPPORTED_TYPES = ["application/vnd.openxmlformats-officedocument.presentationml.presentation"]

    Processing pipeline:
    1. python-pptx extract text from slides
    2. Extract speaker notes
    3. Convert slides to images
    4. GPT-4V analyze slide visuals
    5. Combine: slide text + notes + visual analysis
```

#### Enhanced Image Processor (`aily/chaos/processors/image_enhanced.py`)
```python
class EnhancedImageProcessor(ContentProcessor):
    Processing pipeline:
    1. OCR (EasyOCR/pytesseract) for text extraction
    2. GPT-4V for visual understanding
    3. Diagram/Chart detection and interpretation
    4. Combine: OCR text + visual description
```

### Phase 3: Tagging Engine (`aily/chaos/tagger.py`)

```python
class IntelligentTagger:
    """Multi-layer tagging system."""

    async def tag(self, content: ExtractedContentMultimodal) -> list[str]:
        # Layer 1: Content-based
        tags = self._content_tags(content)

        # Layer 2: LLM-based
        tags.extend(await self._llm_tags(content))

        # Layer 3: Knowledge graph
        tags.extend(await self._graph_tags(content))

        return list(set(tags))  # Deduplicate
```

### Phase 4: DIKIWI Integration (`aily/chaos/dikiwi_bridge.py`)

```python
class ChaosDikiwiBridge:
    """Bridge between chaos processing and DIKIWI pipeline."""

    async def process_to_zettelkasten(
        self,
        extracted: ExtractedContentMultimodal,
        file_path: Path
    ) -> list[Zettel]:
        # Create RainDrop from extracted content
        drop = RainDrop(
            rain_type=RainType.FILE,
            content=extracted.text,
            metadata={
                "source_file": str(file_path),
                "extracted": extracted.to_dict(),
            },
            tags=extracted.tags,
        )

        # Process through DIKIWI
        result = await self.dikiwi_mind.process_input(drop)

        return result.zettels
```

## Production Runtime: Chaos Daemon

The `run_chaos_daemon.py` script provides the production file processing service.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CHAOS DAEMON                                  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ File Scanner │  │ SQLite Queue │  │   Worker     │          │
│  │ (os.walk)    │→ │ (persistent) │→ │ (asyncio)    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                              │                   │
│                                              ▼                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              PROCESSING PIPELINE                      │      │
│  │  1. Content Extraction (PDF/Video/Image/Text)        │      │
│  │  2. DIKIWI Bridge (RainDrop conversion)              │      │
│  │  3. Zettelkasten Generation (Obsidian output)        │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### Key Features

| Feature | Implementation |
|---------|---------------|
| **Persistent Queue** | SQLite with PENDING→PROCESSING→COMPLETED/FAILED states |
| **Crash Recovery** | Resets stuck PROCESSING files on startup |
| **Size Limits** | PDF: 50MB, Video: 500MB, Image: 20MB |
| **Timeouts** | PDF: 60s, Video: 300s, Image: 30s |
| **Smart Filtering** | Skips node_modules, .git, build artifacts |
| **Auto-Start** | macOS launchd plist for boot-time startup |

### File Processing Flow

```
~/aily_chaos/
├── file.pdf                    # Detected by scanner
│       ↓
├── .aily_chaos.db              # Queued (PENDING)
│       ↓
├── .processed/                 # Moved after processing
│   └── 2026-04-12/
│       └── file.pdf
│       ↓
~/Documents/Obsidian Vault/
└── 10-Knowledge/
    ├── concepts/               # Generated zettels
    └── sources/                # Source notes
```

### Commands

```bash
# Setup (creates folders, installs plist, starts service)
./scripts/setup_daemon.sh

# Manual operation
python scripts/run_chaos_daemon.py start    # Background daemon
python scripts/run_chaos_daemon.py stop     # Stop daemon
python scripts/run_chaos_daemon.py status   # Queue statistics
python scripts/run_chaos_daemon.py once     # Process 5 files, exit
```

### macOS Service Integration

The daemon runs as a launchd service (`com.aily.chaos`):

```bash
# Check service status
launchctl list | grep com.aily.chaos

# View logs
tail -f ~/aily_chaos/daemon.log
tail -f ~/aily_chaos/daemon.error.log

# Manual control
launchctl start com.aily.chaos
launchctl stop com.aily.chaos
```

## Dependencies

```toml
[tool.poetry.dependencies]
# Core processing
watchdog = "^3.0.0"           # File system watching
python-magic = "^0.4.27"      # MIME type detection

# Video processing
ffmpeg-python = "^0.2.0"      # Video/audio processing
openai-whisper = "^20231117"  # Audio transcription

# Document processing
pdfplumber = "^0.10.0"        # PDF text extraction
pymupdf = "^1.23.0"           # PDF to image
python-pptx = "^0.6.23"       # PowerPoint extraction

# Image processing
pillow = "^10.0.0"            # Image manipulation
easyocr = "^1.7.0"            # OCR

# LLM integration
openai = "^1.0.0"             # GPT-4V for visual analysis

# Utilities
langdetect = "^1.0.9"         # Language detection
```

## Usage

### Chaos Daemon (Production)

The Chaos Daemon is the production file watcher that runs continuously:

```bash
# Setup and start (one-time setup, auto-starts on boot)
./scripts/setup_daemon.sh

# Manual control
python scripts/run_chaos_daemon.py start    # Run in background
python scripts/run_chaos_daemon.py stop     # Stop daemon
python scripts/run_chaos_daemon.py status   # Check queue stats
python scripts/run_chaos_daemon.py once     # Process 5 files and exit
```

### Programmatic Usage

```python
from aily.chaos.queue_processor import ChaosQueue
from aily.chaos.dikiwi_bridge import ChaosDikiwiBridge

# Queue files for processing
queue = ChaosQueue(db_path="/Users/luzi/aily_chaos/.aily_chaos.db")
queue.add_file("/path/to/file.pdf", file_type="pdf")

# Process through bridge
bridge = ChaosDikiwiBridge(dikiwi_mind=dikiwi, vault_path=vault_path)
result = await bridge.process_file(file_record)
```

## Configuration

```yaml
# aily_chaos.yaml
chaos:
  watch_folder: /Users/luzi/aily_chaos
  processed_folder: /Users/luzi/aily_chaos/.processed
  failed_folder: /Users/luzi/aily_chaos/.failed

  processing:
    debounce_seconds: 5
    max_file_size_mb: 500
    supported_extensions:
      - pdf
      - mp4
      - mov
      - pptx
      - md
      - txt
      - png
      - jpg
      - url

  video:
    extract_frames_every_n_seconds: 5
    whisper_model: base
    max_frames_per_video: 20

  image:
    ocr_enabled: true
    visual_analysis: true
    max_image_size: 2000

  tagging:
    llm_based: true
    knowledge_graph_integration: true
    auto_domain_classification: true

  dikiwi:
    zettelkasten_only: true
    generate_visual_element_zettels: true
```
