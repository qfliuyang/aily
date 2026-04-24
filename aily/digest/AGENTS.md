<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# digest

## Purpose

Daily digest pipeline. Aggregates recent knowledge graph activity, verifies claims, and generates a formatted daily summary pushed to Feishu.

## Key Files

| File | Description |
|------|-------------|
| `pipeline.py` | `DigestPipeline` — collects recent nodes, verifies, formats, pushes |

## For AI Agents

### Working In This Directory
- Digest runs on a schedule (see `aily/scheduler/jobs.py`)
- Pulls recent nodes from GraphDB (last 24h)
- Uses `ClaimVerifier` to validate claims against sources
- Output is sent via `FeishuPusher`

### Common Patterns
- GraphDB query: `SELECT * FROM nodes WHERE created_at > ?`
- Verification is optional (skipped if no browser API key)
- Markdown formatting for Feishu rich text

## Dependencies

### Internal
- `aily/graph/` — GraphDB for knowledge queries
- `aily/verify/` — Claim verification
- `aily/push/feishu.py` — Feishu message delivery
- `aily/queue/` — QueueDB for ingestion logs

<!-- MANUAL: -->
