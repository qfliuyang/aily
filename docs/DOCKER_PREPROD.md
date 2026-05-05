# Docker Pre-Production Runbook

Docker is Aily's clean-room pre-production and first distribution path. It should prove the app can run without hidden workstation state while still using real mounted storage, real browser actions, and real provider calls when keys are injected.

## Files

- `Dockerfile`: builds the FastAPI app and the compiled Aily Studio frontend.
- `docker-compose.yml`: default private single-user stack.
- `docker-compose.preprod.yml`: pre-production overrides and optional profiles.
- `.env.docker.example`: safe template for runtime configuration.
- `scripts/run_docker_preprod_e2e.py`: evidence-producing Docker E2E gate.

## First Run

```bash
cp .env.docker.example .env.docker
# edit UI_AUTH_TOKEN and provider keys if running real DIKIWI
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.preprod.yml build --no-cache
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.preprod.yml up -d
```

Open `http://127.0.0.1:${AILY_HOST_PORT:-8000}/?token=<UI_AUTH_TOKEN>`.

## Volumes

Use explicit host paths in `.env.docker`:

- `AILY_DOCKER_DATA_DIR`: queue DB, graph DB, source store, source objects, UI event log, audit log, run evidence.
- `AILY_DOCKER_VAULT_DIR`: Obsidian-compatible vault output.
- `AILY_DOCKER_CHAOS_DIR`: optional drop/input folder for batch document tests.

Do not bake these into the image.

## Secrets

Never put real keys in Dockerfile, compose files, docs, or image layers. Use `.env.docker` or your deployment secret manager.

Minimum private Studio settings:

```bash
AILY_DOCKER_HOSTED_MODE=true
AILY_DOCKER_UI_AUTH_ENABLED=true
AILY_DOCKER_UI_AUTH_TOKEN=<long random token>
```

Real LLM Docker acceptance settings:

```bash
AILY_DOCKER_DIKIWI_ENABLED=true
AILY_DOCKER_LLM_PROVIDER=kimi
AILY_DOCKER_KIMI_API_KEY=<key>
AILY_DOCKER_DIKIWI_INCREMENTAL_TRIGGER_RATIO=0.0
AILY_DOCKER_DIKIWI_NETWORK_MIN_NODES=2
AILY_DOCKER_DIKIWI_NETWORK_TRIGGER_SCORE=0.0
```

or:

```bash
AILY_DOCKER_DIKIWI_ENABLED=true
AILY_DOCKER_LLM_PROVIDER=deepseek
AILY_DOCKER_DEEPSEEK_API_KEY=<key>
```

## Pre-Production E2E

Run the clean-room gate:

```bash
uv run python scripts/run_docker_preprod_e2e.py --build --exercise-url --exercise-retry
```

The gate must write `logs/runs/<run_id>/manifest.json` with:

- git state
- Docker image digest
- compose file hash
- env key names without secret values
- mounted volume paths
- health/readiness responses
- source manifest

## Real-LLM DIKIWI Quality Gate

Use this when you want to prove DIKIWI quality inside Docker, not just Studio/control-plane behavior. This gate runs real PDFs through 00-06 and then audits the generated vault, graph, and LLM trace.

The accepted evidence pattern is:

- Docker app container built from the current checkout.
- `/Users/luzi/aily_chaos` or another corpus mounted as `/root/aily_chaos`.
- `/vault` mounted to an empty host evidence vault.
- `/data` mounted so `EvidenceRun` output survives container shutdown.
- `scripts/run_test_suite.py full-pipeline --skip-business` runs inside the container.
- `scripts/audit_dikiwi_quality.py` runs on the mounted output and must pass.

Latest accepted proof:

- `logs/runs/2026-05-03T08-13-27Z_docker_real_llm_dikiwi_quality_2pdf/dikiwi-quality-report.json`
- 2 PDFs
- 20 successful `kimi-k2.6` calls, 0 LLM failures
- 47 Data, 43 Information, 20 Knowledge, 3 Insight, 4 Wisdom, 5 Impact notes
- 191 graph edges
- 0 quality-audit failures
- graph and vault snapshots
- UI event log
- browser screenshots
- container logs
- restart-persistence proof
- backup/restore dry-run proof

## Restart And Persistence

The pre-production test restarts the app container and verifies that source records, UI events, graph DB, vault files, and evidence survive because they are mounted volumes.

Manual check:

```bash
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.preprod.yml restart aily-app
curl http://127.0.0.1:${AILY_HOST_PORT:-8000}/ready
```

## Backup And Restore

Aily Studio exposes admin backup controls through `/api/ui/control`.

The Docker E2E calls:

- `create_backup` to write a zip under `/data/backups/`
- `restore_backup_dry_run` to extract into `/data/restore-dry-run`

This is not a replacement for host-level volume backups. It is a product-level sanity check.

## Optional MinerU Profile

The preprod compose file includes a placeholder `mineru` profile. Do not treat it as accepted until a dedicated MinerU Docker E2E proves PDF extraction into `00-Chaos` and downstream DIKIWI routing.

```bash
docker compose --profile mineru --env-file .env.docker -f docker-compose.yml -f docker-compose.preprod.yml up -d
```

## Troubleshooting

- `401` on Studio/API: open `/?token=<UI_AUTH_TOKEN>` or save the token in the Studio Private Access strip.
- URL E2E fails in Docker: confirm `host.docker.internal` resolves. The compose file maps it to `host-gateway`.
- Data disappears after restart: check `.env.docker` volume paths and make sure they are host paths, not image paths.
- Real DIKIWI is slow or expensive: keep `AILY_DIKIWI_ENABLED=false` for smoke gates and run real-LLM Docker acceptance intentionally.
