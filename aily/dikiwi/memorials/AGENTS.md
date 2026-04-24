<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# memorials

## Purpose

Persistent memory system for DIKIWI. Stores long-term context, session memory, and cross-pipeline state that survives individual DIKIWI runs.

## Key Files

| File | Description |
|------|-------------|
| `storage.py` | `MemorialStorage` — read/write persistent memory records |
| `models.py` | `Memorial` dataclass — memory entries with timestamps and metadata |

## For AI Agents

### Working In This Directory
- Memorials persist across pipeline runs
- Used by agents to recall prior context
- Storage backend is typically SQLite or the GraphDB
- Memorials have TTL (time-to-live) for automatic expiration

### Common Patterns
- `store(key, value, ttl)` — write memory
- `recall(key)` — read memory
- `search(query)` — semantic search over memories
- Memorials are tagged by pipeline correlation ID

## Dependencies

### Internal
- `aily/graph/` — GraphDB for persistent storage
- `aily/llm/` — Embedding generation for semantic search

<!-- MANUAL: -->
