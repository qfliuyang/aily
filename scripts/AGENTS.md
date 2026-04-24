<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# scripts

## Purpose

CLI tools, daemons, and batch runners for operating Aily. These are standalone scripts that can be run directly or invoked by the main application.

## Key Files

| File | Description |
|------|-------------|
| `run_chaos_daemon.py` | File-watcher daemon for `~/aily_chaos/` — starts/stops/status |
| `run_mineru_chaos_batch.py` | Batch runner: folder → MinerU → 00-Chaos → DIKIWI |
| `run_test_suite.py` | Unified test runner with multiple scenarios |
| `test_framework.py` | Test framework with scenarios: full-pipeline, chaos-e2e, dikiwi-smoke |
| `fresh_test_run.py` | Fresh vault test with LLM call logging |
| `batch_chaos_processor.py` | Batch process existing chaos files |
| `aily_chaos_cli.py` | CLI for chaos operations |
| `setup_daemon.sh` | macOS launchd plist setup for daemon |

## For AI Agents

### Working In This Directory
- Scripts use `sys.path.insert(0, str(Path(__file__).parent.parent))` to import `aily`
- Most scripts are async — wrapped with `asyncio.run()`
- Daemon scripts support `start`, `stop`, `status` subcommands

### Common Patterns
- `ChaosConfig()` for default chaos settings
- `PrimaryLLMRoute.route_kimi()` for LLM client
- `DikiwiObsidianWriter(vault_path=...)` for vault output

## Dependencies

### Internal
- `aily/` — all subsystems

<!-- MANUAL: -->
