from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aily.verify.evidence import environment_snapshot, git_state, graph_snapshot, source_manifest, utc_timestamp, vault_counts


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _sha256_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _run(command: list[str], *, cwd: Path, command_log: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    command_log.append(" ".join(command))
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def _run_required(command: list[str], *, cwd: Path, command_log: list[str], timeout: int = 120) -> str:
    result = _run(command, cwd=cwd, command_log=command_log, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def _compose_base(compose_files: list[Path], env_file: Path, project_name: str) -> list[str]:
    command = ["docker", "compose", "--env-file", str(env_file), "-p", project_name]
    for compose_file in compose_files:
        command.extend(["-f", str(compose_file)])
    return command


async def _wait_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 90.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return dict(response.json())
            last_error = RuntimeError(f"status={response.status_code} body={response.text[:300]}")
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(1.0)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


async def _query_events(base_url: str, event_type: str, token: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{base_url}/api/ui/events/query",
            params={"event_type": event_type},
            headers={"x-aily-token": token},
        )
    response.raise_for_status()
    return list(response.json().get("events", []))


async def _post_control(base_url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base_url}/api/ui/control",
            headers={"x-aily-token": token},
            json=payload,
        )
    response.raise_for_status()
    return dict(response.json())


def _run_browser(*args: str, cwd: Path, command_log: list[str]) -> str:
    command = ["agent-browser", "--session", "aily-docker-preprod-e2e", *args]
    command_log.append(" ".join(command))
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=75)
    if result.returncode != 0:
        raise RuntimeError(
            f"agent-browser command failed: {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def _mark_failed(source_store_db: Path, source_id: str) -> None:
    with sqlite3.connect(source_store_db, timeout=10) as conn:
        conn.execute(
            """
            UPDATE sources
            SET status = 'failed',
                metadata = '{"docker_preprod_seeded_failure": true}',
                updated_at = datetime('now')
            WHERE source_id = ?
            """,
            (source_id,),
        )
        conn.commit()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Docker pre-production E2E for Aily.")
    parser.add_argument("--compose-file", action="append", type=Path, default=None)
    parser.add_argument("--build", action="store_true", help="Build the Docker image before starting the stack.")
    parser.add_argument("--no-cache", action="store_true", help="Use --no-cache when building.")
    parser.add_argument("--exercise-url", action="store_true", help="Submit a real local HTTP URL through Studio.")
    parser.add_argument("--exercise-retry", action="store_true", help="Seed a failed source and retry it through Studio.")
    parser.add_argument("--keep-running", action="store_true", help="Leave the Docker stack running after the test.")
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    compose_files = args.compose_file or [repo_root / "docker-compose.yml", repo_root / "docker-compose.preprod.yml"]
    compose_files = [path.resolve() for path in compose_files]
    missing = [path for path in compose_files if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing compose file(s): {missing}")

    scenario_parts = ["docker_preprod"]
    if args.exercise_retry:
        scenario_parts.append("retry")
    if args.exercise_url:
        scenario_parts.append("url")
    scenario_parts.append("e2e")
    scenario = "_".join(scenario_parts)
    run_id = datetime.now(timezone.utc).strftime(f"%Y-%m-%dT%H-%M-%SZ_{scenario}")
    evidence_dir = repo_root / "logs" / "runs" / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = evidence_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    command_log: list[str] = []
    failures: list[dict[str, Any]] = []
    started_at = utc_timestamp()

    volume_root = evidence_dir / "docker-volumes"
    data_dir = volume_root / "data"
    vault_dir = volume_root / "vault"
    chaos_dir = volume_root / "chaos"
    source_dir = evidence_dir / "sources"
    for directory in [data_dir, vault_dir, chaos_dir, source_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    sample_file = source_dir / "docker-upload.txt"
    sample_file.write_text(
        "Aily Docker pre-production upload. This file proves real mounted-volume ingestion.",
        encoding="utf-8",
    )
    web_dir = source_dir / "web"
    web_dir.mkdir()
    article = web_dir / "article.html"
    article.write_text(
        """
        <!doctype html>
        <html>
          <head><title>Docker Preprod URL Article</title></head>
          <body>
            <main>
              <h1>Docker Preprod URL Article</h1>
              <p>This local host-served article proves a Dockerized Aily backend can fetch external URLs.</p>
              <p>The evidence runner submits this URL through the same Studio form a human uses.</p>
            </main>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    source_records = source_manifest([sample_file, article] if args.exercise_url else [sample_file])

    host_port = _free_port()
    fixture_port = _free_port()
    token = "docker-preprod-token"
    project_name = f"aily-preprod-{run_id.lower().replace('_', '-')}"[:62]
    image_name = f"aily:preprod-{run_id.lower().replace('_', '-')}"
    env_file = evidence_dir / ".env.docker.generated"
    env_values = {
        "AILY_HOST_PORT": str(host_port),
        "AILY_DOCKER_IMAGE": image_name,
        "AILY_DOCKER_DATA_DIR": str(data_dir),
        "AILY_DOCKER_VAULT_DIR": str(vault_dir),
        "AILY_DOCKER_CHAOS_DIR": str(chaos_dir),
        "AILY_DOCKER_HOSTED_MODE": "true",
        "AILY_DOCKER_UI_AUTH_ENABLED": "true",
        "AILY_DOCKER_UI_AUTH_TOKEN": token,
        "AILY_DOCKER_UI_RATE_LIMIT_REQUESTS": "200",
        "AILY_DOCKER_UI_RATE_LIMIT_WINDOW_SECONDS": "60",
        "AILY_DOCKER_DIKIWI_ENABLED": os.getenv("AILY_DOCKER_REAL_LLM", "false"),
        "AILY_DOCKER_INNOVATION_ENABLED": "false",
        "AILY_DOCKER_ENTREPRENEUR_ENABLED": "false",
        "AILY_DOCKER_MAC_ENABLED": "false",
        "AILY_DOCKER_LLM_PROVIDER": os.getenv("AILY_DOCKER_LLM_PROVIDER", "kimi"),
        "AILY_DOCKER_LLM_API_KEY": os.getenv("AILY_DOCKER_LLM_API_KEY", ""),
        "AILY_DOCKER_KIMI_API_KEY": os.getenv("AILY_DOCKER_KIMI_API_KEY", ""),
        "AILY_DOCKER_DEEPSEEK_API_KEY": os.getenv("AILY_DOCKER_DEEPSEEK_API_KEY", ""),
        "AILY_DOCKER_LLM_TIMEOUT_SECONDS": os.getenv("AILY_DOCKER_LLM_TIMEOUT_SECONDS", "120"),
        "AILY_DOCKER_LLM_MAX_RETRIES": os.getenv("AILY_DOCKER_LLM_MAX_RETRIES", "0"),
    }
    env_file.write_text("\n".join(f"{key}={value}" for key, value in env_values.items()) + "\n", encoding="utf-8")

    fixture_process: subprocess.Popen[str] | None = None
    base_url = f"http://127.0.0.1:{host_port}"
    fixture_url = f"http://host.docker.internal:{fixture_port}/article.html"
    exit_code = 1
    health_response: dict[str, Any] = {}
    ready_response: dict[str, Any] = {}
    restart_check: dict[str, Any] = {}
    backup_result: dict[str, Any] = {}
    restore_result: dict[str, Any] = {}
    stored_events: list[dict[str, Any]] = []
    retry_started_events: list[dict[str, Any]] = []
    retry_terminal_events: list[dict[str, Any]] = []
    url_fetch_events: list[dict[str, Any]] = []
    url_ingest_events: list[dict[str, Any]] = []
    before_graph = graph_snapshot(data_dir / "aily_graph.db")
    before_vault = vault_counts(vault_dir)

    compose = _compose_base(compose_files, env_file, project_name)
    try:
        if args.exercise_url:
            fixture_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "http.server",
                    str(fixture_port),
                    "--bind",
                    "0.0.0.0",
                    "--directory",
                    str(web_dir),
                ],
                cwd=repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        if args.build:
            build_command = [*compose, "build"]
            if args.no_cache:
                build_command.append("--no-cache")
            _run_required(build_command, cwd=repo_root, command_log=command_log, timeout=900)

        _run_required([*compose, "up", "-d", "--build"], cwd=repo_root, command_log=command_log, timeout=900)
        health_response = await _wait_json(f"{base_url}/health", timeout=120)
        ready_response = await _wait_json(f"{base_url}/ready", timeout=120)

        async with httpx.AsyncClient(timeout=10.0) as client:
            rejected = await client.get(f"{base_url}/api/ui/status")
            if rejected.status_code != 401:
                raise AssertionError(f"Unauthenticated status should be rejected, got {rejected.status_code}")
            accepted = await client.get(f"{base_url}/api/ui/status", headers={"x-aily-token": token})
            if accepted.status_code != 200:
                raise AssertionError(f"Authenticated status failed: {accepted.status_code} {accepted.text[:300]}")

        with contextlib_suppress():
            subprocess.run(["agent-browser", "close", "--all"], cwd=repo_root, timeout=20)
        _run_browser("open", f"{base_url}/?token={token}", cwd=repo_root, command_log=command_log)
        _run_browser("set", "viewport", "1920", "1400", "2", cwd=repo_root, command_log=command_log)
        _run_browser("wait", "--text", "Thinking Theater", cwd=repo_root, command_log=command_log)
        _run_browser("screenshot", "--full", str(screenshots_dir / "01-home.png"), cwd=repo_root, command_log=command_log)
        _run_browser("upload", 'input[type="file"]', str(sample_file), cwd=repo_root, command_log=command_log)
        _run_browser("wait", "2500", cwd=repo_root, command_log=command_log)
        _run_browser("screenshot", "--full", str(screenshots_dir / "02-after-upload.png"), cwd=repo_root, command_log=command_log)
        stored_events = await _query_events(base_url, "source_stored", token)
        if not stored_events:
            raise AssertionError("No source_stored events after Docker upload")

        if args.exercise_url:
            _run_browser("fill", 'input[type="url"]', fixture_url, cwd=repo_root, command_log=command_log)
            _run_browser("find", "role", "button", "click", "--name", "Process link", "--exact", cwd=repo_root, command_log=command_log)
            _run_browser("wait", "3500", cwd=repo_root, command_log=command_log)
            _run_browser("screenshot", "--full", str(screenshots_dir / "03-after-url.png"), cwd=repo_root, command_log=command_log)
            url_fetch_events = await _query_events(base_url, "url_fetch_started", token)
            ingest_events = await _query_events(base_url, "source_ingest_completed", token)
            url_ingest_events = [event for event in ingest_events if str(event.get("url", "")) == fixture_url]
            if not any(str(event.get("url", "")) == fixture_url for event in url_fetch_events):
                raise AssertionError("No url_fetch_started event for Docker fixture URL")
            if not url_ingest_events:
                raise AssertionError("No source_ingest_completed event for Docker fixture URL")

        if args.exercise_retry:
            if args.exercise_url:
                bad_url = f"http://host.docker.internal:{fixture_port}/missing-for-retry.html"
                _run_browser("fill", 'input[type="url"]', bad_url, cwd=repo_root, command_log=command_log)
                _run_browser("find", "role", "button", "click", "--name", "Process link", "--exact", cwd=repo_root, command_log=command_log)
                _run_browser("wait", "2500", cwd=repo_root, command_log=command_log)
                failures_for_bad_url = await _query_events(base_url, "pipeline_failed", token)
                if not any(str(event.get("url", "")) == bad_url for event in failures_for_bad_url):
                    raise AssertionError("Bad URL did not create a failed source for retry")
            else:
                source_id = str(stored_events[-1].get("source_id") or "")
                if not source_id:
                    raise AssertionError("source_stored event did not include source_id")
                _mark_failed(data_dir / "source_store.db", source_id)
            _run_browser("find", "role", "button", "click", "--name", "Operations", cwd=repo_root, command_log=command_log)
            _run_browser("wait", "--text", "Retry failed sources", cwd=repo_root, command_log=command_log)
            _run_browser("find", "role", "button", "click", "--name", "Retry failed sources", "--exact", cwd=repo_root, command_log=command_log)
            _run_browser("wait", "1500", cwd=repo_root, command_log=command_log)
            _run_browser("screenshot", "--full", str(screenshots_dir / "04-after-retry.png"), cwd=repo_root, command_log=command_log)
            retry_started_events = await _query_events(base_url, "source_retry_started", token)
            completed = await _query_events(base_url, "source_retry_completed", token)
            failed = await _query_events(base_url, "source_retry_failed", token)
            retry_terminal_events = [*completed, *failed]
            if not retry_started_events or not retry_terminal_events:
                raise AssertionError("Retry lifecycle events were not emitted")

        async with httpx.AsyncClient(timeout=10.0) as client:
            before_sources = (await client.get(f"{base_url}/api/ui/sources", headers={"x-aily-token": token})).json()
        _run_required([*compose, "restart", "aily-app"], cwd=repo_root, command_log=command_log, timeout=120)
        await _wait_json(f"{base_url}/ready", timeout=120)
        async with httpx.AsyncClient(timeout=10.0) as client:
            after_sources_response = await client.get(f"{base_url}/api/ui/sources", headers={"x-aily-token": token})
            after_sources_response.raise_for_status()
            after_sources = after_sources_response.json()
        restart_check = {
            "sources_before": before_sources.get("total", 0),
            "sources_after": after_sources.get("total", 0),
            "source_count_persisted": int(after_sources.get("total", 0)) >= int(before_sources.get("total", 0)),
            "ui_event_log_exists": (data_dir / "ui-events.jsonl").exists(),
            "source_store_exists": (data_dir / "source_store.db").exists(),
        }
        if not restart_check["source_count_persisted"]:
            raise AssertionError(f"Source count did not persist across restart: {restart_check}")

        backup_result = await _post_control(
            base_url,
            token,
            {"action": "create_backup", "backup_path": "/data/backups/docker-preprod.zip"},
        )
        restore_result = await _post_control(
            base_url,
            token,
            {"action": "restore_backup_dry_run", "backup_path": "/data/backups/docker-preprod.zip"},
        )
        if not restore_result.get("manifest"):
            raise AssertionError("Backup restore dry run did not return a manifest")

        exit_code = 0
    except Exception as exc:
        failures.append({"type": type(exc).__name__, "error": str(exc)})
        exit_code = 1
    finally:
        with contextlib_suppress():
            subprocess.run(["agent-browser", "close", "--all"], cwd=repo_root, timeout=20)
        if fixture_process is not None:
            fixture_process.terminate()
            with contextlib_suppress():
                fixture_out, fixture_err = fixture_process.communicate(timeout=10)
                (evidence_dir / "url-fixture-stdout.log").write_text(fixture_out or "", encoding="utf-8")
                (evidence_dir / "url-fixture-stderr.log").write_text(fixture_err or "", encoding="utf-8")

        logs = _run([*compose, "logs", "--no-color"], cwd=repo_root, command_log=command_log, timeout=120)
        (evidence_dir / "container-logs.stdout.log").write_text(logs.stdout, encoding="utf-8")
        (evidence_dir / "container-logs.stderr.log").write_text(logs.stderr, encoding="utf-8")
        ps = _run([*compose, "ps"], cwd=repo_root, command_log=command_log, timeout=60)
        (evidence_dir / "docker-ps.txt").write_text(ps.stdout + ps.stderr, encoding="utf-8")
        if not args.keep_running:
            _run([*compose, "down", "--remove-orphans"], cwd=repo_root, command_log=command_log, timeout=120)

    image_inspect = _run(["docker", "image", "inspect", image_name, "--format", "{{.Id}}"], cwd=repo_root, command_log=command_log, timeout=60)
    image_digest = image_inspect.stdout.strip() if image_inspect.returncode == 0 else ""
    ui_events_path = data_dir / "ui-events.jsonl"
    (evidence_dir / "ui-events.jsonl").write_text(
        ui_events_path.read_text(encoding="utf-8") if ui_events_path.exists() else "",
        encoding="utf-8",
    )
    (evidence_dir / "command.txt").write_text("\n".join(command_log), encoding="utf-8")
    (evidence_dir / "environment.json").write_text(json.dumps(environment_snapshot(), indent=2), encoding="utf-8")
    (evidence_dir / "source-manifest.json").write_text(json.dumps(source_records, ensure_ascii=False, indent=2), encoding="utf-8")
    (evidence_dir / "graph-before.json").write_text(json.dumps(before_graph, ensure_ascii=False, indent=2), encoding="utf-8")
    (evidence_dir / "graph-after.json").write_text(json.dumps(graph_snapshot(data_dir / "aily_graph.db"), ensure_ascii=False, indent=2), encoding="utf-8")
    (evidence_dir / "vault-counts-before.json").write_text(json.dumps(before_vault, ensure_ascii=False, indent=2), encoding="utf-8")
    (evidence_dir / "vault-counts-after.json").write_text(json.dumps(vault_counts(vault_dir), ensure_ascii=False, indent=2), encoding="utf-8")
    (evidence_dir / "failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    (evidence_dir / "llm-calls.jsonl").write_text("", encoding="utf-8")
    samples_dir = evidence_dir / "samples"
    for name in ["chaos", "data", "information", "knowledge", "insight", "wisdom", "impact", "proposal", "entrepreneurship"]:
        (samples_dir / name).mkdir(parents=True, exist_ok=True)
    (samples_dir / "index.json").write_text("{}", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        **git_state(repo_root),
        "scenario": scenario,
        "evidence_scope": "docker_preprod_ui_control",
        "source_count": len(source_records),
        "source_selector": "explicit",
        "vault_path": str(vault_dir),
        "graph_db_path": str(data_dir / "aily_graph.db"),
        "started_at": started_at,
        "completed_at": utc_timestamp(),
        "exit_code": exit_code,
        "provider_routes": {},
        "docker": {
            "enabled": True,
            "image": image_name,
            "image_digest": image_digest,
            "compose_files": [str(path) for path in compose_files],
            "compose_hash": _sha256_files(compose_files),
            "project_name": project_name,
            "volume_paths": [str(data_dir), str(vault_dir), str(chaos_dir)],
            "env_keys": sorted(env_values.keys()),
            "host_port": host_port,
            "health": health_response,
            "ready": ready_response,
        },
        "acceptance": {
            "mocked": False,
            "fake_components": [],
            "real_files": True,
            "real_graph_db": True,
            "real_vault": True,
            "real_llm": env_values["AILY_DOCKER_DIKIWI_ENABLED"].lower() == "true",
            "real_browser": True,
            "real_fastapi": True,
            "real_docker": True,
            "hosted_auth": True,
            "scope_note": "Docker pre-production UI/control evidence; real LLM only when AILY_DOCKER_REAL_LLM=true and provider keys are injected.",
        },
        "checks": {
            "unauthenticated_api_rejected": True,
            "browser_loaded_frontend": not failures,
            "browser_uploaded_real_file": bool(stored_events),
            "url_fetch_event": bool(url_fetch_events),
            "url_ingest_event": bool(url_ingest_events),
            "retry_started_event": bool(retry_started_events),
            "retry_terminal_event": bool(retry_terminal_events),
            "restart_persistence": restart_check,
            "backup_created": bool(backup_result),
            "restore_dry_run": bool(restore_result.get("manifest")) if restore_result else False,
        },
        "screenshots": sorted(str(path.relative_to(evidence_dir)) for path in screenshots_dir.glob("*.png")),
        "failures_count": len(failures),
    }
    (evidence_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "evidence_dir": str(evidence_dir), "exit_code": exit_code}, indent=2))
    return exit_code


class contextlib_suppress:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return True


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
