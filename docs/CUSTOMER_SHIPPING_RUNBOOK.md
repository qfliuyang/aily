# Aily Customer Shipping Runbook

Date: 2026-05-07

Scope: initial customer-ready, single-tenant/private deployment. This is not a
multi-tenant SaaS runbook. It covers one customer/operator running Aily with
Docker Compose, Aily Studio, a real LLM provider, durable vault/graph storage,
backups, and evidence-producing acceptance gates.

## Supported customer deployment

- Docker Compose deployment from `Dockerfile`, `docker-compose.yml`, and
  `docker-compose.preprod.yml`.
- Hosted/private Studio with `HOSTED_MODE=true`, `UI_AUTH_ENABLED=true`, and a
  strong `UI_AUTH_TOKEN`.
- Durable mounted volumes for `/data`, `/vault`, and `/chaos`.
- Real provider DIKIWI through Kimi or DeepSeek credentials.
- Browser-based Studio upload/URL/control flows.
- Obsidian/Zettelkasten vault output through `00-Chaos` to `06-Impact`.

## Required customer environment

Minimum `.env`/deployment values:

```bash
AILY_DOCKER_UI_AUTH_TOKEN=<strong random token, 16+ chars>
AILY_DOCKER_DIKIWI_ENABLED=true
AILY_DOCKER_LLM_PROVIDER=kimi
AILY_DOCKER_KIMI_API_KEY=<real key>
# or DeepSeek:
# AILY_DOCKER_LLM_PROVIDER=deepseek
# AILY_DOCKER_DEEPSEEK_API_KEY=<real key>
AILY_DOCKER_LLM_TRACE_LOG_PATH=/data/llm-calls.jsonl
```

Never commit provider keys. Evidence manifests list env key names only, not key
values. Generated Docker `.env` files under `logs/runs/` are local evidence
artifacts and must not be published with secrets.

## Customer acceptance gate

Before shipping a customer build, run:

```bash
python3 scripts/run_docker_preprod_e2e.py --build --require-real-llm
python3 scripts/audit_customer_ship_readiness.py --output logs/customer-ship-readiness.json
```

Required result:

- Docker real-LLM E2E exits `0`.
- Customer readiness audit exits `0`.
- The Docker manifest is from current clean `HEAD`.
- Manifest acceptance has:
  - `mocked=false`
  - `real_docker=true`
  - `real_browser=true`
  - `real_fastapi=true`
  - `real_vault=true`
  - `real_graph_db=true`
  - `real_llm=true`
  - `provider_verified_dikiwi=true`
- `vault_counts_after` has non-zero `01-Data` through `06-Impact` counts.
- `llm_receipts.provider_verified_successes > 0` and
  `llm_receipts.unverified_successes == 0`.

## Operations

### Start

```bash
docker compose --env-file <customer-env-file> \
  -f docker-compose.yml \
  -f docker-compose.preprod.yml \
  up -d --build
```

### Health checks

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

### Backup and restore dry run

Use Studio Operations or the API control action:

- `create_backup`
- `restore_backup_dry_run`

Do not ship a customer update without a successful backup and restore dry-run
artifact.

### Evidence audit

Keep the latest customer acceptance manifest and readiness audit with the
customer release notes. They are the proof chain for support/debugging.

## Security boundaries

- Single-token auth is acceptable only for single-tenant/private customer
  deployment.
- Put Aily behind a customer-controlled HTTPS reverse proxy for internet access.
- Rotate `UI_AUTH_TOKEN` and provider keys after any evidence bundle is shared
  outside the deployment host.
- Do not expose `/data`, `/vault`, `/chaos`, generated `.env` files, or raw
  `llm-calls.jsonl` publicly.
- This release is not certified for multi-tenant account isolation, public SaaS,
  regulated workloads, or untrusted arbitrary internet users.

## Known limits for this customer-ready scope

- Customer-ready means initial single-tenant/private shipping, not broad SaaS.
- Current combined acceptance covers text/file upload through Studio. URL/retry
  controls are covered by the Docker control-plane gate and RC0 gates, but the
  combined real-LLM gate focuses on one browser-submitted document to
  DATA→IMPACT.
- Long provider runs are slow and budget-consuming. Treat timeout, 429, or
  partial-stage failures as blockers, not success.
