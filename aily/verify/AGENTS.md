<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# verify

## Purpose

Claim verification system. Automates the process of a human researcher clicking source links and checking that AI-generated claims match the actual content.

## Key Files

| File | Description |
|------|-------------|
| `verifier.py` | `ClaimVerifier` — fetches sources, verifies claims with LLM |

## For AI Agents

### Working In This Directory
- Extracts URLs from generated content
- Fetches each source with `BrowserFetcher`
- Uses LLM to compare claim against source text
- Reports verification results with confidence scores

### Common Patterns
- URL extraction with regex
- Parallel fetching of multiple sources
- LLM prompt: "Does the source support this claim?"
- Results: `verified`, `partial`, `contradicted`, `unreachable`

## Dependencies

### Internal
- `aily/browser/` — Source fetching
- `aily/llm/` — Verification reasoning

### External
- `httpx` — HTTP fallback

<!-- MANUAL: -->
