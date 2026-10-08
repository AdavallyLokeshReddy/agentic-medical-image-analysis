from typing import Any, Dict, List

from .case_state import (
    CaseState,
    CaseStatus,
    VerificationStatus,
)
from .task_graph import TaskGraph, TaskNode
from .safety_contract import (
    SafetyContract,
    DataPolicy,
    OperationPolicy,
    UncertaintyPolicy,
    EscalationPolicy,
    ResourcePolicy,
    ActionTier,
)

from tools.registry import ToolRegistry
from verification.verifier import ICHVerificationEngine


class AgentOrchestrator:
    """
    Generic orchestrator for the governed medical-imaging prototype.

    The orchestrator coordinates:

        - CaseState
        - Tool discovery
        - Safety Contract
        - Bounded TaskGraph
        - Verification

    Current responsibilities:
        1. Receive a CaseState.
        2. Inspect the case.
        3. Discover compatible registered tools.
        4. Create a case-specific safety contract.
        5. Build a bounded task graph constrained by the contract.
        6. Identify tasks that are ready to proceed.
        7. Verify analytical results.
        8. Store verification state inside CaseState.

    Important:
        This version does NOT autonomously execute medical AI tools.

        Tool execution will be added only after:
            - task planning
            - safety-contract
            - verification
            - evidence/provenance
            layers are established.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        verifier: ICHVerificationEngine | None = None,
    ):
        """
        Initialize the orchestrator.

        Parameters
        ----------
        registry:
            ToolRegistry containing registered analytical tools.

        verifier:
            Verification engine used to validate analytical results.

            If no verifier is supplied, the default
            ICHVerificationEngine is created.
        """

        if not isinstance(
            registry,
            ToolRegistry,
        ):
            raise TypeError(
                "registry must be a ToolRegistry instance."
            )

        self.registry = registry

        self.verifier = (
            verifier
            if verifier is not None
            else ICHVerificationEngine()
        )

    # ==================================================================
    # CASE INSPECTION
    # ==================================================================

    def inspect_case(
        self,
        case: CaseState,
    ) -> Dict[str, Any]:
        """
        Inspect the current case without executing any tool.
        """

        if not isinstance(
            case,
            CaseState,
        ):
            raise TypeError(
                "case must be a CaseState instance."
            )

        return {
            "case_id": case.case_id,
            "modality": case.modality.value,
            "body_region": case.body_region,
            "clinical_question": case.clinical_question,
            "image_count": len(case.images),
            "status": case.status.value,
        }

    # ==================================================================
    # TOOL DISCOVERY
    # ==================================================================

    def discover_tools(
        self,
        case: CaseState,
    ) -> List[dict]:
        """
        Discover registered tools compatible with the case.

        Discovery only identifies compatible registered tools.

        It does not:
            - authorize execution
            - execute a tool
            - create evidence
        """

        if not isinstance(
            case,
            CaseState,
        ):
            raise TypeError(
                "case must be a CaseState instance."
            )

        return case.discover_available_tools(
            self.registry
        )

    # ==================================================================
    # SAFETY CONTRACT
    # ==================================================================

    def create_safety_contract(
        self,
        case: CaseState,
    ) -> SafetyContract:
        """
        Create a case-specific safety contract.

        The contract constrains which tools, operations,
        and action authority levels the orchestrator
        may coordinate.

        This implements the paper's safety-contract structure:

            C = (D, V, P, R, Θ, Γ, Δ)

        where:

            D = allowed data
            V = approved tools
            P = task preconditions
            R = allowed operations
            Θ = uncertainty / abstention thresholds
            Γ = escalation paths
            Δ = time / retry / resource restrictions
        """

        if not isinstance(
            case,
            CaseState,
        ):
            raise TypeError(
                "case must be a CaseState instance."
            )

        # --------------------------------------------------------------
        # Discover compatible registered tools.
        #
        # Compatibility is determined by the Tool Registry.
        # The safety contract then explicitly approves those tools
        # for this particular case.
        # --------------------------------------------------------------

        discovered_tools = self.discover_tools(
            case
        )

        approved_tools = [
            tool["name"]
            for tool in discovered_tools
        ]

        # --------------------------------------------------------------
        # Create the case-specific contract.
        # --------------------------------------------------------------

        contract = SafetyContract(
            contract_id=f"{case.case_id}-SAFETY",

            # ----------------------------------------------------------
            # D = Allowed data
            # ----------------------------------------------------------

            data_policy=DataPolicy(
                allowed_modalities=[
                    case.modality.value
                ],

                allowed_body_regions=[
                    case.body_region
                ],

                required_data=[
                    "imaging_data",
                    "modality",
                    "body_region",
                ],
            ),

            # ----------------------------------------------------------
            # V = Approved tools
            # ----------------------------------------------------------

            approved_tools=approved_tools,

            # ----------------------------------------------------------
            # P = Task preconditions
            # ----------------------------------------------------------

            task_preconditions={
                "intake": [
                    "Case exists.",
                ],

                "technical_validation": [
                    "Imaging data is available.",
                    "Modality is identified.",
                    "Body region is identified.",
                ],

                "ich_analysis": [
                    "Technical validation completed.",
                    "Compatible analytical tool is available.",
                ],

                "verification": [
                    "Analytical result exists.",
                ],

                "human_review": [
                    "Verification indicates human review "
                    "is required.",
                ],
            },

            # ----------------------------------------------------------
            # R = Allowed operations
            # ----------------------------------------------------------

            operation_policy=OperationPolicy(
                allowed_operations=[
                    "observe",
                    "analyze",
                    "verify",
                    "recommend_review",
                ],

                # The prototype may recommend/escalate,
                # but cannot autonomously perform high-consequence
                # clinical actions.
                maximum_action_tier=ActionTier.T1,
            ),

            # ----------------------------------------------------------
            # Θ = Uncertainty / abstention policy
            # ----------------------------------------------------------

            uncertainty_policy=UncertaintyPolicy(
                minimum_confidence=0.5,

                require_verification=True,

                abstain_on_missing_evidence=True,

                abstain_on_verification_failure=True,
            ),

            # ----------------------------------------------------------
            # Γ = Escalation paths
            # ----------------------------------------------------------

            escalation_policy=EscalationPolicy(
                escalation_paths=[
                    "human_review",
                ],

                human_review_required=True,
            ),

            # ----------------------------------------------------------
            # Δ = Resource restrictions
            # ----------------------------------------------------------

            resource_policy=ResourcePolicy(
                maximum_retries=0,

                timeout_seconds=300,

                maximum_concurrent_tools=1,
            ),
        )

        # --------------------------------------------------------------
        # Store the contract inside CaseState.
        # --------------------------------------------------------------

        case.safety_contract = contract

        case.touch()

        return contract

    # ==================================================================
    # TASK GRAPH
    # ==================================================================

    def create_task_graph(
        self,
        case: CaseState,
    ) -> TaskGraph:
        """
        Construct the bounded task graph for the case.

        The graph describes workflow dependencies but does not
        execute any medical AI capability.

        The analysis task is constrained by the case-specific
        safety contract.
        """

        if not isinstance(
            case,
            CaseState,
        ):
            raise TypeError(
                "case must be a CaseState instance."
            )

        # --------------------------------------------------------------
        # Safety contract must exist before task planning.
        # --------------------------------------------------------------

        contract = case.safety_contract

        if contract is None:
            raise RuntimeError(
                "Safety contract must exist before "
                "creating the task graph."
            )

        graph = TaskGraph()

        # --------------------------------------------------------------
        # 1. INTAKE
        # --------------------------------------------------------------

        intake_task = TaskNode(
            task_id=f"{case.case_id}-INTAKE",

            task_type="intake",

            description=(
                "Receive and identify the imaging case."
            ),

            preconditions=contract.task_preconditions[
                "intake"
            ],

            stopping_conditions=[
                "Required case information is unavailable.",
            ],
        )

        graph.add_task(
            intake_task
        )

        # --------------------------------------------------------------
        # 2. TECHNICAL VALIDATION
        # --------------------------------------------------------------

        technical_task = TaskNode(
            task_id=f"{case.case_id}-TECHNICAL",

            task_type="technical_validation",

            description=(
                "Validate technical imaging requirements "
                "before analytical processing."
            ),

            dependencies=[
                intake_task.task_id
            ],

            preconditions=contract.task_preconditions[
                "technical_validation"
            ],

            stopping_conditions=[
                "Required technical checks fail.",
            ],
        )

        graph.add_task(
            technical_task
        )

        # --------------------------------------------------------------
        # 3. ANALYSIS
        # --------------------------------------------------------------

        # Only tools explicitly approved by the safety contract
        # may enter the analysis task.
        permitted_tools = [
            tool_name
            for tool_name in case.available_tools
            if contract.is_tool_permitted(
                tool_name
            )
        ]

        analysis_task = TaskNode(
            task_id=f"{case.case_id}-ANALYSIS",

            task_type="ich_analysis",

            description=(
                "Analyze the CT study using a permitted "
                "registered ICH detection tool."
            ),

            dependencies=[
                technical_task.task_id
            ],

            permitted_tools=permitted_tools,

            preconditions=contract.task_preconditions[
                "ich_analysis"
            ],

            verification_required=True,

            stopping_conditions=[
                "No permitted analytical tool is available.",
                "Required analytical input is unavailable.",
            ],
        )

        graph.add_task(
            analysis_task
        )

        # --------------------------------------------------------------
        # 4. VERIFICATION
        # --------------------------------------------------------------

        verification_task = TaskNode(
            task_id=f"{case.case_id}-VERIFICATION",

            task_type="verification",

            description=(
                "Verify technical, applicability, and "
                "cross-output safety conditions."
            ),

            dependencies=[
                analysis_task.task_id
            ],

            preconditions=contract.task_preconditions[
                "verification"
            ],

            verification_required=True,

            stopping_conditions=[
                "Required verification checks fail.",
            ],
        )

        graph.add_task(
            verification_task
        )

        # --------------------------------------------------------------
        # 5. HUMAN REVIEW
        # --------------------------------------------------------------

        human_review_task = TaskNode(
            task_id=f"{case.case_id}-HUMAN-REVIEW",

            task_type="human_review",

            description=(
                "Escalate the case for human review when "
                "verification requires review."
            ),

            dependencies=[
                verification_task.task_id
            ],

            preconditions=contract.task_preconditions[
                "human_review"
            ],

            stopping_conditions=[
                "Human review is not required.",
            ],
        )

        graph.add_task(
            human_review_task
        )

        # --------------------------------------------------------------
        # Store the graph inside CaseState.
        # --------------------------------------------------------------

        case.task_graph = graph

        case.touch()

        return graph

    # ==================================================================
    # PLANNING
    # ==================================================================

    def plan(
        self,
        case: CaseState,
    ) -> Dict[str, Any]:
        """
        Inspect the case, discover tools, create the safety contract,
        construct the bounded task graph, and identify currently
        ready tasks.

        No medical AI tool is executed here.
        """

        if not isinstance(
            case,
            CaseState,
        ):
            raise TypeError(
                "case must be a CaseState instance."
            )

        # --------------------------------------------------------------
        # Set case status.
        # --------------------------------------------------------------

        case.set_status(
            CaseStatus.ANALYZING
        )

        # --------------------------------------------------------------
        # Inspect case.
        # --------------------------------------------------------------

        case_info = self.inspect_case(
            case
        )

        # --------------------------------------------------------------
        # Discover compatible registered tools.
        # --------------------------------------------------------------

        available_tools = self.discover_tools(
            case
        )

        # --------------------------------------------------------------
        # Create case-specific safety contract.
        # --------------------------------------------------------------

        safety_contract = self.create_safety_contract(
            case
        )

        # --------------------------------------------------------------
        # Build bounded task graph.
        # --------------------------------------------------------------

        task_graph = self.create_task_graph(
            case
        )

        # --------------------------------------------------------------
        # Identify tasks whose dependencies are satisfied.
        # --------------------------------------------------------------

        ready_tasks = [
            task.to_dict()
            for task in task_graph.get_ready_tasks()
        ]

        # --------------------------------------------------------------
        # Return complete planning result.
        # --------------------------------------------------------------

        return {
            "case": case_info,

            "available_tools": available_tools,

            "safety_contract":
                safety_contract.to_dict(),

            "task_graph":
                task_graph.to_dict(),

            "ready_tasks":
                ready_tasks,

            "selected_tools":
                list(
                    case.selected_tools
                ),

            # Planning does NOT mean execution.
            "execution_started": False,
        }

    # ==================================================================
    # TOOL SELECTION
    # ==================================================================

    def select_tool(
        self,
        case: CaseState,
        tool_name: str,
    ) -> Dict[str, Any]:
        """
        Select one tool that has already been discovered as compatible
        AND explicitly approved by the case safety contract.

        This only records selection.
        It does not execute the tool.
        """

        if not isinstance(
            case,
            CaseState,
        ):
            raise TypeError(
                "case must be a CaseState instance."
            )

        # --------------------------------------------------------------
        # Tool must exist in the registry.
        # --------------------------------------------------------------

        if not self.registry.is_tool_available(
            tool_name
        ):
            raise ValueError(
                f"Tool '{tool_name}' is not registered."
            )

        # --------------------------------------------------------------
        # Safety contract must exist before selection.
        # --------------------------------------------------------------

        if case.safety_contract is None:
            raise RuntimeError(
                "Safety contract must exist before "
                "selecting a tool."
            )

        # --------------------------------------------------------------
        # Tool must be explicitly approved by the contract.
        # --------------------------------------------------------------

        validation = (
            case.safety_contract.validate_tool(
                tool_name
            )
        )

        if not validation["allowed"]:
            raise PermissionError(
                validation["reason"]
            )

        # --------------------------------------------------------------
        # Record the tool selection.
        # --------------------------------------------------------------

        case.select_tool(
            tool_name
        )

        metadata = self.registry.get_metadata(
            tool_name
        )

        return {
            "name": tool_name,

            "description": (
                self.registry
                .get(tool_name)
                .description
            ),

            "version": metadata.version,

            "intended_use":
                metadata.intended_use,

            "supported_modalities":
                metadata.supported_modalities,

            "supported_body_regions":
                metadata.supported_body_regions,
        }

    # ==================================================================
    # VERIFICATION
    # ==================================================================

    def verify_analysis(
        self,
        case: CaseState,
        detection_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Verify an analytical result produced for the case.

        This method:

            1. Validates the case.
            2. Confirms that a Safety Contract exists.
            3. Confirms that verification is permitted.
            4. Builds verifier input from CaseState.
            5. Runs the verification engine.
            6. Stores verification state in CaseState.
            7. Updates the verification task.
            8. Updates the case lifecycle status.

        Important:
            Verification does not authorize diagnosis,
            treatment, or irreversible clinical action.
        """

        # --------------------------------------------------------------
        # Validate case
        # --------------------------------------------------------------

        if not isinstance(
            case,
            CaseState,
        ):
            raise TypeError(
                "case must be a CaseState instance."
            )

        # --------------------------------------------------------------
        # Validate detection result
        # --------------------------------------------------------------

        if not isinstance(
            detection_result,
            dict,
        ):
            raise TypeError(
                "detection_result must be a dictionary."
            )

        # --------------------------------------------------------------
        # Safety Contract must exist
        # --------------------------------------------------------------

        contract = case.safety_contract

        if contract is None:
            raise RuntimeError(
                "Safety contract must exist before "
                "verification."
            )

        # --------------------------------------------------------------
        # Verification must be explicitly permitted
        # by the Safety Contract.
        # --------------------------------------------------------------

        if not contract.is_operation_permitted(
            "verify"
        ):
            raise PermissionError(
                "Verification operation is not permitted "
                "by the case safety contract."
            )

        # --------------------------------------------------------------
        # Build CT metadata from CaseState.
        #
        # Nothing here is hardcoded to CASE-0004.
        # --------------------------------------------------------------

        ct_metadata = {
            "modality": case.modality.value,

            "body_region": case.body_region,

            "slice_count": case.metadata.get(
                "slice_count"
            ),

            "voxel_spacing": case.metadata.get(
                "voxel_spacing"
            ),

            "study_instance_uid": case.metadata.get(
                "study_instance_uid"
            ),

            "series_instance_uid": case.metadata.get(
                "series_instance_uid"
            ),
        }

        # --------------------------------------------------------------
        # Run the verification engine.
        # --------------------------------------------------------------

        verification_result = self.verifier.verify(
            {
                "ct_metadata": ct_metadata,

                "detection_result": detection_result,
            }
        )

        # --------------------------------------------------------------
        # Extract verifier output.
        # --------------------------------------------------------------

        verification = verification_result[
            "verification"
        ]

        decision = verification_result[
            "decision"
        ]

        checks = verification.get(
            "checks",
            {}
        )

        # --------------------------------------------------------------
        # Convert verification checks into the
        # CaseState representation.
        # --------------------------------------------------------------

        check_list: List[Dict[str, Any]] = []

        for name, result in checks.items():

            check_list.append(
                {
                    "name": name,
                    **result,
                }
            )

        # --------------------------------------------------------------
        # Collect warnings.
        # --------------------------------------------------------------

        warnings: List[str] = []

        for name, result in checks.items():

            if result.get(
                "status"
            ) == "warning":

                message = result.get(
                    "message"
                )

                if message:
                    warnings.append(
                        message
                    )

                warnings.extend(
                    result.get(
                        "warnings",
                        [],
                    )
                )

        # --------------------------------------------------------------
        # Collect failed checks.
        # --------------------------------------------------------------

        failed_checks = list(
            decision.get(
                "failed_checks",
                [],
            )
        )

        # --------------------------------------------------------------
        # Determine CaseState verification status
        # and overall lifecycle status.
        # --------------------------------------------------------------

        decision_status = decision.get(
            "status"
        )

        if decision_status == "blocked":

            verification_status = (
                VerificationStatus.FAILED
            )

            case_status = (
                CaseStatus.FAILED
            )

        elif decision_status == "requires_review":

            verification_status = (
                VerificationStatus.REQUIRES_REVIEW
            )

            case_status = (
                CaseStatus.REQUIRES_REVIEW
            )

        elif (
            decision_status
            == "verified_for_workflow_review"
        ):

            # All verification checks passed,
            # but human review remains mandatory.
            verification_status = (
                VerificationStatus.PASSED
            )

            case_status = (
                CaseStatus.REQUIRES_REVIEW
            )

        else:

            # Defensive fallback.
            #
            # An unknown verifier decision should
            # never silently pass through the system.
            verification_status = (
                VerificationStatus.FAILED
            )

            case_status = (
                CaseStatus.FAILED
            )

            failed_checks.append(
                "unknown_verification_decision"
            )

            warnings.append(
                "Verifier returned an unknown decision status."
            )

        # --------------------------------------------------------------
        # Store verification state in CaseState.
        # --------------------------------------------------------------

        case.set_verification(
            status=verification_status,

            checks=check_list,

            warnings=warnings,

            failed_checks=failed_checks,

            human_review_required=decision.get(
                "human_review_required",
                True,
            ),
        )

        # --------------------------------------------------------------
        # Preserve complete verifier provenance.
        #
        # This will become useful when we implement
        # Evidence Objects / Provenance.
        # --------------------------------------------------------------

        case.verification.metadata = {
            "verifier":
                verification_result.get(
                    "verifier"
                ),

            "decision":
                decision,

            "safety":
                verification_result.get(
                    "safety",
                    {},
                ),

            "all_required_checks_passed":
                verification.get(
                    "all_required_checks_passed",
                    False,
                ),

            "warnings_present":
                verification.get(
                    "warnings_present",
                    False,
                ),
        }

        # --------------------------------------------------------------
        # Update case lifecycle status.
        # --------------------------------------------------------------

        case.set_status(
            case_status
        )

        # --------------------------------------------------------------
        # Update verification task in TaskGraph.
        # --------------------------------------------------------------

        verification_task_id = (
            f"{case.case_id}-VERIFICATION"
        )

        verification_task = (
            case.task_graph.get_task(
                verification_task_id
            )
        )

        if verification_task is not None:

            if decision_status == "blocked":

                case.task_graph.mark_failed(
                    verification_task_id
                )

            else:

                case.task_graph.mark_completed(
                    verification_task_id
                )

            case.touch()

        # --------------------------------------------------------------
        # Return integration result.
        # --------------------------------------------------------------

        return {
            "case_id":
                case.case_id,

            "verification_result":
                verification_result,

            "case_verification_status":
                case.verification.status.value,

            "case_status":
                case.status.value,

            "human_review_required":
                case.verification.human_review_required,
        }

    # ==================================================================
    # SUMMARY
    # ==================================================================

    def summary(
        self,
        case: CaseState,
    ) -> Dict[str, Any]:
        """
        Return a compact orchestrator/case summary.
        """

        if not isinstance(
            case,
            CaseState,
        ):
            raise TypeError(
                "case must be a CaseState instance."
            )

        return {
            "case": case.summary(),

            "registered_tools": [
                tool["name"]
                for tool in self.registry.list_tools()
            ],
        }