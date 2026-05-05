#!/usr/bin/env python3
"""Run a real Studio upload soak test with human-like random PDF drops."""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import httpx


STAGES = [
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


def _utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _write_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _wait_ready(base_url: str, timeout: float) -> None:
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
    raise TimeoutError(f"Studio backend was not ready before timeout: {last_error}")


def _all_pdfs(chaos_dir: Path) -> list[Path]:
    pdfs = sorted(path for path in chaos_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf")
    if not pdfs:
        raise RuntimeError(f"No PDFs found under {chaos_dir}")
    return pdfs


def _vault_counts(vault_dir: Path) -> dict[str, int]:
    return {
        stage: sum(1 for _ in (vault_dir / stage).rglob("*.md")) if (vault_dir / stage).exists() else 0
        for stage in STAGES
    }


def _fetch_json(client: httpx.Client, base_url: str, token: str, path: str) -> dict[str, Any]:
    headers = {"x-aily-token": token} if token else {}
    response = client.get(f"{base_url}{path}", headers=headers)
    response.raise_for_status()
    return response.json()


def _export_event_pages(
    *,
    client: httpx.Client,
    base_url: str,
    token: str,
    run_dir: Path,
    page_limit: int = 5000,
) -> dict[str, Any]:
    """Export the complete persisted Studio event stream using seq pagination."""
    after_seq: int | None = 0
    page_index = 0
    total_events = 0
    max_seq = 0
    pages_dir = run_dir / "event-pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    while True:
        path = f"/api/ui/events/query?limit={page_limit}"
        path += f"&after_seq={after_seq}"
        payload = _fetch_json(client, base_url, token, path)
        events = list(payload.get("events", []))
        if not events:
            break
        page_index += 1
        _write_json(pages_dir / f"events-{page_index:05d}.json", payload)
        total_events += len(events)
        max_seq = max(max_seq, max(int(event.get("seq") or 0) for event in events))
        next_after_seq = payload.get("next_after_seq")
        after_seq = int(next_after_seq or max_seq)
        if len(events) < page_limit:
            break

    manifest = {
        "page_count": page_index,
        "event_count": total_events,
        "max_seq": max_seq,
        "page_limit": page_limit,
    }
    _write_json(run_dir / "event-pages-manifest.json", manifest)
    return manifest


def _write_partial_summary(
    *,
    run_dir: Path,
    drops: int,
    submitted_files: int,
    errors: int,
    latest_snapshot: dict[str, Any],
    started_at: float,
    label: str,
) -> None:
    failed_sources = int(latest_snapshot.get("source_status_counts", {}).get("failed", 0))
    exhausted_sources = int(latest_snapshot.get("source_status_counts", {}).get("failed_retry_exhausted", 0))
    retry_pending_sources = int(latest_snapshot.get("source_status_counts", {}).get("retry_pending", 0))
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "elapsed_seconds": round(time.monotonic() - started_at, 2),
        "drops": drops,
        "submitted_files": submitted_files,
        "errors": errors,
        "failed_sources": failed_sources,
        "failed_retry_exhausted_sources": exhausted_sources,
        "retry_pending_sources": retry_pending_sources,
        "latest_snapshot": latest_snapshot,
    }
    _write_json(run_dir / "partial-summary.json", summary)
    _write_jsonl(run_dir / "partial-summaries.jsonl", summary)


def _sample_state(
    *,
    client: httpx.Client,
    base_url: str,
    token: str,
    vault_dir: Path,
    run_dir: Path,
    started_at: float,
) -> dict[str, Any]:
    status = _fetch_json(client, base_url, token, "/api/ui/status")
    sources = _fetch_json(client, base_url, token, "/api/ui/sources?limit=500")
    events = _fetch_json(client, base_url, token, "/api/ui/events/query?limit=2000")
    proposals = _fetch_json(client, base_url, token, "/api/ui/proposals?limit=100")
    entrepreneurship = _fetch_json(client, base_url, token, "/api/ui/entrepreneurship?limit=100")
    graph = _fetch_json(client, base_url, token, "/api/ui/graph")
    source_items = list(sources.get("sources", []))
    source_status_counts = Counter(str(source.get("status", "")) for source in source_items)
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.monotonic() - started_at, 2),
        "active_uploads": status.get("active_uploads", []),
        "active_pipelines": status.get("active_pipelines", []),
        "source_total": sources.get("total", len(source_items)),
        "source_status_counts": dict(source_status_counts),
        "source_jobs": status.get("source_jobs", {}),
        "event_count": len(events.get("events", [])),
        "latest_event_seq": max(
            [int(event.get("seq") or 0) for event in events.get("events", [])],
            default=0,
        ),
        "graph_nodes": len(graph.get("nodes", [])),
        "graph_edges": len(graph.get("edges", [])),
        "proposal_notes": proposals.get("total", 0),
        "entrepreneurship_notes": entrepreneurship.get("total", 0),
        "vault_counts": _vault_counts(vault_dir),
    }
    _write_jsonl(run_dir / "samples.jsonl", snapshot)
    return snapshot


def _post_drop(
    *,
    client: httpx.Client,
    base_url: str,
    token: str,
    pdfs: list[Path],
    timeout: float,
) -> dict[str, Any]:
    files: list[tuple[str, tuple[str, Any, str]]] = []
    handles = []
    try:
        for path in pdfs:
            handle = path.open("rb")
            handles.append(handle)
            files.append(("files", (path.name, handle, "application/pdf")))
        headers = {"x-aily-token": token} if token else {}
        response = client.post(
            f"{base_url}/api/ui/uploads",
            headers=headers,
            files=files,
            timeout=httpx.Timeout(timeout, connect=30.0),
        )
        payload: dict[str, Any]
        try:
            payload = response.json()
        except Exception:
            payload = {"text": response.text[:2000]}
        if response.status_code >= 400:
            return {"ok": False, "status_code": response.status_code, "payload": payload}
        return {"ok": True, "status_code": response.status_code, "payload": payload}
    finally:
        for handle in handles:
            handle.close()


def _next_batch_size(rng: random.Random, max_batch: int) -> int:
    candidates = [1, 1, 1, 1, 2, 2, 3, 5, 8, 13, max_batch]
    return max(1, min(max_batch, int(rng.choice(candidates))))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a real human-like Aily Studio PDF drop soak test.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", default="")
    parser.add_argument("--chaos-dir", type=Path, default=Path.home() / "aily_chaos")
    parser.add_argument("--vault-dir", type=Path, default=Path.home() / "Documents" / "aily" / "aily")
    parser.add_argument("--duration-seconds", type=float, default=5 * 60 * 60)
    parser.add_argument("--settle-seconds", type=float, default=30 * 60)
    parser.add_argument("--min-wait-seconds", type=float, default=90)
    parser.add_argument("--max-wait-seconds", type=float, default=12 * 60)
    parser.add_argument("--max-batch-size", type=int, default=25)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--upload-timeout", type=float, default=600)
    parser.add_argument("--ready-timeout", type=float, default=120)
    parser.add_argument("--run-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    seed = args.seed if args.seed is not None else int(time.time())
    rng = random.Random(seed)
    run_dir = args.run_dir or Path("logs") / "runs" / f"{_utc_id()}_studio_human_drop_soak"
    run_dir.mkdir(parents=True, exist_ok=True)
    pdf_pool = _all_pdfs(args.chaos_dir)
    shuffled = list(pdf_pool)
    rng.shuffle(shuffled)
    cursor = 0
    started_at = time.monotonic()
    deadline = started_at + args.duration_seconds
    errors = 0
    drops = 0
    submitted_files = 0

    _write_json(
        run_dir / "metadata.json",
        {
            "scenario": "studio_human_drop_soak",
            "base_url": args.base_url,
            "chaos_dir": str(args.chaos_dir),
            "vault_dir": str(args.vault_dir),
            "duration_seconds": args.duration_seconds,
            "settle_seconds": args.settle_seconds,
            "min_wait_seconds": args.min_wait_seconds,
            "max_wait_seconds": args.max_wait_seconds,
            "max_batch_size": args.max_batch_size,
            "seed": seed,
            "pdf_pool_count": len(pdf_pool),
        },
    )
    (run_dir / "pdf-pool.txt").write_text("\n".join(str(path) for path in pdf_pool), encoding="utf-8")
    _wait_ready(args.base_url, args.ready_timeout)

    with httpx.Client(timeout=30.0) as client:
        while time.monotonic() < deadline:
            batch_size = _next_batch_size(rng, args.max_batch_size)
            if cursor + batch_size > len(shuffled):
                rng.shuffle(shuffled)
                cursor = 0
            chosen = shuffled[cursor : cursor + batch_size]
            cursor += batch_size
            drop_started = time.monotonic()
            result = _post_drop(
                client=client,
                base_url=args.base_url,
                token=args.token,
                pdfs=chosen,
                timeout=args.upload_timeout,
            )
            drops += 1
            submitted_files += len(chosen)
            drop_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": round(time.monotonic() - started_at, 2),
                "drop_index": drops,
                "file_count": len(chosen),
                "files": [str(path) for path in chosen],
                "elapsed_upload_seconds": round(time.monotonic() - drop_started, 2),
                **result,
            }
            _write_jsonl(run_dir / "drops.jsonl", drop_record)
            if not result.get("ok"):
                errors += 1
                _write_jsonl(run_dir / "errors.jsonl", drop_record)
            try:
                snapshot = _sample_state(
                    client=client,
                    base_url=args.base_url,
                    token=args.token,
                    vault_dir=args.vault_dir,
                    run_dir=run_dir,
                    started_at=started_at,
                )
                _write_partial_summary(
                    run_dir=run_dir,
                    drops=drops,
                    submitted_files=submitted_files,
                    errors=errors,
                    latest_snapshot=snapshot,
                    started_at=started_at,
                    label="drop_sample",
                )
            except Exception as exc:
                errors += 1
                _write_jsonl(
                    run_dir / "errors.jsonl",
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "elapsed_seconds": round(time.monotonic() - started_at, 2),
                        "error": f"sample_state_failed: {exc}",
                    },
                )
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0:
                break
            time.sleep(min(remaining, rng.uniform(args.min_wait_seconds, args.max_wait_seconds)))

        settle_deadline = time.monotonic() + args.settle_seconds
        while time.monotonic() < settle_deadline:
            snapshot = _sample_state(
                client=client,
                base_url=args.base_url,
                token=args.token,
                vault_dir=args.vault_dir,
                run_dir=run_dir,
                started_at=started_at,
            )
            _write_partial_summary(
                run_dir=run_dir,
                drops=drops,
                submitted_files=submitted_files,
                errors=errors,
                latest_snapshot=snapshot,
                started_at=started_at,
                label="settle_sample",
            )
            if not snapshot["active_uploads"] and not snapshot["active_pipelines"]:
                break
            time.sleep(30)
        final_snapshot = _sample_state(
            client=client,
            base_url=args.base_url,
            token=args.token,
            vault_dir=args.vault_dir,
            run_dir=run_dir,
            started_at=started_at,
        )
        event_pages = _export_event_pages(
            client=client,
            base_url=args.base_url,
            token=args.token,
            run_dir=run_dir,
        )

    failed_sources = int(final_snapshot.get("source_status_counts", {}).get("failed", 0))
    summary = {
        "run_dir": str(run_dir),
        "drops": drops,
        "submitted_files": submitted_files,
        "errors": errors,
        "failed_sources": failed_sources,
        "final_snapshot": final_snapshot,
        "event_pages": event_pages,
        "exit_code": 1 if errors or failed_sources else 0,
    }
    _write_json(run_dir / "final-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return int(summary["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
