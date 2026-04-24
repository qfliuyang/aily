<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# graph

## Purpose

SQLite-backed knowledge graph. Stores nodes (concepts, notes, proposals) and edges (relationships) with bidirectional link support. Used by all three Minds for persistent knowledge storage.

## Key Files

| File | Description |
|------|-------------|
| `db.py` | `GraphDB` — SQLite graph with nodes/edges tables |

## For AI Agents

### Working In This Directory
- All node/edge operations are async via `aiosqlite`
- WAL mode enabled for concurrent reads during writes
- Nodes have `id`, `type`, `label`, `source`, `created_at`
- Edges have `id`, `source_id`, `target_id`, `relation`, `weight`

### Common Patterns
- `insert_node()` returns the node ID
- `insert_edge()` creates bidirectional links automatically
- `query_nodes()` supports type filtering and pagination
- GraphDB is initialized once in `main.py` lifespan

## Dependencies

### External
- `aiosqlite` — Async SQLite

<!-- MANUAL: -->
