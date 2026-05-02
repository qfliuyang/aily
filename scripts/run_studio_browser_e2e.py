from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for_status(base_url: str, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{base_url}/api/ui/status")
            if response.status_code == 200:
                return
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(0.5)
    raise RuntimeError(f"Studio backend did not become ready: {last_error}")


async def _query_events(base_url: str, event_type: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{base_url}/api/ui/events/query", params={"event_type": event_type})
    response.raise_for_status()
    return list(response.json().get("events", []))


async def _run_browser(base_url: str, sample_file: Path) -> None:
    from playwright.async_api import async_playwright, expect

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(base_url, wait_until="networkidle")
        await expect(page.get_by_role("heading", name="Thinking Theater").first).to_be_visible()
        async with page.expect_response(lambda response: "/api/ui/uploads" in response.url) as upload_response:
            await page.set_input_files('input[type="file"]', str(sample_file))
        response = await upload_response.value
        if not response.ok:
            raise AssertionError(f"Upload failed with {response.status}: {await response.text()}")
        await page.get_by_role("button", name="Operations").click()
        await expect(page.get_by_text(sample_file.name).first).to_be_visible(timeout=30000)
        await page.get_by_role("button", name="Retry failed sources").click()
        await expect(page.get_by_text("retry_failed_sources_requested")).to_be_visible(timeout=30000)
        await browser.close()


async def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    runs_root = repo_root / "logs" / "runs"
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ_studio_browser_e2e")
    evidence_dir = runs_root / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="aily-studio-browser-") as temp_root_raw:
        temp_root = Path(temp_root_raw)
        data_dir = temp_root / "data"
        vault = temp_root / "vault"
        vault.mkdir(parents=True)
        sample_file = temp_root / "studio-real-upload.txt"
        sample_file.write_text(
            "Aily Studio browser E2E real upload. This file is intentionally small and processed by the real FastAPI upload path.",
            encoding="utf-8",
        )

        port = _free_port()
        base_url = f"http://127.0.0.1:{port}"
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
        command = [
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
            command,
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout_text = ""
        stderr_text = ""
        exit_code = 1
        try:
            await _wait_for_status(base_url)
            await _run_browser(base_url, sample_file)
            stored_events = await _query_events(base_url, "source_stored")
            retry_events = await _query_events(base_url, "retry_failed_sources_requested")
            if not stored_events:
                raise AssertionError("No source_stored event persisted")
            if not retry_events:
                raise AssertionError("No retry_failed_sources_requested event persisted")

            process.terminate()
            try:
                stdout_text, stderr_text = process.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout_text, stderr_text = process.communicate(timeout=10)

            process = subprocess.Popen(
                command,
                cwd=repo_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            await _wait_for_status(base_url)
            replayed_events = await _query_events(base_url, "source_stored")
            if not replayed_events:
                raise AssertionError("Persisted source_stored event was not queryable after restart")
            exit_code = 0
        finally:
            process.terminate()
            try:
                out, err = process.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                out, err = process.communicate(timeout=10)
            stdout_text += out or ""
            stderr_text += err or ""

        (evidence_dir / "command.txt").write_text(" ".join(command), encoding="utf-8")
        (evidence_dir / "stdout.log").write_text(stdout_text, encoding="utf-8")
        (evidence_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")
        event_log = data_dir / "ui-events.jsonl"
        if event_log.exists():
            (evidence_dir / "ui-events.jsonl").write_text(event_log.read_text(encoding="utf-8"), encoding="utf-8")
        manifest = {
            "run_id": run_id,
            "scenario": "studio_browser_e2e",
            "source_count": 1,
            "source_selector": "explicit",
            "source_seed": None,
            "vault_path": str(vault),
            "graph_db_path": str(data_dir / "aily_graph.db"),
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
            },
            "checks": {
                "browser_loaded_frontend": True,
                "browser_uploaded_real_file": True,
                "persisted_source_stored_event": True,
                "websocket_rendered_retry_event": True,
                "control_endpoint_emitted_retry_event": True,
                "persisted_events_queryable_after_restart": True,
            },
        }
        (evidence_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({"run_id": run_id, "evidence_dir": str(evidence_dir), "exit_code": exit_code}, indent=2))
        return exit_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
