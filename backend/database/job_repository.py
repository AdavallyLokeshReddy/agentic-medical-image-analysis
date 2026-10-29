"""
Persistence for analysis jobs. Plain dictionaries in, plain dictionaries out: this module knows
nothing about backend/jobs, so the database package keeps no dependency on the job layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Base, JobModel

_COLUMNS = (
    "job_id", "case_id", "body_region", "clinical_question", "status", "tool_name",
    "created_at", "updated_at", "started_at", "finished_at",
    "steps", "timings_seconds", "error", "note", "outcome",
)

_UNSET = object()


def _row_to_dict(row: JobModel) -> dict[str, Any]:
    data = {name: getattr(row, name) for name in _COLUMNS}
    data["result_json"] = row.result_json
    return data


class JobRepository:
    """Each method opens, commits and closes its own session: callers never hold a transaction."""

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def ensure_schema(self) -> None:
        """Create the jobs table if it is missing. Idempotent. Touches no other table."""
        with self._session_factory() as session:
            Base.metadata.create_all(bind=session.get_bind(), tables=[JobModel.__table__])

    def save(self, job: dict[str, Any], result_json: Any = _UNSET) -> None:
        """Insert or update a job. `result_json` is left untouched unless it is passed."""
        values = {name: job[name] for name in _COLUMNS}
        with self._session_factory() as session:
            row = session.get(JobModel, values["job_id"])
            if row is None:
                row = JobModel(**values, result_json=None if result_json is _UNSET else result_json)
                session.add(row)
            else:
                for name, value in values.items():
                    setattr(row, name, value)
                if result_json is not _UNSET:
                    row.result_json = result_json
            session.commit()

    def get(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._session_factory() as session:
            row = session.get(JobModel, job_id)
            return _row_to_dict(row) if row is not None else None

    def list_for_case(self, case_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(JobModel).where(JobModel.case_id == case_id).order_by(JobModel.created_at.desc())
            ).all()
            return [_row_to_dict(r) for r in rows]

    def count_in_statuses(self, statuses: Iterable[str]) -> int:
        with self._session_factory() as session:
            return len(session.scalars(select(JobModel.job_id).where(JobModel.status.in_(list(statuses)))).all())

    def interrupt_working(self, working: Iterable[str], reason: str) -> list[str]:
        """
        Mark every job still in a working status as failed. Called once at startup: the worker thread
        that owned those jobs died with the previous process, so they can never finish.
        """
        working = list(working)
        now = datetime.now(timezone.utc).isoformat()
        interrupted: list[str] = []
        with self._session_factory() as session:
            rows = session.scalars(select(JobModel).where(JobModel.status.in_(working))).all()
            for row in rows:
                previous = row.status
                row.error = {"stage": previous, "type": "RestartInterrupted", "message": reason}
                row.steps = [*row.steps, {"status": "failed", "at": now, "detail": f"interrupted during {previous}: {reason}"}]
                row.status = "failed"
                row.updated_at = now
                row.finished_at = now
                interrupted.append(row.job_id)
            session.commit()
        return interrupted
