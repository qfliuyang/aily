<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# chaos

## Purpose

Tests for the Chaos document processing subsystem. Covers document extraction, DIKIWI bridge, and MinerU integration.

## Key Files

| File | Description |
|------|-------------|
| `test_document_processor.py` | Tests for document type detection and processing |
| `test_dikiwi_bridge.py` | Tests for Chaos → DIKIWI handoff |
| `test_mineru_processor.py` | Tests for MinerU PDF extraction |
| `test_mineru_batch.py` | Tests for batch MinerU processing |

## For AI Agents

### Working In This Directory
- Tests use sample documents from `tests/integration/evidence/`
- MinerU tests require the mineru CLI or API to be available
- Document processor tests cover PDF, image, and text extraction

### Testing Requirements
- Run with: `pytest tests/chaos/ -xvs`
- Some tests are skipped if MinerU is not installed

## Dependencies

### Internal
- `aily/chaos/` — Chaos subsystem under test

<!-- MANUAL: -->
