<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# integration

## Purpose

Integration tests and test infrastructure. Contains mock services, test evidence files, and service-level integration validations.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `evidence/` | Sample documents, search results, and test artifacts |
| `services/` | Mock services for isolated testing |

## For AI Agents

### Working In This Directory
- `evidence/` holds sample PDFs, images, and web pages for testing
- `services/` contains Docker-based mocks (Feishu, Obsidian, browser)
- Integration tests verify subsystem boundaries

### Testing Requirements
- Mock services can be started with Docker Compose
- Evidence files are committed for reproducible tests

## Dependencies

### Internal
- Various Aily subsystems under integration test

<!-- MANUAL: -->
