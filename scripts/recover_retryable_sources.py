#!/usr/bin/env python3
"""Recover timeout/provider-failed sources into retryable queued work."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aily.config import SETTINGS
from aily.source_store import SourceStore


RETRYABLE_MARKERS = (
    "timed out",
    "timeout",
    "llm failed",
    "provider",
    "rate limit",
    "temporarily",
    "connection",
    "network",
    "circuit breaker",
)


def _is_retryable(error: str) -> bool:
    lowered = (error or "").lower()
    return any(marker in lowered for marker in RETRYABLE_MARKERS)


async def _run(args: argparse.Namespace) -> int:
    store = SourceStore(args.db_path, args.object_dir)
    await store.initialize()
    recovered: list[dict] = []
    skipped: list[dict] = []
    try:
        listing = await store.list_sources(limit=args.limit)
        for source in listing["sources"]:
            status = str(source.get("status") or "")
            if status not in {"failed", "failed_retry_exhausted"}:
                continue
            metadata = source.get("metadata") or {}
            error = str(metadata.get("error") or metadata.get("last_error") or "")
            source_id = str(source["source_id"])
            try:
                await store.read_stored_object(source_id)
            except Exception as exc:
                skipped.append({"source_id": source_id, "reason": f"missing_object: {exc}"})
                continue
            if not _is_retryable(error):
                skipped.append({"source_id": source_id, "reason": f"not_retryable: {error}"})
                continue
            recovered.append({"source_id": source_id, "filename": source.get("filename"), "error": error})
            if args.dry_run:
                continue
            await store.mark_retry_pending(
                source_id,
                error=error,
                stage=str(metadata.get("last_failed_stage") or ""),
                pipeline_id=str(metadata.get("pipeline_id") or ""),
                retry_delay_seconds=0,
            )
            await store.enqueue_source_job(
                source_id=source_id,
                job_type="process_upload_source",
                payload={
                    "upload_id": f"recovery-{source_id.split(':', 1)[-1][:12]}",
                    "filename": source.get("filename") or source_id,
                    "content_type": source.get("content_type") or "application/octet-stream",
                    "recovered_from": status,
                },
                priority=50,
            )
    finally:
        await store.close()

    report = {
        "dry_run": args.dry_run,
        "recovered_count": len(recovered),
        "skipped_count": len(skipped),
        "recovered": recovered,
        "skipped": skipped[: args.report_limit],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover retryable Aily sources into source_jobs.")
    parser.add_argument("--db-path", type=Path, default=SETTINGS.source_store_db_path)
    parser.add_argument("--object-dir", type=Path, default=SETTINGS.source_object_dir)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--report-limit", type=int, default=50)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
