<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# scripts

## Purpose

CLI tools, daemons, batch runners, and benchmarks for operating Aily.

## Key Files

| File | Description |
|------|-------------|
| `aily_ingest.py` | Daily incremental ingestion — watch mode + one-shot, supports `--force` |
| `benchmark_providers.py` | Multi-provider benchmark: runs 3 providers on same PDFs, compares results |
| `benchmark_run.py` | Single-provider benchmark: processes pre-extracted 00-Chaos through full pipeline |
| `prep_chaos.py` | Pre-extract PDFs via MinerU, populate identical 00-Chaos in multiple vaults |
| `run_chaos_daemon.py` | File-watcher daemon for `~/aily_chaos/` — starts/stops/status |
| `run_mineru_chaos_batch.py` | Batch runner: folder → MinerU → 00-Chaos → DIKIWI |
| `run_test_suite.py` | Unified test runner with multiple scenarios |
| `test_framework.py` | Test framework — full-pipeline, chaos-e2e, dikiwi-smoke, image copy |
| `batch_chaos_processor.py` | Batch process existing chaos files |
| `aily_chaos_cli.py` | CLI for chaos operations |
| `setup_daemon.sh` | macOS launchd plist setup for daemon |

## For AI Agents

### Working In This Directory
- Scripts use `sys.path.insert(0, str(Path(__file__).parent.parent))` to import `aily`
- Most scripts are async — wrapped with `asyncio.run()`
- Daemon scripts support `start`, `stop`, `status` subcommands
- Benchmark scripts use seeded random selection for reproducibility

### Common Patterns
- `ChaosConfig()` for default chaos settings
- `PrimaryLLMRoute.route_kimi()` for LLM client (or `route_zhipu()`, `route_deepseek()`)
- `DikiwiObsidianWriter(vault_path=...)` for vault output
- `GraphDB(db_path=vault/.aily/graph.db)` for graph persistence
- Benchmark patterns: pre-extract once, run separately, compare reports

## Dependencies

### Internal
- `aily/` — all subsystems

<!-- MANUAL: -->
