# Hosted Private Website Runbook

Phase 8 target: Aily can be exposed as a private website without relying on obscurity.

## Required Environment

```bash
HOSTED_MODE=true
UI_AUTH_ENABLED=true
UI_AUTH_TOKEN=<long random token>
AILY_DATA_DIR=/srv/aily/data
OBSIDIAN_VAULT_PATH=/srv/aily/vault
UI_RATE_LIMIT_REQUESTS=20
UI_RATE_LIMIT_WINDOW_SECONDS=60
```

## Reverse Proxy

- Terminate TLS at the reverse proxy.
- Forward `Authorization` and `X-Aily-Token`.
- Preserve websocket upgrade headers for `/api/ui/events`.
- Forward `X-Forwarded-For` so hosted-mode rate limiting keys abusive clients correctly.

## Health

- `GET /health`: process is alive.
- `GET /ready`: storage/vault/auth readiness summary.

## Backup

Admin control action:

```json
{"action":"create_backup","backup_path":"/srv/aily/backups/aily.zip"}
```

Dry-run restore action:

```json
{"action":"restore_backup_dry_run","backup_path":"/srv/aily/backups/aily.zip"}
```

The backup contains vault files, GraphDB, source-store DB, source objects, and a hash manifest.

## Audit

Hosted UI requests and admin maintenance actions append JSONL records to `SETTINGS.resolved_audit_log_path`.
