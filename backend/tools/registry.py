from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import MedicalAITool


@dataclass
class ToolMetadata:
    """
    Metadata describing a registered medical AI tool.

    The metadata allows the agent to determine whether a tool
    is appropriate for the current case before executing it.
    """

    supported_modalities: List[str] = field(default_factory=list)

    supported_body_regions: List[str] = field(default_factory=list)

    intended_use: str = ""

    expected_inputs: List[str] = field(default_factory=list)

    output_schema: Optional[Dict[str, Any]] = None

    validation_population: str = ""

    exclusions: List[str] = field(default_factory=list)

    version: str = "unknown"

    compute_requirements: Dict[str, Any] = field(
        default_factory=dict
    )


class ToolRegistry:
    """
    Registry of approved medical AI tools.

    The registry provides a controlled way for the agent
    to discover, inspect, select, and execute registered tools.

    The registry is intentionally separate from the agent.
    The agent can ask the registry what tools are available,
    but the registry remains responsible for the registered
    tool implementations.
    """

    def __init__(self):
        self._tools: Dict[str, MedicalAITool] = {}

        self._metadata: Dict[str, ToolMetadata] = {}

    def register(
        self,
        tool: MedicalAITool,
        metadata: Optional[ToolMetadata] = None,
    ) -> None:
        """
        Register a medical AI tool.

        Parameters
        ----------
        tool:
            An instance of MedicalAITool.

        metadata:
            Optional ToolMetadata describing the tool's
            supported modality, body region, intended use,
            validation scope, version, etc.
        """

        if not isinstance(tool, MedicalAITool):
            raise TypeError(
                "Only MedicalAITool instances can be registered."
            )

        if not tool.name:
            raise ValueError(
                "Tool must have a non-empty name."
            )

        if tool.name in self._tools:
            raise ValueError(
                f"Tool already registered: {tool.name}"
            )

        self._tools[tool.name] = tool

        if metadata is None:
            metadata = ToolMetadata()

        self._metadata[tool.name] = metadata

    def get(self, tool_name: str) -> MedicalAITool:
        """
        Retrieve a registered tool by name.
        """

        if tool_name not in self._tools:
            raise KeyError(
                f"Tool not found: {tool_name}"
            )

        return self._tools[tool_name]

    def get_metadata(self, tool_name: str) -> ToolMetadata:
        """
        Retrieve metadata for a registered tool.
        """

        if tool_name not in self._metadata:
            raise KeyError(
                f"Tool metadata not found: {tool_name}"
            )

        return self._metadata[tool_name]

    def list_tools(self) -> List[dict]:
        """
        Return metadata for all registered tools.

        This is the main discovery interface that the future
        agent/orchestrator will use.
        """

        tools = []

        for tool_name, tool in self._tools.items():
            metadata = self._metadata[tool_name]

            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "supported_modalities": (
                        metadata.supported_modalities
                    ),
                    "supported_body_regions": (
                        metadata.supported_body_regions
                    ),
                    "intended_use": metadata.intended_use,
                    "expected_inputs": metadata.expected_inputs,
                    "output_schema": metadata.output_schema,
                    "validation_population": (
                        metadata.validation_population
                    ),
                    "exclusions": metadata.exclusions,
                    "version": metadata.version,
                    "compute_requirements": (
                        metadata.compute_requirements
                    ),
                }
            )

        return tools

    def find_tools(
        self,
        modality: Optional[str] = None,
        body_region: Optional[str] = None,
    ) -> List[dict]:
        """
        Find registered tools that are appropriate for a case.

        Parameters
        ----------
        modality:
            Imaging modality such as CT, MRI, or X-RAY.

        body_region:
            Anatomical region such as head, chest, or abdomen.

        Returns
        -------
        List[dict]
            Matching registered tool descriptions.

        Important:
        This method performs tool capability matching only.
        It does not execute any medical AI tool.
        """

        matching_tools = []

        for tool_name, tool in self._tools.items():
            metadata = self._metadata[tool_name]

            modality_matches = True
            body_region_matches = True

            if modality is not None:
                modality_matches = (
                    modality.upper()
                    in [
                        value.upper()
                        for value in metadata.supported_modalities
                    ]
                )

            if body_region is not None:
                body_region_matches = (
                    body_region.lower()
                    in [
                        value.lower()
                        for value in metadata.supported_body_regions
                    ]
                )

            if modality_matches and body_region_matches:
                matching_tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "supported_modalities": (
                            metadata.supported_modalities
                        ),
                        "supported_body_regions": (
                            metadata.supported_body_regions
                        ),
                        "intended_use": metadata.intended_use,
                        "version": metadata.version,
                    }
                )

        return matching_tools

    def is_tool_available(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether a tool is registered.
        """

        return tool_name in self._tools

    def run(
        self,
        tool_name: str,
        input_data: dict,
    ) -> dict:
        """
        Execute a registered tool.

        The registry only executes tools that have already
        been explicitly registered.
        """

        tool = self.get(tool_name)

        return tool.run(input_data)


# Global registry used by the backend.
tool_registry = ToolRegistry()