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


def _run_browser_command(*args: str, cwd: Path, command_log: list[str]) -> str:
    command = ["agent-browser", "--session", "aily-studio-e2e", *args]
    command_log.append(" ".join(command))
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(
            f"agent-browser command failed: {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


async def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    runs_root = repo_root / "logs" / "runs"
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ_studio_agent_browser_e2e")
    evidence_dir = runs_root / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    command_log: list[str] = []

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
        stdout_text = ""
        stderr_text = ""
        exit_code = 1
        try:
            await _wait_for_status(base_url)
            with contextlib_suppress():
                subprocess.run(["agent-browser", "close", "--all"], cwd=repo_root, timeout=20)

            _run_browser_command("open", base_url, cwd=repo_root, command_log=command_log)
            _run_browser_command("set", "viewport", "1920", "1400", "2", cwd=repo_root, command_log=command_log)
            _run_browser_command("wait", "--text", "Thinking Theater", cwd=repo_root, command_log=command_log)
            _run_browser_command("screenshot", "--full", str(screenshots_dir / "01-home.png"), cwd=repo_root, command_log=command_log)
            _run_browser_command("upload", 'input[type="file"]', str(sample_file), cwd=repo_root, command_log=command_log)
            _run_browser_command("wait", "2000", cwd=repo_root, command_log=command_log)
            _run_browser_command("screenshot", "--full", str(screenshots_dir / "02-after-upload.png"), cwd=repo_root, command_log=command_log)
            _run_browser_command("find", "role", "button", "click", "--name", "Operations", cwd=repo_root, command_log=command_log)
            _run_browser_command("wait", "--text", sample_file.name, cwd=repo_root, command_log=command_log)
            _run_browser_command("wait", "--text", "Retry failed sources", cwd=repo_root, command_log=command_log)
            _run_browser_command("scroll", "down", "500", cwd=repo_root, command_log=command_log)
            _run_browser_command("screenshot", "--full", str(screenshots_dir / "03-operations.png"), cwd=repo_root, command_log=command_log)
            _run_browser_command("find", "role", "button", "click", "--name", "Retry failed sources", "--exact", cwd=repo_root, command_log=command_log)
            _run_browser_command("wait", "1000", cwd=repo_root, command_log=command_log)
            _run_browser_command("screenshot", "--full", str(screenshots_dir / "04-retry-control.png"), cwd=repo_root, command_log=command_log)

            stored_events = await _query_events(base_url, "source_stored")
            retry_events = await _query_events(base_url, "retry_failed_sources_requested")
            if not stored_events:
                raise AssertionError("No source_stored event persisted")
            if not retry_events:
                raise AssertionError("No retry_failed_sources_requested event persisted")
            exit_code = 0
        finally:
            with contextlib_suppress():
                subprocess.run(["agent-browser", "close", "--all"], cwd=repo_root, timeout=20)
            process.terminate()
            try:
                out, err = process.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                out, err = process.communicate(timeout=10)
            stdout_text += out or ""
            stderr_text += err or ""

        event_log = data_dir / "ui-events.jsonl"
        if event_log.exists():
            (evidence_dir / "ui-events.jsonl").write_text(event_log.read_text(encoding="utf-8"), encoding="utf-8")
        (evidence_dir / "command.txt").write_text(
            "\n".join([" ".join(server_command), *command_log]),
            encoding="utf-8",
        )
        (evidence_dir / "stdout.log").write_text(stdout_text, encoding="utf-8")
        (evidence_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")
        manifest = {
            "run_id": run_id,
            "scenario": "studio_agent_browser_e2e",
            "source_count": 1,
            "source_selector": "explicit",
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
                "browser_tool": "agent-browser",
            },
            "screenshots": sorted(str(path.relative_to(evidence_dir)) for path in screenshots_dir.glob("*.png")),
            "screenshot_mode": {
                "full_page": True,
                "viewport_css_pixels": "1920x1400",
                "device_scale_factor": 2,
            },
            "checks": {
                "browser_loaded_frontend": True,
                "browser_uploaded_real_file": True,
                "browser_saw_backend_source_event": True,
                "browser_opened_operations_view": True,
                "browser_clicked_retry_control": bool(retry_events),
                "persisted_events_queryable": True,
            },
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
