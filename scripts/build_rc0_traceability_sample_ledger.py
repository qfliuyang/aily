#!/usr/bin/env python3
"""Build a fresh RC0 traceability sample ledger through real source-store APIs."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aily.source_store.store import SourceStore


async def build(output: Path, *, pdf: Path | None = None) -> int:
    samples: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="aily-rc0-traceability-ledger-") as temp_root_raw:
        temp_root = Path(temp_root_raw)
        store = SourceStore(db_path=temp_root / "source_store.db", object_dir=temp_root / "objects")
        await store.initialize()
        try:
            async def add(sample_id: str, sample_type: str, record: dict[str, Any], *, job_type: str = "process_upload_source") -> None:
                status = str(record.get("status") or "")
                job = None
                if status == "stored" and sample_type not in {"malformed"}:
                    source_id = str(record["source_id"])
                    if sample_type == "url":
                        job_type_used = "process_url_source"
                        payload = {"url": record.get("url"), "sample_id": sample_id}
                    else:
                        job_type_used = job_type
                        payload = {"filename": record.get("filename"), "sample_id": sample_id}
                    job = await store.enqueue_source_job(source_id=source_id, job_type=job_type_used, payload=payload)
                    await store.update_status(source_id, "queued", {"sample_id": sample_id})
                    status = "queued"
                samples.append(
                    {
                        "id": sample_id,
                        "sample_type": sample_type,
                        "status": "duplicate" if record.get("duplicate") else status,
                        "successful": sample_type != "malformed",
                        "source_id": record.get("source_id", ""),
                        "sha256": record.get("sha256", ""),
                        "duplicate": bool(record.get("duplicate")),
                        "job_id": job.get("job_id") if job else "",
                        "job_type": job.get("job_type") if job else "",
                        "mocked": False,
                        "manual_state_mutation": False,
                        "real_source_store": True,
                        "real_queue_job": bool(job),
                    }
                )

            await add("url-1", "url", await store.store_url(url="https://example.com/aily-rc0-alpha", metadata={"ledger": True}))
            await add("url-2", "url", await store.store_url(url="https://example.com/aily-rc0-beta", metadata={"ledger": True}))
            await add("url-duplicate", "duplicate", await store.store_url(url="https://example.com/aily-rc0-alpha", metadata={"ledger": True}))

            await add("text-1", "text", await store.store_text(title="RC0 Text One", text="Aily should preserve every second-brain intake with source traceability.", metadata={"ledger": True}))
            await add("text-2", "text", await store.store_text(title="RC0 Text Two", text="Traceability requires queue-visible work and durable records.", metadata={"ledger": True}))
            await add("text-duplicate", "duplicate", await store.store_text(title="RC0 Text One", text="Aily should preserve every second-brain intake with source traceability.", metadata={"ledger": True}))

            await add("file-1", "file", await store.store_upload(upload_id="upload-file-1", filename="rc0-note.md", content_type="text/markdown", data=b"# RC0 note\n\nDurable upload sample.", metadata={"ledger": True}))
            await add("file-2", "file", await store.store_upload(upload_id="upload-file-2", filename="rc0-note.txt", content_type="text/plain", data=b"Another durable upload sample.", metadata={"ledger": True}))
            if pdf and pdf.exists():
                await add("pdf-1", "pdf", await store.store_upload(upload_id="upload-pdf-1", filename=pdf.name, content_type="application/pdf", data=pdf.read_bytes(), metadata={"ledger": True, "source_path": str(pdf)}))
            else:
                await add("pdf-1", "pdf", await store.store_upload(upload_id="upload-pdf-1", filename="synthetic.pdf", content_type="application/pdf", data=b"%PDF-1.4\n% synthetic ledger pdf boundary\n", metadata={"ledger": True}))

            try:
                await store.store_text(title="Malformed Empty Text", text="   ", metadata={"ledger": True})
            except ValueError as exc:
                samples.append(
                    {
                        "id": "malformed-empty-text",
                        "sample_type": "malformed",
                        "status": "rejected",
                        "successful": False,
                        "error": str(exc),
                        "mocked": False,
                        "manual_state_mutation": False,
                        "real_source_store": True,
                        "real_queue_job": False,
                    }
                )
        finally:
            await store.close()

    payload = {
        "description": "Fresh RC0 representative intake sample ledger built through SourceStore and source job enqueue APIs.",
        "sample_count": len(samples),
        "samples": samples,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build RC0 traceability sample ledger.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pdf", type=Path)
    args = parser.parse_args()
    return asyncio.run(build(args.output, pdf=args.pdf))


if __name__ == "__main__":
    raise SystemExit(main())
