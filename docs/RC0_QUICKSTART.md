# Aily RC0 Docker Quickstart

This is the docs-only path for running Aily RC0 as a private second brain on a
local machine or small private server.

## 1. Prerequisites

- Docker with Compose v2.
- A local directory for persistent Aily state.
- A local directory that will act as the Obsidian-compatible vault.
- A long random Studio token.
- Optional: a real LLM provider key when you want DIKIWI note generation rather
  than control-plane smoke testing.

## 2. Configure Environment

Copy the placeholder template and edit values locally:

```bash
cp .env.example .env
```

Minimum Docker environment for private Studio access:

```bash
export AILY_DOCKER_UI_AUTH_TOKEN="replace-with-a-long-random-token"
export AILY_DOCKER_DATA_DIR="$PWD/.docker-data/data"
export AILY_DOCKER_VAULT_DIR="$PWD/.docker-data/vault"
```

Optional real DIKIWI provider settings:

```bash
export AILY_DOCKER_DIKIWI_ENABLED=true
export AILY_DOCKER_LLM_PROVIDER=kimi
export AILY_DOCKER_KIMI_API_KEY="replace-with-real-provider-key"
```

For smoke testing without LLM spend, leave `AILY_DOCKER_DIKIWI_ENABLED=false`.
Hosted mode fails fast if UI auth is weak, and hosted real-DIKIWI mode fails fast
if no provider key is configured.

## 3. Start Aily With Docker

```bash
docker compose build
docker compose up -d
```

Open Studio:

```text
http://127.0.0.1:8000/?token=<your AILY_DOCKER_UI_AUTH_TOKEN>
```

## 4. Healthchecks

```bash
curl -f http://127.0.0.1:8000/health
curl -f -H "X-Aily-Token: $AILY_DOCKER_UI_AUTH_TOKEN" http://127.0.0.1:8000/ready
```

`/health` proves the process is alive. `/ready` summarizes storage, vault, and
auth readiness.

## 5. Capture Methods

Studio supports three RC0 capture methods:

1. Upload files through the Studio upload panel.
2. Submit URLs through the Studio URL form.
3. Submit text notes/messages through the Studio text capture form.

The backend stores each input in the durable source store and queues source jobs
with source metadata. Duplicate behavior is deterministic: files deduplicate by
content hash, URLs by normalized URL, and text by stripped text content.

## 6. Watch Queue And Processing Status

Use Studio to inspect:

- queued and running work;
- durable source events;
- successful notes/summaries where available;
- visible failures with error messages; and
- retry/reprocess actions for eligible failed work.

For API-level checks, inspect the documented UI source and queue endpoints under
`/api/ui/` while authenticated with `X-Aily-Token`.

## 7. Backups And Restore Dry Run

Create a backup through the admin maintenance API or Studio admin action:

```json
{"action":"create_backup","backup_path":"/data/backups/aily.zip"}
```

Run a restore dry run before trusting a backup:

```json
{"action":"restore_backup_dry_run","backup_path":"/data/backups/aily.zip"}
```

The backup covers vault markdown files, GraphDB, source-store DB, source objects,
and a hash manifest.

## 8. Troubleshooting

- `401` in Studio: use `/?token=<token>` or send `X-Aily-Token`.
- Startup exits immediately: check `UI_AUTH_TOKEN`, `HOSTED_MODE`, and provider
  keys. Hosted mode is intentionally fail-closed.
- No DIKIWI notes appear: verify real DIKIWI is enabled and a provider key is
  set. Smoke mode may keep `AILY_DOCKER_DIKIWI_ENABLED=false`.
- URL capture fails: private-network URL intake is denied unless explicitly
  enabled; failures should remain visible in source/job state.
- Docker data disappeared after restart: verify `AILY_DOCKER_DATA_DIR` and
  `AILY_DOCKER_VAULT_DIR` are mounted as persistent host directories.

## 9. Known Limitations For RC0

- Real-provider DIKIWI quality is still under active RC0 target work; do not
  treat smoke-mode Docker success as note-quality acceptance.
- Business/proposal stages are intentionally separate from the core 00-06 DIKIWI
  evidence unless explicitly enabled and audited.
- Existing health baseline debt is tracked in `tests/quality_baseline.json`; new
  RC0 regressions must not be hidden by regenerating the baseline.

## 10. Deeper Operator References

- [Docker pre-production runbook](DOCKER_PREPROD.md)
- [Hosted private website runbook](HOSTED_PRIVATE_WEBSITE_RUNBOOK.md)
- [RC0 goal contract](AILY_RC0_GOAL_CONTRACT.md)
- [RC0 evidence ledger](release-rc0-evidence.md)
