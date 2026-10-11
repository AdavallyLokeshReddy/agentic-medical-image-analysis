"""
Test configuration.

A fresh clone has no model weights, no patient/test imaging data and may have no PostgreSQL server.
Tests that need those are SKIPPED with a clear reason instead of crashing, so the result of
`pytest` on a clean machine is honest: what can run, runs; the rest says what it is missing.
"""

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"



@pytest.fixture(autouse=True, scope="session")
def _run_from_backend_dir():
    """The tools and tests resolve model bundles and uploads relative to the backend/ folder."""
    previous = os.getcwd()
    os.chdir(BACKEND)
    yield
    os.chdir(previous)

HAS_SKP = importlib.util.find_spec("skp") is not None

# Modules that import the optional external `skp` package at import time.
NEEDS_SKP = {
    "backend/tests/test_ct3_governed_integration.py",
    "backend/tests/test_evidence_objects.py",
    "backend/tests/test_verification_integration.py",
    "tests/test_verification_integration.py",
}

# Modules that need a running PostgreSQL server.
NEEDS_DB = {
    "test_audit.py",
    "test_case_audit.py",
    "test_case_persistence.py",
    "test_case_state_workflow_persistence.py",
    "test_repository.py",
}

WHOLE_BODY_WEIGHTS = (
    BACKEND / "models/monai/wholeBody_ct_segmentation/wholeBody_ct_segmentation/models/model.pt"
)
LUNG_WEIGHTS = BACKEND / "models/monai/lung_nodule_ct_detection/models/model.pt"
LUNG_CASE = BACKEND / "uploads/CASE-LUNG-0001/series"

# module -> (path that must exist, reason shown when it does not)
NEEDS_FILES = {
    "test_ct5_model_loading.py": (WHOLE_BODY_WEIGHTS, "CT-5 model weights (model.pt) not in repository"),
    "test_ct5_synthetic_inference.py": (WHOLE_BODY_WEIGHTS, "CT-5 model weights (model.pt) not in repository"),
    "test_lung_nodule_detection.py": (LUNG_WEIGHTS, "lung nodule model weights (model.pt) not in repository"),
    "test_ct2_governed_integration.py": (LUNG_CASE, "chest CT test series uploads/CASE-LUNG-0001 not in repository"),
}


def _db_available() -> bool:
    try:
        from sqlalchemy import text

        from database.connection import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True, scope="session")
def _reset_test_database():
    """
    The database tests use fixed IDs and do not clean up after themselves, so a second run against the
    same database would fail. For a database whose name ends in "_test" (or when ALLOW_TEST_DB_RESET=1),
    drop and recreate all tables once per session. Any other database is never touched.
    """
    if not _db_available():
        yield
        return
    from database.connection import engine
    from database.models import Base

    name = engine.url.database or ""
    if name.endswith("_test") or os.getenv("ALLOW_TEST_DB_RESET") == "1":
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    yield


def pytest_ignore_collect(collection_path, config):
    # Modules that cannot even be imported without `skp` are skipped at collection time.
    if HAS_SKP:
        return False
    try:
        rel = Path(collection_path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return False
    return rel in NEEDS_SKP


def pytest_report_header(config):
    lines = []
    if not HAS_SKP:
        lines.append(
            "skp (head CT hemorrhage model code) not installed: skipping "
            + ", ".join(sorted(NEEDS_SKP))
        )
    return lines


def pytest_collection_modifyitems(config, items):
    db_ok = None
    for item in items:
        name = Path(str(item.fspath)).name
        if name in NEEDS_DB:
            if db_ok is None:
                db_ok = _db_available()
            if not db_ok:
                item.add_marker(pytest.mark.skip(reason="PostgreSQL not reachable (set DATABASE_URL)"))
        if name in NEEDS_FILES:
            path, reason = NEEDS_FILES[name]
            if not path.exists():
                item.add_marker(pytest.mark.skip(reason=reason))
