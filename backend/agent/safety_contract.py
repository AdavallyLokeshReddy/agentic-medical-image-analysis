from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class ActionTier(str, Enum):
    """
    Action authority levels defined by the safety-contract framework.

    T0: Observe
    T1: Recommend
    T2: Reversible workflow action
    T3: Time-critical / high-consequence action
    """

    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


@dataclass
class DataPolicy:
    """
    Defines what data the agent is allowed to use.
    """

    allowed_modalities: List[str] = field(
        default_factory=list
    )

    allowed_body_regions: List[str] = field(
        default_factory=list
    )

    required_data: List[str] = field(
        default_factory=list
    )


@dataclass
class OperationPolicy:
    """
    Defines which operations the agent is allowed to perform.
    """

    allowed_operations: List[str] = field(
        default_factory=list
    )

    maximum_action_tier: ActionTier = ActionTier.T1


@dataclass
class UncertaintyPolicy:
    """
    Defines prototype uncertainty and abstention rules.

    These thresholds are configuration values for the research
    prototype and are NOT clinically validated thresholds.
    """

    minimum_confidence: float = 0.5

    require_verification: bool = True

    abstain_on_missing_evidence: bool = True

    abstain_on_verification_failure: bool = True


@dataclass
class EscalationPolicy:
    """
    Defines what happens when the agent cannot safely continue.
    """

    escalation_paths: List[str] = field(
        default_factory=list
    )

    human_review_required: bool = True


@dataclass
class ResourcePolicy:
    """
    Defines time, retry, and resource restrictions.
    """

    maximum_retries: int = 0

    timeout_seconds: int = 300

    maximum_concurrent_tools: int = 1


@dataclass
class SafetyContract:
    """
    Case-specific safety contract.

    Implements:

        C = (D, V, P, R, Θ, Γ, Δ)

    where:

        D = allowed data
        V = approved tools
        P = task preconditions
        R = allowed operations
        Θ = uncertainty/abstention thresholds
        Γ = escalation paths
        Δ = time/retry/resource restrictions
    """

    contract_id: str

    data_policy: DataPolicy

    approved_tools: List[str] = field(
        default_factory=list
    )

    task_preconditions: Dict[str, List[str]] = field(
        default_factory=dict
    )

    operation_policy: OperationPolicy = field(
        default_factory=OperationPolicy
    )

    uncertainty_policy: UncertaintyPolicy = field(
        default_factory=UncertaintyPolicy
    )

    escalation_policy: EscalationPolicy = field(
        default_factory=EscalationPolicy
    )

    resource_policy: ResourcePolicy = field(
        default_factory=ResourcePolicy
    )

    def is_tool_permitted(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether a tool is explicitly approved.
        """

        return tool_name in self.approved_tools

    def is_operation_permitted(
        self,
        operation: str,
    ) -> bool:
        """
        Check whether an operation is explicitly allowed.
        """

        return (
            operation
            in self.operation_policy.allowed_operations
        )

    def is_action_tier_permitted(
        self,
        action_tier: ActionTier,
    ) -> bool:
        """
        Check whether an action tier is within the
        contract's maximum authority.
        """

        tier_order = {
            ActionTier.T0: 0,
            ActionTier.T1: 1,
            ActionTier.T2: 2,
            ActionTier.T3: 3,
        }

        return (
            tier_order[action_tier]
            <= tier_order[
                self.operation_policy.maximum_action_tier
            ]
        )

    def are_task_preconditions_defined(
        self,
        task_type: str,
    ) -> bool:
        """
        Check whether the contract defines preconditions
        for a task type.
        """

        return task_type in self.task_preconditions

    def validate_tool(
        self,
        tool_name: str,
    ) -> Dict[str, Any]:
        """
        Return an explicit allow/block decision for a tool.
        """

        if not self.is_tool_permitted(tool_name):
            return {
                "allowed": False,
                "reason": (
                    f"Tool '{tool_name}' is not "
                    "approved by the safety contract."
                ),
            }

        return {
            "allowed": True,
            "reason": (
                f"Tool '{tool_name}' is approved "
                "by the safety contract."
            ),
        }

    def validate_action_tier(
        self,
        action_tier: ActionTier,
    ) -> Dict[str, Any]:
        """
        Return an explicit allow/block decision
        for an action authority level.
        """

        if not self.is_action_tier_permitted(
            action_tier
        ):
            return {
                "allowed": False,
                "reason": (
                    f"Action tier {action_tier.value} "
                    "exceeds the contract authority."
                ),
            }

        return {
            "allowed": True,
            "reason": (
                f"Action tier {action_tier.value} "
                "is permitted."
            ),
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the complete safety contract.
        """

        return {
            "contract_id": self.contract_id,
            "data_policy": {
                "allowed_modalities":
                    list(
                        self.data_policy.allowed_modalities
                    ),
                "allowed_body_regions":
                    list(
                        self.data_policy.allowed_body_regions
                    ),
                "required_data":
                    list(
                        self.data_policy.required_data
                    ),
            },
            "approved_tools":
                list(self.approved_tools),
            "task_preconditions": {
                task_type: list(preconditions)
                for task_type, preconditions
                in self.task_preconditions.items()
            },
            "operation_policy": {
                "allowed_operations":
                    list(
                        self.operation_policy
                        .allowed_operations
                    ),
                "maximum_action_tier":
                    self.operation_policy
                    .maximum_action_tier.value,
            },
            "uncertainty_policy": {
                "minimum_confidence":
                    self.uncertainty_policy
                    .minimum_confidence,
                "require_verification":
                    self.uncertainty_policy
                    .require_verification,
                "abstain_on_missing_evidence":
                    self.uncertainty_policy
                    .abstain_on_missing_evidence,
                "abstain_on_verification_failure":
                    self.uncertainty_policy
                    .abstain_on_verification_failure,
            },
            "escalation_policy": {
                "escalation_paths":
                    list(
                        self.escalation_policy
                        .escalation_paths
                    ),
                "human_review_required":
                    self.escalation_policy
                    .human_review_required,
            },
            "resource_policy": {
                "maximum_retries":
                    self.resource_policy
                    .maximum_retries,
                "timeout_seconds":
                    self.resource_policy
                    .timeout_seconds,
                "maximum_concurrent_tools":
                    self.resource_policy
                    .maximum_concurrent_tools,
            },
        }