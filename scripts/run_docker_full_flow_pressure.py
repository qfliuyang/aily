#!/usr/bin/env python3
"""Run Docker full-flow pressure evidence: 00-Chaos through 08-Entrepreneurship."""

from __future__ import annotations

import argparse
import json
import os
import random
import socket
import subprocess
import sys
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import httpx


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(command: list[str], *, cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def _run_required(command: list[str], *, cwd: Path, timeout: int = 120) -> str:
    result = _run(command, cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        stdout = result.stdout[-12000:] if len(result.stdout) > 12000 else result.stdout
        stderr = result.stderr[-12000:] if len(result.stderr) > 12000 else result.stderr
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
    return result.stdout


def _safe_write_text(path: Path, text: str, *, max_chars: int = 2_000_000) -> None:
    """Write bounded evidence without crashing when Docker fills the host volume."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[truncated: evidence log exceeded wrapper cap]\n"
        path.write_text(text, encoding="utf-8")
    except OSError:
        # The caller's primary failure should remain visible; evidence writing must not mask it.
        return


def _wait_ready(base_url: str, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base_url}/ready", timeout=3) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for Docker readiness: {last_error}")


def _select_pdfs(chaos_dir: Path, *, limit: int, seed: int) -> list[Path]:
    pdfs = sorted(path for path in chaos_dir.rglob("*.pdf") if path.is_file())
    if not pdfs:
        raise RuntimeError(f"No PDF files found in {chaos_dir}")
    rng = random.Random(seed)
    selected = list(pdfs)
    rng.shuffle(selected)
    return selected[: min(limit, len(selected))]


def _stage_counts(vault_dir: Path) -> dict[str, int]:
    stages = [
        "00-Chaos",
        "01-Data",
        "02-Information",
        "03-Knowledge",
        "04-Insight",
        "05-Wisdom",
        "06-Impact",
        "07-Proposal",
        "08-Entrepreneurship",
    ]
    return {
        stage: sum(1 for _ in (vault_dir / stage).rglob("*.md")) if (vault_dir / stage).exists() else 0
        for stage in stages
    }


def _post_studio_uploads(
    *,
    base_url: str,
    token: str,
    pdfs: list[Path],
    evidence_dir: Path,
    timeout: float,
) -> dict[str, object]:
    started_at = time.monotonic()
    files: list[tuple[str, tuple[str, object, str]]] = []
    handles = []
    try:
        for path in pdfs:
            handle = path.open("rb")
            handles.append(handle)
            files.append(("files", (path.name, handle, "application/pdf")))
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=30.0)) as client:
            response = client.post(
                f"{base_url}/api/ui/uploads",
                headers={"x-aily-token": token},
                files=files,
            )
            response.raise_for_status()
            payload = response.json()
    finally:
        for handle in handles:
            handle.close()
    _safe_write_text(evidence_dir / "studio-upload-response.json", json.dumps(payload, ensure_ascii=False, indent=2))
    return {
        "submitted": len(pdfs),
        "elapsed_seconds": round(time.monotonic() - started_at, 2),
        "response": payload,
    }


def _fetch_json(base_url: str, token: str, path: str, *, timeout: float = 10.0) -> dict[str, object]:
    with httpx.Client(timeout=timeout) as client:
        response = client.get(f"{base_url}{path}", headers={"x-aily-token": token})
        response.raise_for_status()
        return response.json()


def _wait_studio_processing(
    *,
    base_url: str,
    token: str,
    evidence_dir: Path,
    vault_dir: Path,
    timeout: float,
) -> tuple[bool, dict[str, object]]:
    deadline = time.monotonic() + timeout
    last_snapshot: dict[str, object] = {}
    samples: list[dict[str, object]] = []
    while time.monotonic() < deadline:
        status = _fetch_json(base_url, token, "/api/ui/status")
        sources = _fetch_json(base_url, token, "/api/ui/sources?limit=500")
        events = _fetch_json(base_url, token, "/api/ui/events/query?limit=500")
        counts = _stage_counts(vault_dir)
        source_items = list(sources.get("sources", []))
        active_uploads = list(status.get("active_uploads", []))
        terminal = {
            "completed",
            "failed",
            "cancelled",
        }
        source_statuses = [str(source.get("status", "")) for source in source_items]
        done = bool(source_items) and not active_uploads and all(status in terminal for status in source_statuses)
        business_ready = counts.get("07-Proposal", 0) > 0 and counts.get("08-Entrepreneurship", 0) > 0
        last_snapshot = {
            "done": done,
            "business_ready": business_ready,
            "status": status,
            "source_statuses": {status: source_statuses.count(status) for status in sorted(set(source_statuses))},
            "source_count": len(source_items),
            "event_count": len(events.get("events", [])),
            "stage_counts": counts,
        }
        samples.append({"elapsed_seconds": round(timeout - (deadline - time.monotonic()), 2), **last_snapshot})
        if done and business_ready:
            _safe_write_text(evidence_dir / "studio-processing-samples.json", json.dumps(samples, ensure_ascii=False, indent=2))
            _safe_write_text(evidence_dir / "studio-final-status.json", json.dumps(last_snapshot, ensure_ascii=False, indent=2))
            return True, last_snapshot
        time.sleep(10)
    _safe_write_text(evidence_dir / "studio-processing-samples.json", json.dumps(samples, ensure_ascii=False, indent=2))
    _safe_write_text(evidence_dir / "studio-final-status.json", json.dumps(last_snapshot, ensure_ascii=False, indent=2))
    return False, last_snapshot


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real Docker full-flow pressure evidence.")
    parser.add_argument("--max", type=int, default=10, help="Number of PDFs to process")
    parser.add_argument("--seed", type=int, default=260503)
    parser.add_argument("--phase-timeout", type=float, default=3600.0)
    parser.add_argument(
        "--build-timeout",
        type=int,
        default=3600,
        help="Seconds to allow for a cold Docker image build",
    )
    parser.add_argument(
        "--up-timeout",
        type=int,
        default=1800,
        help="Seconds to allow for Docker compose up/startup",
    )
    parser.add_argument("--build", action="store_true", help="Build image before running")
    parser.add_argument("--no-down", action="store_true", help="Leave Docker stack running")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    local_env = {**_load_env_file(repo_root / ".env"), **os.environ}
    run_id = datetime.now(timezone.utc).strftime(
        f"%Y-%m-%dT%H-%M-%SZ_docker_real_llm_full_flow_{args.max}pdf"
    )
    evidence_dir = repo_root / "logs" / "runs" / run_id
    data_dir = evidence_dir / "docker-volumes" / "data"
    vault_dir = evidence_dir / "docker-volumes" / "vault"
    data_dir.mkdir(parents=True, exist_ok=True)
    vault_dir.mkdir(parents=True, exist_ok=True)

    image_name = f"aily:full-flow-{run_id.lower().replace('_', '-')}"
    project_name = f"aily-full-flow-{run_id.lower().replace('_', '-')}"[:62]
    host_port = _free_port()
    env_file = evidence_dir / ".env.docker.generated"
    secret_env_dir = Path("/tmp/aily-docker-secrets")
    secret_env_dir.mkdir(parents=True, exist_ok=True)
    secret_env_file = secret_env_dir / f"{run_id}.env"
    secret_env_values = {
        "AILY_DOCKER_LLM_API_KEY": local_env.get("LLM_API_KEY", ""),
        "AILY_DOCKER_KIMI_API_KEY": local_env.get("KIMI_API_KEY", ""),
        "AILY_DOCKER_DEEPSEEK_API_KEY": local_env.get("DEEPSEEK_API_KEY", ""),
    }
    env_values = {
        "AILY_HOST_PORT": str(host_port),
        "AILY_DOCKER_IMAGE": image_name,
        "AILY_DOCKER_DATA_DIR": str(data_dir),
        "AILY_DOCKER_VAULT_DIR": str(vault_dir),
        "AILY_DOCKER_CHAOS_DIR": str(Path.home() / "aily_chaos"),
        "AILY_DOCKER_HOSTED_MODE": "true",
        "AILY_DOCKER_UI_AUTH_ENABLED": "true",
        "AILY_DOCKER_UI_AUTH_TOKEN": "docker-full-flow-token",
        "AILY_DOCKER_UI_MAX_UPLOAD_FILES": str(max(8, args.max)),
        "AILY_DOCKER_UI_MAX_ACTIVE_UPLOADS": str(max(16, args.max)),
        "AILY_DOCKER_UI_UPLOAD_CONCURRENCY": "2",
        "AILY_DOCKER_DIKIWI_ENABLED": "true",
        "AILY_DOCKER_INNOVATION_ENABLED": "true",
        "AILY_DOCKER_ENTREPRENEUR_ENABLED": "true",
        "AILY_DOCKER_MAC_ENABLED": "true",
        "AILY_DOCKER_LLM_PROVIDER": local_env.get("LLM_PROVIDER", "kimi"),
        "AILY_DOCKER_LLM_TIMEOUT_SECONDS": "600",
        "AILY_DOCKER_LLM_MAX_RETRIES": "1",
        "AILY_DOCKER_DIKIWI_INCREMENTAL_TRIGGER_RATIO": "0.05",
        "AILY_DOCKER_DIKIWI_NETWORK_MIN_NODES": "3",
        "AILY_DOCKER_DIKIWI_NETWORK_TRIGGER_SCORE": "4.0",
        "AILY_DOCKER_DIKIWI_NETWORK_MAX_CANDIDATE_NODES": "18",
        "AILY_DOCKER_DIKIWI_HIGHER_ORDER_MAX_CONTEXTS": "3",
        "AILY_DOCKER_DIKIWI_BATCH_STAGE_CONCURRENCY": "2",
        "AILY_DOCKER_DIKIWI_STAGE_TIMEOUT_SECONDS": "600",
        "AILY_DOCKER_REACTOR_METHOD_TIMEOUT_SECONDS": "300",
        "AILY_DOCKER_ENTREPRENEUR_EVALUATION_TIMEOUT_MINUTES": "3",
        "AILY_DOCKER_PROPOSAL_MAX_PER_SESSION": "4",
    }
    env_file.write_text("\n".join(f"{key}={value}" for key, value in env_values.items()), encoding="utf-8")
    secret_env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in secret_env_values.items()),
        encoding="utf-8",
    )
    secret_env_file.chmod(0o600)
    (evidence_dir / "run-metadata.txt").write_text(
        "\n".join(
            [
                f"run_id={run_id}",
                f"project={project_name}",
                f"image={image_name}",
                f"host_port={host_port}",
                f"max_pdfs={args.max}",
                "driver=studio_api_upload",
                "business_driver=studio_reactor_entrepreneur",
                f"provider_key_present={bool(secret_env_values['AILY_DOCKER_LLM_API_KEY'] or secret_env_values['AILY_DOCKER_KIMI_API_KEY'] or secret_env_values['AILY_DOCKER_DEEPSEEK_API_KEY'])}",
            ]
        ),
        encoding="utf-8",
    )

    compose = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "--env-file",
        str(secret_env_file),
        "-p",
        project_name,
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.preprod.yml",
    ]
    exit_code = 1
    try:
        up_command = [*compose, "up", "-d", "--build"]
        if args.build:
            _run_required([*compose, "build"], cwd=repo_root, timeout=args.build_timeout)
            up_command = [*compose, "up", "-d"]
        _run_required(up_command, cwd=repo_root, timeout=args.up_timeout)
        base_url = f"http://127.0.0.1:{host_port}"
        token = env_values["AILY_DOCKER_UI_AUTH_TOKEN"]
        _wait_ready(base_url)
        selected_pdfs = _select_pdfs(Path.home() / "aily_chaos", limit=args.max, seed=args.seed)
        _safe_write_text(
            evidence_dir / "selected-pdfs.txt",
            "\n".join(str(path) for path in selected_pdfs),
        )
        upload_result = _post_studio_uploads(
            base_url=base_url,
            token=token,
            pdfs=selected_pdfs,
            evidence_dir=evidence_dir,
            timeout=max(120.0, args.phase_timeout),
        )
        _safe_write_text(evidence_dir / "studio-upload-summary.json", json.dumps(upload_result, ensure_ascii=False, indent=2))
        completed, final_status = _wait_studio_processing(
            base_url=base_url,
            token=token,
            evidence_dir=evidence_dir,
            vault_dir=vault_dir,
            timeout=args.phase_timeout,
        )
        exit_code = 0 if completed else 1
        if final_status.get("source_statuses", {}).get("failed", 0):
            exit_code = 1
    finally:
        logs = _run([*compose, "logs", "--no-color"], cwd=repo_root, timeout=120)
        _safe_write_text(evidence_dir / "container-logs.stdout.log", logs.stdout)
        _safe_write_text(evidence_dir / "container-logs.stderr.log", logs.stderr)
        ps = _run([*compose, "ps"], cwd=repo_root, timeout=60)
        _safe_write_text(evidence_dir / "docker-ps.txt", ps.stdout + ps.stderr)
        with suppress(Exception):
            _safe_write_text(
                evidence_dir / "data-files.txt",
                "\n".join(str(path) for path in sorted(data_dir.rglob("*")) if path.is_file()),
            )
            _safe_write_text(
                evidence_dir / "vault-files.txt",
                "\n".join(str(path) for path in sorted(vault_dir.rglob("*")) if path.is_file()),
            )
        if not args.no_down:
            _run([*compose, "down", "--remove-orphans"], cwd=repo_root, timeout=120)
        with suppress(Exception):
            if not args.no_down:
                env_file.unlink()
        secret_env_file.unlink(missing_ok=True)
    print({"run_id": run_id, "evidence_dir": str(evidence_dir), "exit_code": exit_code})
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
