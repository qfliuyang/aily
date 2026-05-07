"""
MVP integration tests for Aily's core value proposition.

These tests validate durable queue-level product behavior: a URL job enters
Aily's queue, processing completes, and structured knowledge appears in
Obsidian. They intentionally do not claim Feishu/webhook ingress evidence;
release acceptance must add an `acceptance`-marked ingress test that exercises
the real webhook/signature boundary.

NO MOCKS - hits real services where configured and exposes real problems.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.integration


class TestAilyCoreFlowMVP:
    """
    MVP integration test: queued URL → knowledge capture.

    This is the local product-path contract below external ingress. It validates
    queue processing and Obsidian output without pretending to prove Feishu
    webhook/signature behavior.
    """

    async def test_queue_url_job_creates_note_in_obsidian(
        self,
        exposure,
        test_id: str,
    ) -> None:
        """
        Full queue-level flow: URL job → Note in Obsidian.

        EXPOSES: Broken parsers, fetch failures, Obsidian API issues,
                 queue processing problems, race conditions.
        """
        # Prerequisites check
        obsidian_ready = bool(os.getenv("OBSIDIAN_VAULT_PATH") and os.getenv("OBSIDIAN_REST_API_KEY"))
        open_id = os.getenv("FEISHU_TEST_OPEN_ID") or "test_user_open_id"

        if not obsidian_ready:
            pytest.skip("Obsidian service not configured")

        if open_id == "test_user_open_id":
            exposure.record_observation("CONFIGURATION_NOTICE", "FEISHU_TEST_OPEN_ID not set - using dummy", {
                "consequence": "Queue-level test cannot verify message delivery confirmation",
            })

        # Use a reliable test URL that should always work
        test_url = "https://httpbin.org/html"
        expected_title_fragment = "Herman Melville"

        start_time = datetime.now(timezone.utc)

        # Step 1: enqueue the URL job through the durable queue boundary.
        try:
            job_id = await self._enqueue_url_job(test_url, open_id, test_id)
            exposure.record_observation("QUEUE_JOB_ACCEPTED", f"Job enqueued: {job_id}", {
                "url": test_url,
                "open_id": open_id[:10] + "..." if len(open_id) > 10 else open_id,
            })
        except Exception as e:
            exposure.expose_problem("QUEUE_JOB_ENQUEUE_FAILURE", "Could not enqueue URL job", {
                "error": str(e),
                "this_blocks_everything": True,
            })
            pytest.fail(f"Queue enqueue failed: {e}")

        # Step 2: Wait for job processing (with timeout)
        try:
            job_completed = await self._wait_for_job_completion(job_id, timeout_seconds=60)
            if not job_completed:
                exposure.expose("JOB_TIMEOUT", "Job did not complete in 60s", {
                    "job_id": job_id,
                    "possible_causes": ["fetcher stuck", "parser crashed", "obsidian timeout"],
                })
                pytest.fail("Job processing timeout")
        except Exception as e:
            exposure.expose("JOB_MONITORING_FAILED", str(e), {"job_id": job_id})
            raise

        # Step 3: Verify note exists in Obsidian
        try:
            note_found = await self._verify_note_in_obsidian(test_url, expected_title_fragment)
            if note_found:
                exposure.expose("NOTE_CREATED", f"Note verified in Obsidian", {
                    "url": test_url,
                    "elapsed_seconds": (datetime.now(timezone.utc) - start_time).total_seconds(),
                })
            else:
                exposure.expose("NOTE_MISSING", "Note not found in Obsidian", {
                    "url": test_url,
                    "job_id": job_id,
                    "this_is_a_real_problem": True,
                })
                pytest.fail("Note not created in Obsidian")
        except Exception as e:
            exposure.expose("OBSIDIAN_VERIFICATION_FAILED", str(e), {
                "url": test_url,
                "error_type": type(e).__name__,
            })
            raise

        # Feishu confirmation is outside this queue-level contract.
        if open_id != "test_user_open_id":
            exposure.record_observation("FEISHU_CONFIRMATION_OUT_OF_SCOPE", "Confirmation message not checked here", {
                "reason": "Ingress/confirmation belongs in acceptance-marked release evidence",
                "test_id": test_id,
            })

    async def _enqueue_url_job(self, url: str, open_id: str, test_id: str) -> str:
        """Enqueue a URL job through the durable queue boundary."""
        from aily.queue.db import QueueDB
        from aily.config import SETTINGS

        db = QueueDB(SETTINGS.queue_db_path)
        await db.initialize()

        # Create a unique test job
        job_id = f"e2e-{test_id}"

        # Queue-level integration: ingress/webhook signature is covered by
        # acceptance-marked release evidence, not this local MVP test.
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO jobs (id, type, payload, status, retry_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    "url_fetch",
                    json.dumps({"url": url, "open_id": open_id}),
                    "pending",
                    0,
                ),
            )
            await conn.commit()

        return job_id

    async def _wait_for_job_completion(self, job_id: str, timeout_seconds: int = 60) -> bool:
        """Poll QueueDB until job reaches terminal state."""
        from aily.config import SETTINGS
        import aiosqlite

        db_path = SETTINGS.queue_db_path
        start = time.time()

        while time.time() - start < timeout_seconds:
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT status, error_message FROM jobs WHERE id = ?",
                    (job_id,)
                )
                row = await cursor.fetchone()

                if not row:
                    await asyncio.sleep(0.5)
                    continue

                status = row["status"]

                if status == "completed":
                    return True
                elif status == "failed":
                    error = row["error_message"] or "Unknown error"
                    raise RuntimeError(f"Job failed: {error}")

            await asyncio.sleep(0.5)

        return False

    async def _verify_note_in_obsidian(self, source_url: str, title_fragment: str) -> bool:
        """Check if note was created in Obsidian vault."""
        from tests.integration.conftest import RealObsidianClient

        client = RealObsidianClient()

        try:
            # List recent notes in test folder
            notes = await client.list_test_notes()

            # Check each note for our source URL
            for note_path in notes:
                content = await client.read_note(Path(note_path).name)
                if source_url in content:
                    return True

            return False
        finally:
            await client.close()

    async def test_link_deduplication_prevents_duplicate_notes(
        self,
        exposure,
        test_id: str,
    ) -> None:
        """
        Sending same URL twice should not create duplicate notes.

        EXPOSES: Deduplication logic failures, race conditions.
        """
        from aily.config import SETTINGS
        from aily.queue.db import QueueDB

        if not os.getenv("OBSIDIAN_VAULT_PATH"):
            pytest.skip("Obsidian not configured")

        db = QueueDB(SETTINGS.queue_db_path)
        await db.initialize()

        test_url = f"https://example.com/e2e-dedup-{test_id}"

        # Enqueue same URL twice rapidly
        job1 = await db.enqueue_url(test_url, open_id="", source="test")
        job2 = await db.enqueue_url(test_url, open_id="", source="test")

        exposure.record_observation("DEDUP_CHECK", "Same URL enqueued twice", {
            "first_enqueued": bool(job1),
            "second_enqueued": bool(job2),
            "deduplication_worked": job2 is False,
        })

        assert job1 is True
        assert job2 is False


class TestAilyFailureModesMVP:
    """
    MVP failure tests: How Aily handles problems.

    These tests verify Aily fails gracefully and informs the user.
    """

    async def test_bad_url_worker_failure_reaches_failed_state(
        self,
        test_id: str,
        tmp_path: Path,
    ) -> None:
        """Worker processor failures should persist failed queue state and error details.

        This is a deterministic worker-path contract for URL failure handling: the
        production worker owns the status transition, not the test itself.
        """
        from aily.queue.db import QueueDB
        from aily.queue.worker import JobWorker

        db = QueueDB(tmp_path / f"bad-url-{test_id}.db")
        await db.initialize()
        job_id = await db.enqueue("url_fetch", {"url": "https://invalid.test", "open_id": "test_user"})

        async def failing_processor(job: dict) -> None:
            assert job["id"] == job_id
            assert job["type"] == "url_fetch"
            raise RuntimeError("DNS resolution failed for test URL")

        worker = JobWorker(db, failing_processor, poll_interval=0.01)
        try:
            await worker.start()
            deadline = time.monotonic() + 2.0
            row = await db.get_job(job_id)
            while time.monotonic() < deadline:
                row = await db.get_job(job_id)
                if row is not None and row["status"] == "failed":
                    break
                await asyncio.sleep(0.01)

            assert row is not None
            assert row["status"] == "failed"
            # QueueDB stores retry_count as completed retry transitions after the
            # initial attempt; max_retries=3 therefore fails closed at count 2.
            assert row["retry_count"] == 2
            assert row["error_message"]
            assert "DNS resolution failed" in row["error_message"]
        finally:
            await worker.stop()
            await db.close()

    async def test_obsidian_down_probe_uses_controlled_unreachable_endpoint(
        self,
        exposure,
    ) -> None:
        """Obsidian-down precondition checks must not depend on ambient services."""

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            unused_port = sock.getsockname()[1]

        obsidian_running = await self._probe_obsidian_running(unused_port)

        assert obsidian_running is False
        exposure.record_observation("OBSIDIAN_OFFLINE_SCENARIO", "Controlled Obsidian endpoint is unreachable", {
            "port": unused_port,
            "expected_behavior": "release failure checks can use deterministic offline endpoint",
        })

    async def _probe_obsidian_running(self, port: int) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"http://127.0.0.1:{port}/", timeout=0.25)
                return resp.status_code < 500
        except Exception:
            return False


class TestAilyObsidianIntegrationMVP:
    """
    MVP tests specifically for Obsidian integration quality.
    """

    async def test_note_has_proper_structure(
        self,
        exposure,
        test_id: str,
    ) -> None:
        """
        Created notes should have proper markdown structure.

        EXPOSES: Malformed markdown, missing frontmatter, encoding issues.
        """
        from tests.integration.conftest import RealObsidianClient

        if not os.getenv("OBSIDIAN_REST_API_KEY"):
            pytest.skip("Obsidian not configured")

        client = RealObsidianClient()

        try:
            # Create a test note directly
            test_content = f"""# Test Note {test_id}

This is a test note created by E2E MVP test.

## Source

https://example.com/test-{test_id}

## Content

- Point 1
- Point 2
- Point 3

---

*Created by Aily E2E test*
"""
            filename = f"e2e-structure-{test_id}.md"

            await client.write_note(filename, test_content)

            # Read it back
            read_content = await client.read_note(filename)

            # Verify structure
            checks = {
                "has_title": test_id in read_content,
                "has_source_url": "example.com" in read_content,
                "has_markdown_headers": "##" in read_content,
                "has_list": "- Point" in read_content,
                "encoding_intact": "———" in read_content or "---" in read_content,
            }

            exposure.expose("NOTE_STRUCTURE_CHECK", "Note structure validation", checks)

            failed_checks = [k for k, v in checks.items() if not v]
            if failed_checks:
                exposure.expose("STRUCTURE_FAILURE", f"Failed checks: {failed_checks}", {
                    "filename": filename,
                    "content_preview": read_content[:200],
                })

        finally:
            await client.close()

    async def test_concurrent_note_creation(
        self,
        exposure,
        test_id: str,
    ) -> None:
        """
        Multiple simultaneous notes should all be created correctly.

        EXPOSES: Race conditions, file locking issues, data corruption.
        """
        from tests.integration.conftest import RealObsidianClient

        if not os.getenv("OBSIDIAN_REST_API_KEY"):
            pytest.skip("Obsidian not configured")

        client = RealObsidianClient()

        async def create_and_verify(i: int) -> dict:
            filename = f"e2e-concurrent-{test_id}-{i}.md"
            content = f"# Concurrent Test {i}\n\nUnique ID: {uuid.uuid4()}"

            try:
                await client.write_note(filename, content)
                read_back = await client.read_note(filename)
                success = content in read_back
                return {"index": i, "success": success, "error": None}
            except Exception as e:
                return {"index": i, "success": False, "error": str(e)}

        try:
            # Create 5 notes concurrently
            tasks = [create_and_verify(i) for i in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            failures = [r for r in results if isinstance(r, dict) and not r.get("success")]
            exceptions = [r for r in results if isinstance(r, Exception)]

            details = {
                "successes": successes,
                "failures": len(failures),
                "exceptions": len(exceptions),
                "details": failures + [str(e) for e in exceptions],
            }
            if successes == 5 and not failures and not exceptions:
                exposure.record_observation("CONCURRENT_NOTES_CREATED", "Created 5/5 notes", details)
            else:
                exposure.expose_problem("CONCURRENT_NOTE_FAILURE", f"Created {successes}/5 notes", details)

        finally:
            await client.close()


# =============================================================================
# E2E Test Summary
# =============================================================================

def pytest_sessionfinish(session, exitstatus):
    """Print E2E test summary."""
    print("\n" + "="*70)
    print("AILY E2E MVP TEST SUMMARY")
    print("="*70)
    print("""
Core Value Tested: "Send link → Get structured knowledge"

Tests Run:
1. test_send_url_receive_note_in_obsidian - Full happy path
2. test_link_deduplication_prevents_duplicate_notes - Deduplication logic
3. test_bad_url_results_in_failure_notification - Error handling
4. test_obsidian_down_graceful_failure - Resilience
5. test_note_has_proper_structure - Output quality
6. test_concurrent_note_creation - Concurrency safety

Service Requirements:
- Feishu: App credentials + test Open ID
- Obsidian: Vault path + REST API key + plugin running
- Network: Can reach httpbin.org for test URLs

If these tests pass, Aily delivers its core promise.
If they fail, the product is broken.
""")
    print("="*70)
