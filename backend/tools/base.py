from abc import ABC, abstractmethod
from typing import Any, Dict


class MedicalAITool(ABC):
    """
    Base interface for all registered medical AI tools.

    Every specialist medical AI tool must:
    1. Have a unique name.
    2. Describe what it does.
    3. Accept structured input.
    4. Return a structured result.
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the medical AI tool.

        Parameters
        ----------
        input_data:
            Structured input required by the tool.

        Returns
        -------
        Dict[str, Any]:
            Structured tool output.
        """

        raise NotImplementedError