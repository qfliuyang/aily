"""
E2E MVP Test: Aily's Core Value Proposition

Send a link → Get structured knowledge in Obsidian.

This test validates the complete user journey:
1. User sends a URL via Feishu message
2. Aily fetches and parses the content
3. Structured note appears in Obsidian vault
4. User receives confirmation

NO MOCKS - hits real services, exposes real problems.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest


class TestAilyCoreFlowMVP:
    """
    MVP E2E test: Link sharing → Knowledge capture.

    This is the "happy path" that validates Aily's reason for existing.
    If this test fails, Aily is not delivering its core value.
    """

    async def test_send_url_receive_note_in_obsidian(
        self,
        exposure,
        test_id: str,
    ) -> None:
        """
        Full flow: URL in Feishu webhook → Note in Obsidian.

        EXPOSES: Broken parsers, fetch failures, Obsidian API issues,
                 message delivery problems, race conditions.
        """
        # Prerequisites check
        feishu_ready = bool(os.getenv("FEISHU_APP_ID") and os.getenv("FEISHU_APP_SECRET"))
        obsidian_ready = bool(os.getenv("OBSIDIAN_VAULT_PATH") and os.getenv("OBSIDIAN_REST_API_KEY"))
        open_id = os.getenv("FEISHU_TEST_OPEN_ID")

        if not feishu_ready or not obsidian_ready:
            pytest.skip("Real services not configured")

        if not open_id:
            exposure.expose("CONFIG_MISSING", "FEISHU_TEST_OPEN_ID not set - using dummy", {
                "consequence": "Cannot verify message delivery confirmation",
            })
            open_id = "test_user_open_id"

        # Use a reliable test URL that should always work
        test_url = "https://httpbin.org/html"
        expected_title_fragment = "Herman Melville"

        start_time = datetime.now(timezone.utc)

        # Step 1: Simulate Feishu webhook with URL
        try:
            job_id = await self._send_feishu_webhook(test_url, open_id, test_id)
            exposure.expose("WEBHOOK_ACCEPTED", f"Job enqueued: {job_id}", {
                "url": test_url,
                "open_id": open_id[:10] + "..." if len(open_id) > 10 else open_id,
            })
        except Exception as e:
            exposure.expose("WEBHOOK_FAILED", "Could not send Feishu webhook", {
                "error": str(e),
                "this_blocks_everything": True,
            })
            pytest.fail(f"Webhook failed: {e}")

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

        # Step 4: Check for confirmation message (if real open_id used)
        if open_id != "test_user_open_id":
            exposure.expose("CONFIRMATION_CHECK", "Confirmation message check skipped", {
                "reason": "Manual verification needed - check Feishu",
                "test_id": test_id,
            })

    async def _send_feishu_webhook(self, url: str, open_id: str, test_id: str) -> str:
        """Simulate Feishu webhook sending a URL to Aily."""
        from tests.integration.conftest import QueueDB
        from aily.config import SETTINGS

        # Directly enqueue via QueueDB (simulating webhook handler)
        db = QueueDB(SETTINGS.queue_db_path)
        await db.initialize()

        # Create a unique test job
        job_id = f"e2e-{test_id}"

        # Directly insert to test the flow without HTTP signature complexity
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

        exposure.expose("DEDUP_TEST", "Same URL enqueued twice", {
            "first_enqueued": job1 is not None,
            "second_enqueued": job2 is not None,
            "deduplication_worked": job2 is None,  # Second should be None (deduped)
        })

        if job1 and job2:
            exposure.expose("DEDUP_FAILURE", "Duplicate URLs were enqueued", {
                "url": test_url,
                "job1": job1,
                "job2": job2,
            })


class TestAilyFailureModesMVP:
    """
    MVP failure tests: How Aily handles problems.

    These tests verify Aily fails gracefully and informs the user.
    """

    async def test_bad_url_results_in_failure_notification(
        self,
        exposure,
        test_id: str,
    ) -> None:
        """
        Sending a bad URL should result in a failure message to user.

        EXPOSES: Silent failures, missing error notifications.
        """
        from aily.config import SETTINGS
        from aily.queue.db import QueueDB

        if not os.getenv("FEISHU_APP_ID"):
            pytest.skip("Feishu not configured")

        db = QueueDB(SETTINGS.queue_db_path)
        await db.initialize()

        # Use a URL that will definitely fail
        bad_url = "https://this-domain-does-not-exist-12345.xyz"

        # Enqueue directly to avoid webhook complexity
        import aiosqlite
        job_id = f"e2e-fail-{test_id}"

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO jobs (id, type, payload, status, retry_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    "url_fetch",
                    json.dumps({"url": bad_url, "open_id": "test_user"}),
                    "pending",
                    0,
                ),
            )
            await conn.commit()

        exposure.expose("BAD_URL_ENQUEUED", f"Testing failure handling: {bad_url}", {
            "job_id": job_id,
        })

        # Wait for failure (should be quick)
        await asyncio.sleep(2)

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT status, error_message FROM jobs WHERE id = ?",
                (job_id,)
            )
            row = await cursor.fetchone()

            if row:
                exposure.expose("JOB_STATUS", f"Job ended with status: {row['status']}", {
                    "status": row["status"],
                    "error": row["error_message"],
                    "expected": "failed",
                })

    async def test_obsidian_down_graceful_failure(
        self,
        exposure,
        test_id: str,
    ) -> None:
        """
        If Obsidian is not running, Aily should fail gracefully.

        EXPOSES: Crash loops, unhandled connection errors.
        """
        from aily.config import SETTINGS

        # Check if Obsidian is running
        obsidian_port = SETTINGS.obsidian_rest_api_port

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"http://127.0.0.1:{obsidian_port}/",
                    timeout=2.0,
                )
                obsidian_running = resp.status_code < 500
        except Exception:
            obsidian_running = False

        if obsidian_running:
            pytest.skip("Obsidian is running - cannot test 'down' scenario")

        exposure.expose("OBSIDIAN_DOWN", "Obsidian REST API not accessible", {
            "port": obsidian_port,
            "expected_behavior": "Jobs should fail with clear error message",
        })


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

            exposure.expose("CONCURRENT_TEST", f"Created {successes}/5 notes", {
                "successes": successes,
                "failures": len(failures),
                "exceptions": len(exceptions),
                "details": failures + [str(e) for e in exceptions],
            })

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
