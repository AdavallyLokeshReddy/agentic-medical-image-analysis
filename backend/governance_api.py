"""
Small, READ-ONLY HTTP surface over the existing governance libraries.

Design rules
------------
* Nothing here executes a medical AI model. The orchestrator's ``plan()`` is
  explicitly a planning step (``execution_started`` is always False).
* Nothing here writes to the database or to the case registry.
* Nothing is fabricated. If a capability cannot run in the current environment
  (missing PyTorch/MONAI, missing ``skp``, no PostgreSQL), the response says so
  and says why, instead of returning placeholder data.
* Evidence, verification results, human-review decisions and structured reports
  are produced by model execution, which is NOT exposed over HTTP. They are
  therefore deliberately absent from this router.

The router is built with a small factory so it can reuse the case helpers that
live in ``main.py`` without a circular import.
"""

from __future__ import annotations

import importlib.util
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import pydicom
from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder

RESEARCH_NOTICE = (
    "Research and engineering prototype. Not clinically validated. "
    "Not for clinical diagnosis or treatment."
)

MODEL_REPO = "ianpan/ct-head-hemorrhage-detection"  # mirrors model_runtime.inference.MODEL_REPO

# Library modules in the repository and whether this router exposes them.
# `http_exposed` is a statement about THIS router, kept next to the code that
# implements it so the two cannot silently drift apart.
LIBRARY_MODULES: list[dict[str, Any]] = [
    {"module": "agent.case_state", "label": "Case state", "http_exposed": "partial"},
    {"module": "agent.orchestrator", "label": "Governed orchestrator", "http_exposed": "plan_only"},
    {"module": "agent.safety_contract", "label": "Safety contract", "http_exposed": "plan_only"},
    {"module": "agent.task_graph", "label": "Task graph", "http_exposed": "plan_only"},
    {"module": "tools.registry", "label": "Tool registry", "http_exposed": "yes"},
    {"module": "verification.verifier", "label": "Evidence verification", "http_exposed": "no"},
    {"module": "agent.human_review", "label": "Human review", "http_exposed": "no"},
    {"module": "agent.review_lifecycle", "label": "Review lifecycle", "http_exposed": "no"},
    {"module": "agent.communication", "label": "Triage and communication", "http_exposed": "no"},
    {"module": "reporting.structured_report", "label": "Structured report", "http_exposed": "no"},
    {"module": "database.audit", "label": "Audit service", "http_exposed": "if_database"},
]


@dataclass
class ApiContext:
    """Helpers owned by main.py that the router needs."""

    cases: dict
    upload_dir: Path
    validate_case_id: Callable[[str], None]
    select_series: Callable[..., tuple[str, Path]]
    get_dicom_files: Callable[[Path], list[Path]]


def _module_importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _describe_error(exc: BaseException) -> str:
    """Short, credential-free description of an exception."""
    return f"{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else 'no detail'}"


# --------------------------------------------------------------------------
# Tool registry — METADATA ONLY
#
# The repository's `register_default_tools()` constructs every tool, and the
# constructors LOAD MODELS (the ICH tool downloads weights from Hugging Face
# and loads them). That must never happen as a side effect of a read-only HTTP
# request. So this router runs the real registration function against an
# ISOLATED registry, with each tool class replaced by a stand-in that carries
# only the class's declared name/description. The ToolMetadata is the real,
# inline metadata from register_tools.py; no model is loaded; the global
# `tool_registry` is never touched; nothing here can execute a tool.
#
# Importing the tool modules needs PyTorch and MONAI. If they are missing the
# registry reports itself unavailable, with the reason.
# --------------------------------------------------------------------------

_registry_lock = threading.Lock()
_registry_state: dict[str, Any] = {"attempted": False, "registry": None, "error": None}



# --------------------------------------------------------------------------
# Heavy third-party imports (torch, monai, skp, ...) are needed only to LOAD
# models, never to describe them. Tool modules import them at module level, so
# on a light host (or one without the external `skp` code) merely importing
# the tool classes would fail. While building the METADATA-ONLY registry, any
# of these that are genuinely not installed are replaced by inert stand-ins.
# Real installed packages always win (the finder is last on sys.meta_path),
# the stand-ins are removed afterwards, and nothing can run a model either way.
# --------------------------------------------------------------------------

import contextlib
import importlib.abc
import importlib.machinery
import sys
import types

_STUBBABLE_ROOTS = {
    "skp", "torch", "monai", "cv2", "safetensors", "huggingface_hub",
    "nibabel", "scipy", "skimage", "SimpleITK", "timm", "einops", "PIL",
}


class _InertMeta(type):
    """Metaclass so attribute access / calls / `|` on an inert class stay inert."""

    def __getattr__(cls, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _make_inert(name)

    def __call__(cls, *args, **kwargs):
        return _make_inert(cls.__name__)

    def __or__(cls, other):
        return cls

    __ror__ = __or__

    def __getitem__(cls, item):
        return cls


def _make_inert(name: str):
    return _InertMeta(name, (), {})


class _InertModule(types.ModuleType):
    __path__: list = []

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _make_inert(name)


class _InertFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self):
        self.used: set[str] = set()

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in _STUBBABLE_ROOTS:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        self.used.add(spec.name)
        return _InertModule(spec.name)

    def exec_module(self, module):
        return None


@contextlib.contextmanager
def _inert_missing_imports():
    """Provide inert stand-ins for heavy packages that are not installed."""
    finder = _InertFinder()
    before = set(sys.modules)
    sys.meta_path.append(finder)  # last: real packages are always preferred
    try:
        yield finder
    finally:
        sys.meta_path.remove(finder)
        if finder.used:
            # Drop everything imported against stand-ins so a later real import is clean.
            # `tools`, `tools.base` and `tools.registry` import nothing heavy and
            # must stay: the orchestrator checks isinstance() against them.
            keep = {"tools", "tools.base", "tools.registry"}
            for name in set(sys.modules) - before:
                if name in keep:
                    continue
                if name in finder.used or name.split(".")[0] in ("tools", "model_runtime"):
                    sys.modules.pop(name, None)


def _build_metadata_registry():
    with _inert_missing_imports():
        return _build_metadata_registry_inner()


def _build_metadata_registry_inner():
    import ast
    import inspect

    import tools as tools_pkg
    from tools.base import MedicalAITool
    from tools.registry import ToolRegistry

    # `tools/register_tools.py` calls register_default_tools() at IMPORT time,
    # which constructs every tool and loads/downloads model weights. Importing
    # it is therefore never safe here. Instead, compile the same file with only
    # that trailing import-time call removed, so its real definitions and inline
    # ToolMetadata are used but nothing is constructed or executed.
    source_path = Path(tools_pkg.__file__).with_name("register_tools.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
    tree.body = [
        node
        for node in tree.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", None) == "register_default_tools"
        )
    ]
    namespace: dict[str, Any] = {
        "__name__": "tools._register_tools_metadata_only",
        "__package__": "tools",
        "__file__": str(source_path),
    }
    exec(compile(tree, str(source_path), "exec"), namespace)  # noqa: S102 - repository file, call removed

    def inert_subclass(real_cls: type[MedicalAITool]) -> type[MedicalAITool]:
        # Same class-level name/description/MODEL_VERSION; constructor loads nothing.
        return type(real_cls.__name__, (real_cls,), {"__init__": lambda self, *a, **k: None})

    isolated = ToolRegistry()
    namespace["tool_registry"] = isolated  # the global registry is never touched
    for attr, obj in list(namespace.items()):
        if inspect.isclass(obj) and issubclass(obj, MedicalAITool) and obj is not MedicalAITool:
            namespace[attr] = inert_subclass(obj)
    namespace["register_default_tools"]()
    return isolated


def _get_registry():
    """Return (registry | None, error | None). Built once, metadata only."""
    with _registry_lock:
        if not _registry_state["attempted"]:
            _registry_state["attempted"] = True
            try:
                _registry_state["registry"] = _build_metadata_registry()
            except Exception as exc:  # noqa: BLE001 - report any import/registration failure honestly
                _registry_state["error"] = _describe_error(exc)
        return _registry_state["registry"], _registry_state["error"]


def _database_probe() -> dict[str, Any]:
    """
    Check PostgreSQL reachability without touching application data.

    Only attempted when DATABASE_URL is explicitly set. Uses a throwaway engine
    with a short connect timeout so a missing database cannot stall the API.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        return {"configured": False, "reachable": None, "error": None}
    try:
        from sqlalchemy import create_engine, text

        probe = create_engine(url, pool_pre_ping=False, connect_args={"connect_timeout": 2})
        try:
            with probe.connect() as conn:
                conn.execute(text("SELECT 1"))
        finally:
            probe.dispose()
        return {"configured": True, "reachable": True, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"configured": True, "reachable": False, "error": type(exc).__name__}


def build_routers(ctx: ApiContext) -> list[APIRouter]:
    cases_router = APIRouter(tags=["cases"])
    governance = APIRouter(prefix="/governance", tags=["governance (read-only)"])

    # ----------------------------------------------------------------------
    # GET /cases  - list known cases (filesystem + in-memory registry)
    # ----------------------------------------------------------------------
    @cases_router.get("/cases")
    def list_cases():
        items = []
        for case_dir in ctx.upload_dir.iterdir():
            if not case_dir.is_dir() or not re.fullmatch(r"[A-Za-z0-9_-]+", case_dir.name):
                continue
            if case_dir.name.startswith("_"):
                continue

            series_root = case_dir / "series"
            series_count = 0
            file_count = 0
            if series_root.is_dir():
                for series_dir in series_root.iterdir():
                    if series_dir.is_dir():
                        files = ctx.get_dicom_files(series_dir)
                        if files:
                            series_count += 1
                            file_count += len(files)

            record = ctx.cases.get(case_dir.name, {})
            items.append(
                {
                    "case_id": case_dir.name,
                    "status": record.get("status", "existing"),
                    "series_count": series_count,
                    "file_count": file_count,
                    # Filesystem modification time: the only timestamp the case registry has.
                    "updated_at": datetime.fromtimestamp(
                        case_dir.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "in_memory_registry": case_dir.name in ctx.cases,
                }
            )

        items.sort(key=lambda item: item["updated_at"], reverse=True)
        return {"count": len(items), "cases": items}

    # ----------------------------------------------------------------------
    # GET /governance/status
    # ----------------------------------------------------------------------
    @governance.get("/status")
    def governance_status():
        registry, registry_error = _get_registry()
        skp_installed = _module_importable("skp")

        return {
            "notice": RESEARCH_NOTICE,
            "tool_registry": {
                "mode": "metadata_only",
                "loaded": registry is not None,
                "tool_count": len(registry.list_tools()) if registry is not None else 0,
                "error": registry_error,
            },
            "model_runtime": {
                "skp_installed": skp_installed,
                "model_repo": MODEL_REPO,
                "weights_source": "Hugging Face Hub, downloaded on first model use",
                "torch_installed": _module_importable("torch"),
                "monai_installed": _module_importable("monai"),
                # Independent of installed dependencies: no route runs a model.
                "execution_exposed_over_http": False,
            },
            "persistence": _database_probe(),
            "library_modules": [
                {**module, "importable": _module_importable(module["module"])}
                for module in LIBRARY_MODULES
            ],
        }

    # ----------------------------------------------------------------------
    # GET /governance/tools
    # ----------------------------------------------------------------------
    @governance.get("/tools")
    def governance_tools():
        registry, registry_error = _get_registry()
        if registry is None:
            return {
                "available": False,
                "reason": registry_error or "Tool registry could not be loaded.",
                "tools": [],
            }
        return {
            "available": True,
            "reason": None,
            "mode": "metadata_only",
            "tools": jsonable_encoder(registry.list_tools()),
        }

    # ----------------------------------------------------------------------
    # GET /governance/cases/{case_id}/plan
    # ----------------------------------------------------------------------
    @governance.get("/cases/{case_id}/plan")
    def governance_plan(
        case_id: str,
        body_region: str = Query("head", pattern=r"^[A-Za-z][A-Za-z _-]{0,31}$"),
        clinical_question: Optional[str] = Query(None, max_length=300),
    ):
        """
        Run the orchestrator's PLANNING step for a case and return what it produced.

        `body_region` and `clinical_question` are inputs supplied by the caller;
        the backend does not infer them. No tool is executed.
        """
        ctx.validate_case_id(case_id)

        # main.py's directory helpers create folders on demand; stay read-only by
        # refusing unknown cases before touching them.
        if not (ctx.upload_dir / case_id).is_dir():
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

        registry, registry_error = _get_registry()
        if registry is None:
            raise HTTPException(
                status_code=503,
                detail=f"Governance planning unavailable: {registry_error}",
            )

        try:
            series_uid, series_dir = ctx.select_series(case_id)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(
                    status_code=409,
                    detail="Upload a CT series to this case before requesting a plan.",
                ) from exc
            raise

        dicom_files = ctx.get_dicom_files(series_dir)
        try:
            ds = pydicom.dcmread(str(dicom_files[0]), stop_before_pixels=True)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Could not read series metadata.") from exc

        modality = str(getattr(ds, "Modality", "")).upper()

        from agent.case_state import CaseModality, CaseState
        from agent.orchestrator import AgentOrchestrator

        try:
            case_modality = CaseModality(modality)
        except ValueError:
            case_modality = CaseModality.UNKNOWN

        case = CaseState(
            case_id=case_id,
            modality=case_modality,
            body_region=body_region.strip().lower(),
            clinical_question=clinical_question,
        )
        case.add_image(
            {
                "series_instance_uid": series_uid,
                "study_instance_uid": str(getattr(ds, "StudyInstanceUID", "")),
                "slice_count": len(dicom_files),
            }
        )

        try:
            plan = AgentOrchestrator(registry).plan(case)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail=f"Orchestrator planning failed: {_describe_error(exc)}",
            ) from exc

        return {
            "notice": RESEARCH_NOTICE,
            "source": "AgentOrchestrator.plan",
            "inputs": {
                "body_region": case.body_region,
                "body_region_source": "supplied by caller (not inferred)",
                "clinical_question": clinical_question,
                "modality": case_modality.value,
                "modality_source": "DICOM Modality of the uploaded series",
            },
            "plan": jsonable_encoder(plan),
        }

    # ----------------------------------------------------------------------
    # GET /governance/cases/{case_id}/audit
    # ----------------------------------------------------------------------
    @governance.get("/cases/{case_id}/audit")
    def governance_audit(case_id: str):
        """
        Read the append-only audit history for a case, if PostgreSQL is reachable.

        The HTTP upload path does not write audit events, so an empty list is the
        normal result for cases created over HTTP.
        """
        ctx.validate_case_id(case_id)

        probe = _database_probe()
        if not probe["configured"]:
            return {
                "available": False,
                "reason": "No database configured (DATABASE_URL is not set).",
                "events": [],
            }
        if not probe["reachable"]:
            return {
                "available": False,
                "reason": f"PostgreSQL is configured but not reachable ({probe['error']}).",
                "events": [],
            }

        try:
            from database.audit import AuditService
            from database.connection import SessionLocal

            with SessionLocal() as session:
                events = AuditService(session).list_case_events(case_id)
                payload = [
                    {
                        "event_id": event.event_id,
                        "timestamp": event.timestamp.isoformat(),
                        "actor_type": event.actor_type,
                        "actor_id": event.actor_id,
                        "action": event.action,
                        "entity_type": event.entity_type,
                        "entity_id": event.entity_id,
                        "metadata": event.metadata_json,
                    }
                    for event in events
                ]
        except Exception as exc:  # noqa: BLE001
            return {
                "available": False,
                "reason": f"Audit read failed: {type(exc).__name__}",
                "events": [],
            }

        return {"available": True, "reason": None, "events": payload}

    return [cases_router, governance]
