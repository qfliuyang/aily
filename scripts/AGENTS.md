<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# scripts

## Purpose

CLI tools, daemons, and batch runners for operating Aily.

## Key Files

| File | Description |
|------|-------------|
| `aily_ingest.py` | Daily incremental ingestion — watch mode + one-shot, supports `--force` |
| `prep_chaos.py` | Pre-extract PDFs via MinerU, populate identical 00-Chaos in multiple vaults |
| `run_chaos_daemon.py` | File-watcher daemon for `~/aily_chaos/` — starts/stops/status |
| `run_mineru_chaos_batch.py` | Batch runner: folder → MinerU → 00-Chaos → DIKIWI |
| `batch_chaos_processor.py` | Batch process existing chaos files |
| `aily_chaos_cli.py` | CLI for chaos operations |
| `setup_daemon.sh` | macOS launchd plist setup for daemon |

## For AI Agents

### Working In This Directory
- Scripts use `sys.path.insert(0, str(Path(__file__).parent.parent))` to import `aily`
- Most scripts are async — wrapped with `asyncio.run()`
- Daemon scripts support `start`, `stop`, `status` subcommands
- Legacy test and benchmark scripts have been removed for the Aily V1 redesign.

### Common Patterns
- `ChaosConfig()` for default chaos settings
- `PrimaryLLMRoute.route_kimi()` for LLM client (or `route_deepseek()`)
- `DikiwiObsidianWriter(vault_path=...)` for vault output
- `GraphDB(db_path=vault/.aily/graph.db)` for graph persistence
- Keep scripts focused on operator workflows, ingestion, and local runtime support.

## Dependencies

### Internal
- `aily/` — all subsystems

<!-- MANUAL: -->
