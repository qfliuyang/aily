import asyncio
import logging
from typing import Callable, Awaitable

from aily.queue.db import QueueDB

logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(
        self,
        db: QueueDB,
        processor: Callable[[dict], Awaitable[None]],
        poll_interval: float = 2.0,
    ) -> None:
        self.db = db
        self.processor = processor
        self.poll_interval = poll_interval
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            job = await self.db.dequeue()
            if job is None:
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.poll_interval
                    )
                except asyncio.TimeoutError:
                    continue
                return
            try:
                await self.processor(job)
                await self.db.complete_job(job["id"], success=True)
            except Exception as exc:
                logger.exception("Job %s failed", job["id"])
                will_retry = await self.db.retry_job(job["id"])
                if not will_retry:
                    await self.db.complete_job(job["id"], success=False, error_message=str(exc))
