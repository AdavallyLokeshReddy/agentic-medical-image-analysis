"""
Execution adapters: the only place that knows WHERE a tool runs.

Stage 1 runs the tool in this process (LocalToolAdapter). A later adapter can send the same
`execute(tool_name, input)` call to a remote worker without changing the job service, the routes,
the governance layer or the frontend.

The adapter never decides whether a tool is ALLOWED. It only declares what it is able to run;
authorization stays with the orchestrator and the Safety Contract.
"""
from __future__ import annotations

import importlib.util
import json
import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Optional

from tools.base import MedicalAITool
from tools.registry import ToolMetadata, ToolRegistry


class ToolRuntimeUnavailable(RuntimeError):
    """The model runtime cannot be loaded. The message says why; it is shown to the user."""


class ExecutionAdapter(ABC):
    name: str = "adapter"

    @abstractmethod
    def registry(self) -> ToolRegistry:
        """Registry the orchestrator plans against (metadata + tool handles)."""

    @abstractmethod
    def executable_tools(self) -> frozenset[str]:
        """Tool names this adapter can actually run."""

    @abstractmethod
    def runtime_status(self) -> dict[str, Any]:
        """Cheap readiness report. Must never load a model."""

    @abstractmethod
    def execute(self, tool_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run a tool and return its structured result."""

    def provenance(self) -> dict[str, Any]:
        """Facts about the runtime for evidence provenance."""
        return {"adapter": self.name}


class _LazyTool(MedicalAITool):
    """
    Registered so the orchestrator can discover and plan. It delegates every run() to the real tool,
    which is loaded on first use. It produces no output of its own: if the real tool cannot load,
    run() raises ToolRuntimeUnavailable.
    """

    def __init__(self, name: str, description: str, loader: Callable[[], MedicalAITool]):
        self.name = name
        self.description = description
        self._loader = loader

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return self._loader().run(input_data)


def _default_metadata(tool_name: str) -> tuple[str, str, ToolMetadata]:
    """Reuse the project's own ToolMetadata (single source of truth) without constructing any model."""
    from governance_api import _get_registry

    registry, error = _get_registry()
    if registry is None:
        raise ToolRuntimeUnavailable(f"Tool metadata could not be built: {error}")
    tool = registry.get(tool_name)
    return tool.name, tool.description, registry.get_metadata(tool_name)


def _default_factory() -> MedicalAITool:
    try:
        from tools.ich_detection import ICHDetectionTool
    except Exception as error:  # torch missing, skp missing, ...
        raise ToolRuntimeUnavailable(
            f"The ICH tool cannot be imported: {type(error).__name__}: {error}"
        ) from error
    try:
        return ICHDetectionTool()
    except Exception as error:  # weights download or load failure
        raise ToolRuntimeUnavailable(
            f"The ICH research model could not be loaded: {type(error).__name__}: {error}"
        ) from error


class LocalToolAdapter(ExecutionAdapter):
    """Runs the CT-1 ICH tool in this process. One loaded model, shared by sequential jobs."""

    name = "local_in_process"
    TOOL = "ich_detection"

    def __init__(
        self,
        tool_factory: Optional[Callable[[], MedicalAITool]] = None,
        metadata_provider: Optional[Callable[[str], tuple[str, str, ToolMetadata]]] = None,
        required_modules: Optional[tuple[str, ...]] = None,
    ):
        injected = tool_factory is not None
        self._factory = tool_factory or _default_factory
        self._metadata_provider = metadata_provider or _default_metadata
        # An injected factory (tests) brings its own runtime; the real one needs these packages.
        self._required = required_modules if required_modules is not None else (() if injected else ("torch", "skp"))
        self._lock = threading.RLock()
        self._registry: Optional[ToolRegistry] = None
        self._tool: Optional[MedicalAITool] = None

    # -- planning handle -----------------------------------------------------------------------
    def registry(self) -> ToolRegistry:
        with self._lock:
            if self._registry is None:
                name, description, metadata = self._metadata_provider(self.TOOL)
                registry = ToolRegistry()
                registry.register(_LazyTool(name, description, self._load_tool), metadata=metadata)
                self._registry = registry
            return self._registry

    def executable_tools(self) -> frozenset[str]:
        return frozenset({self.TOOL})

    # -- readiness -----------------------------------------------------------------------------
    def runtime_status(self) -> dict[str, Any]:
        missing = []
        for module in self._required:
            try:
                found = importlib.util.find_spec(module) is not None
            except (ImportError, ValueError):
                found = False
            if not found:
                missing.append(module)
        return {
            "adapter": self.name,
            "tool": self.TOOL,
            "available": not missing,
            "missing_modules": missing,
            "reason": None if not missing else f"Missing Python packages: {', '.join(missing)}",
            "model_loaded": self._tool is not None,
        }

    # -- execution -----------------------------------------------------------------------------
    def _load_tool(self) -> MedicalAITool:
        with self._lock:
            if self._tool is None:
                self._tool = self._factory()  # raises ToolRuntimeUnavailable on failure; not cached
            return self._tool

    def execute(self, tool_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self.executable_tools():
            raise PermissionError(f"Adapter '{self.name}' cannot execute tool '{tool_name}'.")
        return self.registry().run(tool_name, input_data)

    def provenance(self) -> dict[str, Any]:
        info: dict[str, Any] = {"adapter": self.name, "execution": "in-process on the API host"}
        manifest = Path(os.environ.get("HF_HOME", "")) / "model_manifest.json" if os.environ.get("HF_HOME") else None
        if manifest and manifest.is_file():
            try:
                info["weights_manifest"] = json.loads(manifest.read_text())
            except (OSError, ValueError):
                info["weights_manifest"] = "unreadable"
        return info
