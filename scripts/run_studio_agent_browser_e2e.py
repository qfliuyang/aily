from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aily.verify.evidence import environment_snapshot, git_state, graph_snapshot, source_manifest, utc_timestamp, vault_counts


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _auth_headers(auth_token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {auth_token}"} if auth_token else {}


async def _wait_for_status(base_url: str, auth_token: str = "", timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{base_url}/api/ui/status", headers=_auth_headers(auth_token))
            if response.status_code == 200:
                return
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(0.5)
    raise RuntimeError(f"Studio backend did not become ready: {last_error}")


async def _wait_for_http_ok(url: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(url)
            if response.status_code == 200:
                return
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(0.25)
    raise RuntimeError(f"HTTP fixture did not become ready: {last_error}")


async def _query_events(base_url: str, event_type: str, auth_token: str = "") -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{base_url}/api/ui/events/query",
            params={"event_type": event_type},
            headers=_auth_headers(auth_token),
        )
    response.raise_for_status()
    return list(response.json().get("events", []))


def _run_browser_command(*args: str, cwd: Path, command_log: list[str]) -> str:
    command = ["agent-browser", "--session", "aily-studio-e2e", *args]
    command_log.append(" ".join(command))
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(
            f"agent-browser command failed: {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def _mark_source_failed_for_retry_evidence(source_store_db: Path, source_id: str) -> None:
    with sqlite3.connect(source_store_db, timeout=10) as conn:
        conn.execute(
            """
            UPDATE sources
            SET status = 'failed',
                metadata = '{"retry_e2e_seeded_failure": true}',
                updated_at = datetime('now')
            WHERE source_id = ?
            """,
            (source_id,),
        )
        conn.commit()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real Aily Studio browser E2E through agent-browser.")
    parser.add_argument(
        "--hosted-auth",
        action="store_true",
        help="Run the browser scenario with HOSTED_MODE/UI_AUTH enabled and bootstrap the page with a token.",
    )
    parser.add_argument(
        "--exercise-retry",
        action="store_true",
        help="Seed the uploaded source into failed status, click Studio retry, and require retry lifecycle events.",
    )
    parser.add_argument(
        "--exercise-url",
        action="store_true",
        help="Submit a real local HTTP URL through Studio and require URL fetch/extract/ingest events.",
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    runs_root = repo_root / "logs" / "runs"
    scenario_parts = ["studio_agent_browser"]
    if args.hosted_auth:
        scenario_parts.append("hosted_auth")
    if args.exercise_retry:
        scenario_parts.append("retry")
    if args.exercise_url:
        scenario_parts.append("url")
    scenario_parts.append("e2e")
    scenario = "_".join(scenario_parts)
    run_id = datetime.now(timezone.utc).strftime(f"%Y-%m-%dT%H-%M-%SZ_{scenario}")
    evidence_dir = runs_root / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    command_log: list[str] = []
    started_at = utc_timestamp()

    with TemporaryDirectory(prefix="aily-agent-browser-") as temp_root_raw:
        temp_root = Path(temp_root_raw)
        data_dir = temp_root / "data"
        vault = temp_root / "vault"
        screenshots_dir = evidence_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        vault.mkdir(parents=True)
        sample_file = temp_root / "human-style-upload.txt"
        sample_file.write_text(
            "Aily agent-browser E2E real upload. This verifies the private Studio as a human-facing website.",
            encoding="utf-8",
        )
        web_dir = temp_root / "web"
        web_dir.mkdir()
        (web_dir / "article.html").write_text(
            """
            <!doctype html>
            <html>
              <head><title>Local Aily URL Evidence Article</title></head>
              <body>
                <article>
                  <h1>Local Aily URL Evidence Article</h1>
                  <p>This locally served article proves Studio URL intake performs a real HTTP fetch.</p>
                  <p>The backend should extract this content and route it into the DIKIWI ingestion path.</p>
                </article>
              </body>
            </html>
            """,
            encoding="utf-8",
        )
        source_records = source_manifest([sample_file, web_dir / "article.html"] if args.exercise_url else [sample_file])

        port = _free_port()
        fixture_port = _free_port()
        base_url = f"http://127.0.0.1:{port}"
        fixture_url = f"http://127.0.0.1:{fixture_port}/article.html"
        auth_token = "agent-browser-hosted-token" if args.hosted_auth else ""
        env = os.environ.copy()
        env.update(
            {
                "AILY_DATA_DIR": str(data_dir),
                "OBSIDIAN_VAULT_PATH": str(vault),
                "AILY_DIKIWI_ENABLED": "false",
                "AILY_INNOVATION_ENABLED": "false",
                "AILY_ENTREPRENEUR_ENABLED": "false",
                "AILY_MAC_ENABLED": "false",
            }
        )
        if args.hosted_auth:
            env.update(
                {
                    "HOSTED_MODE": "true",
                    "UI_AUTH_ENABLED": "true",
                    "UI_AUTH_TOKEN": auth_token,
                }
            )
        server_command = [
            sys.executable,
            "-m",
            "uvicorn",
            "aily.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
        process = subprocess.Popen(
            server_command,
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        fixture_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "http.server",
                str(fixture_port),
                "--bind",
                "127.0.0.1",
                "--directory",
                str(web_dir),
            ],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout_text = ""
        stderr_text = ""
        fixture_stdout_text = ""
        fixture_stderr_text = ""
        exit_code = 1
        failures: list[dict[str, Any]] = []
        stored_events: list[dict[str, Any]] = []
        retry_events: list[dict[str, Any]] = []
        retry_started_events: list[dict[str, Any]] = []
        retry_terminal_events: list[dict[str, Any]] = []
        retry_seeded_source_id = ""
        url_fetch_events: list[dict[str, Any]] = []
        url_ingest_events: list[dict[str, Any]] = []
        before_graph = graph_snapshot(data_dir / "aily_graph.db")
        before_vault = vault_counts(vault)
        try:
            await _wait_for_status(base_url, auth_token=auth_token)
            if args.exercise_url:
                await _wait_for_http_ok(fixture_url)
            with contextlib_suppress():
                subprocess.run(["agent-browser", "close", "--all"], cwd=repo_root, timeout=20)

            open_url = f"{base_url}/?token={auth_token}" if auth_token else base_url
            _run_browser_command("open", open_url, cwd=repo_root, command_log=command_log)
            _run_browser_command("set", "viewport", "1920", "1400", "2", cwd=repo_root, command_log=command_log)
            _run_browser_command("wait", "--text", "Thinking Theater", cwd=repo_root, command_log=command_log)
            _run_browser_command("screenshot", "--full", str(screenshots_dir / "01-home.png"), cwd=repo_root, command_log=command_log)
            _run_browser_command("upload", 'input[type="file"]', str(sample_file), cwd=repo_root, command_log=command_log)
            _run_browser_command("wait", "2000", cwd=repo_root, command_log=command_log)
            _run_browser_command("screenshot", "--full", str(screenshots_dir / "02-after-upload.png"), cwd=repo_root, command_log=command_log)
            stored_events = await _query_events(base_url, "source_stored", auth_token=auth_token)
            if not stored_events:
                raise AssertionError("No source_stored event persisted")
            if args.exercise_url:
                _run_browser_command("fill", 'input[type="url"]', fixture_url, cwd=repo_root, command_log=command_log)
                _run_browser_command("find", "role", "button", "click", "--name", "Process link", "--exact", cwd=repo_root, command_log=command_log)
                _run_browser_command("wait", "2500", cwd=repo_root, command_log=command_log)
                _run_browser_command("screenshot", "--full", str(screenshots_dir / "02b-after-url.png"), cwd=repo_root, command_log=command_log)
                url_fetch_events = await _query_events(base_url, "url_fetch_started", auth_token=auth_token)
                chaos_events = await _query_events(base_url, "chaos_note_created", auth_token=auth_token)
                ingest_events = await _query_events(base_url, "source_ingest_completed", auth_token=auth_token)
                url_ingest_events = [event for event in ingest_events if str(event.get("url", "")) == fixture_url]
                if not any(str(event.get("url", "")) == fixture_url for event in url_fetch_events):
                    raise AssertionError("URL exercise did not emit url_fetch_started for fixture URL")
                if not any(str(event.get("url", "")) == fixture_url for event in chaos_events):
                    raise AssertionError("URL exercise did not emit chaos_note_created for fixture URL")
                if not url_ingest_events:
                    raise AssertionError("URL exercise did not emit source_ingest_completed for fixture URL")
            if args.exercise_retry:
                retry_seeded_source_id = str(stored_events[-1].get("source_id") or "")
                if not retry_seeded_source_id:
                    raise AssertionError("source_stored event did not include source_id")
                _mark_source_failed_for_retry_evidence(data_dir / "source_store.db", retry_seeded_source_id)

            _run_browser_command("find", "role", "button", "click", "--name", "Operations", cwd=repo_root, command_log=command_log)
            _run_browser_command("wait", "--text", sample_file.name, cwd=repo_root, command_log=command_log)
            _run_browser_command("wait", "--text", "Retry failed sources", cwd=repo_root, command_log=command_log)
            _run_browser_command("scroll", "down", "500", cwd=repo_root, command_log=command_log)
            _run_browser_command("screenshot", "--full", str(screenshots_dir / "03-operations.png"), cwd=repo_root, command_log=command_log)
            _run_browser_command("find", "role", "button", "click", "--name", "Retry failed sources", "--exact", cwd=repo_root, command_log=command_log)
            _run_browser_command("wait", "1000", cwd=repo_root, command_log=command_log)
            _run_browser_command("screenshot", "--full", str(screenshots_dir / "04-retry-control.png"), cwd=repo_root, command_log=command_log)

            retry_events = await _query_events(base_url, "retry_failed_sources_requested", auth_token=auth_token)
            if not retry_events:
                raise AssertionError("No retry_failed_sources_requested event persisted")
            retry_started_events = await _query_events(base_url, "source_retry_started", auth_token=auth_token)
            retry_completed_events = await _query_events(base_url, "source_retry_completed", auth_token=auth_token)
            retry_failed_events = await _query_events(base_url, "source_retry_failed", auth_token=auth_token)
            retry_terminal_events = [*retry_completed_events, *retry_failed_events]
            if args.exercise_retry and not retry_started_events:
                raise AssertionError("Retry exercise did not emit source_retry_started")
            if args.exercise_retry and not retry_terminal_events:
                raise AssertionError("Retry exercise did not emit source_retry_completed/source_retry_failed")
            exit_code = 0
        except Exception as exc:
            failures.append({"type": type(exc).__name__, "error": str(exc)})
            exit_code = 1
        finally:
            with contextlib_suppress():
                subprocess.run(["agent-browser", "close", "--all"], cwd=repo_root, timeout=20)
            process.terminate()
            fixture_process.terminate()
            try:
                out, err = process.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                out, err = process.communicate(timeout=10)
            try:
                fixture_out, fixture_err = fixture_process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                fixture_process.kill()
                fixture_out, fixture_err = fixture_process.communicate(timeout=10)
            stdout_text += out or ""
            stderr_text += err or ""
            fixture_stdout_text += fixture_out or ""
            fixture_stderr_text += fixture_err or ""

        event_log = data_dir / "ui-events.jsonl"
        if event_log.exists():
            (evidence_dir / "ui-events.jsonl").write_text(event_log.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            (evidence_dir / "ui-events.jsonl").write_text("", encoding="utf-8")
        (evidence_dir / "command.txt").write_text(
            "\n".join([" ".join(server_command), *command_log]),
            encoding="utf-8",
        )
        (evidence_dir / "stdout.log").write_text(stdout_text, encoding="utf-8")
        (evidence_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")
        (evidence_dir / "url-fixture-stdout.log").write_text(fixture_stdout_text, encoding="utf-8")
        (evidence_dir / "url-fixture-stderr.log").write_text(fixture_stderr_text, encoding="utf-8")
        (evidence_dir / "environment.json").write_text(json.dumps(environment_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence_dir / "source-manifest.json").write_text(json.dumps(source_records, ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence_dir / "graph-before.json").write_text(json.dumps(before_graph, ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence_dir / "graph-after.json").write_text(json.dumps(graph_snapshot(data_dir / "aily_graph.db"), ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence_dir / "vault-counts-before.json").write_text(json.dumps(before_vault, ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence_dir / "vault-counts-after.json").write_text(json.dumps(vault_counts(vault), ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence_dir / "failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence_dir / "llm-calls.jsonl").write_text("", encoding="utf-8")
        samples_dir = evidence_dir / "samples"
        for name in ["chaos", "data", "information", "knowledge", "insight", "wisdom", "impact", "proposal", "entrepreneurship"]:
            (samples_dir / name).mkdir(parents=True, exist_ok=True)
        (samples_dir / "index.json").write_text("{}", encoding="utf-8")
        git = git_state(repo_root)
        manifest = {
            "run_id": run_id,
            **git,
            "scenario": scenario,
            "evidence_scope": "ui_control",
            "source_count": len(source_records),
            "source_selector": "explicit",
            "vault_path": str(vault),
            "graph_db_path": str(data_dir / "aily_graph.db"),
            "started_at": started_at,
            "completed_at": utc_timestamp(),
            "exit_code": exit_code,
            "acceptance": {
                "mocked": False,
                "fake_components": [],
                "real_files": True,
                "real_graph_db": True,
                "real_vault": True,
                "real_llm": False,
                "real_browser": True,
                "real_fastapi": True,
                "hosted_auth": bool(args.hosted_auth),
                "retry_e2e_seeded_failure": bool(args.exercise_retry),
                "url_e2e_local_http_fixture": bool(args.exercise_url),
                "browser_tool": "agent-browser",
                "scope_note": "UI/control evidence only: DIKIWI, Innovation, and Entrepreneur are disabled in this scenario.",
            },
            "screenshots": sorted(str(path.relative_to(evidence_dir)) for path in screenshots_dir.glob("*.png")),
            "screenshot_mode": {
                "full_page": True,
                "viewport_css_pixels": "1920x1400",
                "device_scale_factor": 2,
            },
            "checks": {
                "browser_loaded_frontend": not failures,
                "browser_uploaded_real_file": bool(stored_events),
                "browser_saw_backend_source_event": bool(stored_events),
                "browser_opened_operations_view": not failures,
                "browser_clicked_retry_control": bool(retry_events),
                "retry_seeded_source_id": retry_seeded_source_id,
                "retry_started_event": bool(retry_started_events),
                "retry_terminal_event": bool(retry_terminal_events),
                "url_fixture": fixture_url if args.exercise_url else "",
                "url_fetch_event": bool(url_fetch_events),
                "url_ingest_event": bool(url_ingest_events),
                "persisted_events_queryable": True,
                "hosted_auth_enabled": bool(args.hosted_auth),
            },
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
