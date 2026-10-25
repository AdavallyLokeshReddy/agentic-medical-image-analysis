"""Tests for the read-only governance router (backend/governance_api.py)."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import governance_api  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app)


def test_registry_builds_without_constructing_any_tool():
    """Importing register_tools normally would construct tools and load weights."""
    registry = governance_api._build_metadata_registry()
    names = {t["name"] for t in registry.list_tools()}
    assert "ich_detection" in names
    # The global registry must be untouched by the metadata build.
    from tools.registry import tool_registry

    assert tool_registry is not registry


def test_status_reports_no_http_model_execution(client):
    body = client.get("/governance/status").json()
    assert body["model_runtime"]["execution_exposed_over_http"] is False
    assert "Not for clinical" in body["notice"]
    assert body["tool_registry"]["loaded"] is True


def test_tools_are_metadata_only(client):
    body = client.get("/governance/tools").json()
    assert body["available"] is True
    assert body["mode"] == "metadata_only"
    assert all(t["validation_population"] for t in body["tools"])


def test_plan_requires_existing_case_and_series(client):
    assert client.get("/governance/cases/NO-SUCH-CASE/plan").status_code == 404
    created = client.post("/cases").json()["case_id"]
    assert client.get(f"/governance/cases/{created}/plan").status_code == 409


def test_audit_without_database_is_honest(client, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    body = client.get("/governance/cases/CASE-0001/audit").json()
    assert body == {
        "available": False,
        "reason": "No database configured (DATABASE_URL is not set).",
        "events": [],
    }


def test_case_list_shape(client):
    client.post("/cases")
    body = client.get("/cases").json()
    assert body["count"] == len(body["cases"]) >= 1
    assert {"case_id", "status", "series_count", "file_count", "updated_at"} <= set(body["cases"][0])


def test_cors_allows_configured_origin(client):
    r = client.options(
        "/cases",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
