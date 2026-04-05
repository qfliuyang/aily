from __future__ import annotations

import asyncio
import logging
import random
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

BASE_INTERVAL = 300
MAX_INTERVAL = 1800
JITTER_MAX = 60
ALERT_THRESHOLD_HOURS = 24


class PassiveCaptureScheduler:
    def __init__(
        self,
        enqueue_fn: Callable[[str], asyncio.Awaitable[None]],
    ) -> None:
        self.enqueue_fn = enqueue_fn
        self.scheduler = AsyncIOScheduler()
        self._consecutive_failures = 0
        self._first_failure_at: datetime | None = None
        self._current_interval = BASE_INTERVAL

    def start(self) -> None:
        self.scheduler.start()
        self.scheduler.add_job(
            self._passive_capture_job,
            trigger=IntervalTrigger(seconds=self._current_interval + random.randint(0, JITTER_MAX)),
            id="passive_capture",
            replace_existing=True,
        )
        logger.info("Passive capture scheduler started")

    def stop(self) -> None:
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:
            pass
        logger.info("Passive capture scheduler stopped")

    async def _passive_capture_job(self) -> None:
        interval = self._current_interval + random.randint(0, JITTER_MAX)
        try:
            urls = await self._detect_urls()
            if urls:
                for url in urls:
                    await self.enqueue_fn(url)
            self._on_success()
        except (OSError, asyncio.TimeoutError) as exc:
            logger.exception("Passive capture failed")
            self._on_failure()
            if self._should_alert():
                self._send_alert()
                logger.error("Passive capture failed for >24h; stopping scheduler")
                self.stop()
                return

        # Reschedule with updated interval
        try:
            self.scheduler.reschedule_job(
                "passive_capture",
                trigger=IntervalTrigger(seconds=interval),
            )
        except Exception:
            logger.exception("Failed to reschedule passive capture")

    async def _detect_urls(self) -> list[str]:
        logger.info("Passive capture: would scan Monica/Kimi for new URLs")
        # Placeholder until DOM selectors are discovered
        return []

    def _on_success(self) -> None:
        if self._consecutive_failures > 0:
            logger.info("Passive capture recovered; resetting backoff")
        self._consecutive_failures = 0
        self._first_failure_at = None
        self._current_interval = BASE_INTERVAL

    def _on_failure(self) -> None:
        self._consecutive_failures += 1
        if self._first_failure_at is None:
            self._first_failure_at = datetime.now(timezone.utc)
        self._current_interval = min(
            BASE_INTERVAL * (2 ** self._consecutive_failures),
            MAX_INTERVAL,
        )
        logger.warning(
            "Passive capture failure #%s; backing off to %ss",
            self._consecutive_failures,
            self._current_interval,
        )

    def _should_alert(self) -> bool:
        if self._first_failure_at is None:
            return False
        elapsed = datetime.now(timezone.utc) - self._first_failure_at
        return elapsed >= timedelta(hours=ALERT_THRESHOLD_HOURS)

    @staticmethod
    def _send_alert() -> None:
        try:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    'display notification "Passive capture has been failing for >24h. Falling back to manual URL sharing." with title "Aily Alert"',
                ],
                check=False,
            )
        except Exception:
            logger.exception("Failed to send macOS alert")
