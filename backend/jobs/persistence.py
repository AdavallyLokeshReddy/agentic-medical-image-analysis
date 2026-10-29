"""
PostgreSQL-backed job store (Phase 3).

Behind the same interface as the in-memory JobStore:

  * Jobs created by THIS process stay in memory as live records (they carry the governance objects the
    worker and the review lifecycle need) and are written to PostgreSQL at creation, at every
    transition and when finished.
  * Jobs created by an EARLIER process are read from PostgreSQL as `restored` records. Their status,
    steps, timings and stored /result snapshot are readable. Their live review context is gone, so a
    pending review cannot be completed (AnalysisJobService.review refuses, and says why).
  * recover_interrupted() marks jobs a dead process left mid-run as failed. Call it once at startup.

A database error never breaks a running job: it is logged and counted in `persistence_errors`, which
is shown in the runtime status, so a degraded store is visible rather than silent.

No image data is stored here. Research & Engineering Prototype - Not for clinical diagnosis or treatment.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from .models import WORKING, JobRecord
from .service import JobStore

log = logging.getLogger("jobs.persistence")

RESTART_REASON = (
    "The backend restarted while this job was running. The worker was interrupted and the job cannot resume. "
    "Rerun the analysis."
)


class PersistentJobStore(JobStore):
    def __init__(self, session_factory: Callable[[], Session], cap: int = 200, create_schema: bool = True):
        from database.job_repository import JobRepository

        super().__init__(cap=cap)
        self._session_factory = session_factory
        self.repository = JobRepository(session_factory)
        self.persistence_errors = 0
        self._error_lock = threading.Lock()
        if create_schema:
            self.repository.ensure_schema()

    # ---- internal ------------------------------------------------------------------------
    def _safely(self, what: str, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except Exception:  # noqa: BLE001 - a database problem must not kill the worker
            with self._error_lock:
                self.persistence_errors += 1
            log.exception("job persistence failed: %s", what)
            return None

    # ---- JobStore interface ----------------------------------------------------------------
    def add(self, job: JobRecord) -> None:
        super().add(job)
        self._safely("add", lambda: self.repository.save(job.to_row()))

    def get(self, job_id: str) -> Optional[JobRecord]:
        live = super().get(job_id)
        if live is not None:
            return live
        row = self._safely("get", lambda: self.repository.get(job_id))
        return JobRecord.from_row(row) if row else None

    def for_case(self, case_id: str) -> list[JobRecord]:
        live = {j.job_id: j for j in super().for_case(case_id)}
        rows = self._safely("list", lambda: self.repository.list_for_case(case_id)) or []
        merged = dict(live)
        for row in rows:
            merged.setdefault(row["job_id"], JobRecord.from_row(row))
        return list(merged.values())

    def save(self, job: JobRecord, snapshot: Any = None, *, write_snapshot: bool = False) -> None:
        if write_snapshot:
            self._safely("save", lambda: self.repository.save(job.to_row(), snapshot))
        else:
            self._safely("save", lambda: self.repository.save(job.to_row()))

    def snapshot(self, job_id: str) -> Optional[dict[str, Any]]:
        row = self._safely("snapshot", lambda: self.repository.get(job_id))
        return (row or {}).get("result_json")

    def persist_case_state(self, case: Any, *, reviews: bool) -> None:
        from database.case_persistence import CaseStatePersistence

        def write() -> None:
            with self._session_factory() as session:
                bridge = CaseStatePersistence(session)
                bridge.save_case(case)
                bridge.save_evidence(case)
                bridge.save_verification(case)
                if reviews:
                    bridge.save_human_reviews(case)  # called only once the review is completed
                session.commit()

        self._safely("case state", write)

    def recover_interrupted(self) -> list[str]:
        ids = self._safely(
            "recover", lambda: self.repository.interrupt_working([s.value for s in WORKING], RESTART_REASON)
        )
        if ids:
            log.warning("marked %d interrupted job(s) as failed after restart: %s", len(ids), ids)
        return ids or []

    def describe(self) -> dict[str, Any]:
        return {
            "state_storage": "postgresql (durable). Jobs interrupted by a restart are marked failed; "
            "a review pending before a restart cannot be completed after it.",
            "persistence_errors": self.persistence_errors,
        }


def store_from_environment() -> JobStore:
    """PostgreSQL store when DATABASE_URL is set and reachable; otherwise the in-memory store (unchanged behaviour)."""
    import os

    if not os.getenv("DATABASE_URL"):
        return JobStore()
    try:
        from sqlalchemy import text

        from database.connection import SessionLocal, engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        store = PersistentJobStore(SessionLocal)
    except Exception:  # noqa: BLE001
        log.exception("DATABASE_URL is set but PostgreSQL is not usable; job state stays in memory")
        return JobStore()
    store.recover_interrupted()
    return store
