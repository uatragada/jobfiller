from __future__ import annotations

import asyncio

from sqlalchemy import select

from ..database import SessionLocal
from ..models import Run, utcnow
from .ingestion import DEFAULT_SCAN_LIMIT, run_scan
from .processor import process_newest_queue


class Worker:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self.interval_seconds = 3 * 60 * 60

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    @property
    def is_running(self) -> bool:
        return bool(self._task and not self._task.done())

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            with SessionLocal() as db:
                run = Run(kind="scheduled_scan", status="RUNNING", message="Scheduled newest-first scan started.")
                db.add(run)
                db.commit()
                scan_limit = DEFAULT_SCAN_LIMIT
                try:
                    imported, message = run_scan(db, run, remote_first=True, limit=scan_limit, source="all")
                    run.message = message
                    process_newest_queue(db, limit=scan_limit, remote_first=True)
                    run.status = "SUCCEEDED"
                    run.finished_at = utcnow()
                except Exception as exc:
                    run.status = "FAILED"
                    run.finished_at = utcnow()
                    run.message = f"{run.message} Failed: {exc}"
                finally:
                    db.commit()


worker = Worker()
