"""
Live walk-through of the governed workflow using the project's REAL library code:
CaseState, ToolRegistry, AgentOrchestrator, SafetyContract, TaskGraph,
ICHVerificationEngine, StructuredDraftReport, ReviewLifecycle, triage and communication.

IMPORTANT: no AI model runs here. The "detection result" is a hand-written SYNTHETIC TEST
INPUT used to exercise the verifier and the governance logic. Every value printed from it is
labelled synthetic. Nothing here is a finding.

Run from the repository root:   python scripts/demo_governed_workflow.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from agent.case_state import (  # noqa: E402
    CaseModality, CaseState, EvidenceItem, EvidenceProvenance, EvidenceStatus,
)
from agent.communication import (  # noqa: E402
    CommunicationRecord, TriageLevel, TriageRecord,
)
from agent.human_review import HumanReview  # noqa: E402
from agent.orchestrator import AgentOrchestrator  # noqa: E402
from agent.review_lifecycle import ReviewLifecycle  # noqa: E402
from reporting.structured_report import create_structured_draft_report  # noqa: E402
from tools.base import MedicalAITool  # noqa: E402
from tools.registry import ToolMetadata, ToolRegistry  # noqa: E402

WIDTH = 78


def banner(text):
    print("\n" + "=" * WIDTH)
    print(text)
    print("=" * WIDTH)


def step(text):
    print(f"\n--- {text}")


class PlanningOnlyStub(MedicalAITool):
    """Registered so the orchestrator can discover and plan. It never runs a model."""

    name = "ich_detection"
    description = "Planning-only stub of the registered ICH detection tool (no model)."

    def run(self, input_data):
        raise RuntimeError("Planning-only stub: no model is executed in this demo.")


def build_registry():
    registry = ToolRegistry()
    registry.register(
        PlanningOnlyStub(),
        ToolMetadata(
            supported_modalities=["CT"],
            supported_body_regions=["head", "brain"],
            intended_use="Research/demo detection of suspected intracranial hemorrhage.",
            validation_population="Research/demo use only. Clinical validation not established.",
            exclusions=["Not a clinical diagnosis.", "Not for autonomous decisions."],
            version="research-model",
        ),
    )
    return registry


def new_case(case_id):
    case = CaseState(
        case_id=case_id,
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Research demonstration: workflow governance only",
    )
    case.metadata.update(
        {
            "slice_count": 24,
            "voxel_spacing": [1.0, 0.5, 0.5],
            "study_instance_uid": "1.2.3.4.5",
            "series_instance_uid": "1.2.3.4.5.6",
        }
    )
    return case


def synthetic_detection(probability, status="completed", with_evidence=True):
    result = {"status": status, "prediction": {"any_probability": probability}}
    if with_evidence:
        result["evidence"] = {"model": "SYNTHETIC TEST INPUT"}
        result["series"] = {"supporting_slices": [10, 11, 12]}
    return result


def show_verification(outcome):
    verification = outcome["verification_result"]["verification"]
    decision = outcome["verification_result"]["decision"]
    for name, check in verification["checks"].items():
        print(f"    {check['status']:<8} {name}")
    print(f"  decision        : {decision['status']}")
    print(f"  action          : {decision['action']}")
    print(f"  reason          : {decision['reason']}")
    print(f"  case status     : {outcome['case_status']}")
    print(f"  verification    : {outcome['case_verification_status']}")
    print(f"  human review    : required = {outcome['human_review_required']}")
    safety = outcome["verification_result"]["safety"]
    print(f"  safety boundary : {safety}")


def run_scenario(orchestrator, case_id, title, detection):
    banner(f"SCENARIO {case_id}: {title}")
    case = new_case(case_id)

    step("1. Orchestrator plans the case (no tool is executed)")
    plan = orchestrator.plan(case)
    print(f"  tools discovered : {[t['name'] for t in plan['available_tools']]}")
    print(f"  tasks in graph   : {[t['task_type'] for t in plan['task_graph']['tasks']]}")
    print(f"  execution_started: {plan['execution_started']}")
    contract = plan["safety_contract"]
    print(f"  allowed ops      : {contract['operation_policy']['allowed_operations']}")
    print(f"  max action tier  : {contract['operation_policy']['maximum_action_tier']}")

    step("2. Tool is selected, only if the safety contract approves it")
    orchestrator.select_tool(case, "ich_detection")
    print(f"  selected tools   : {case.selected_tools}")
    try:
        orchestrator.select_tool(case, "not_a_registered_tool")
    except ValueError as error:
        print(f"  unknown tool     : refused ({error})")

    step("3. Verifier checks the SYNTHETIC test input")
    print(f"  input            : {detection['status']}, any_probability = "
          f"{detection['prediction'].get('any_probability')}  [SYNTHETIC TEST INPUT]")
    outcome = orchestrator.verify_analysis(case, detection)
    show_verification(outcome)
    return case, outcome


def main():
    registry = build_registry()
    orchestrator = AgentOrchestrator(registry)

    banner("GOVERNED WORKFLOW DEMO: real governance code, synthetic test inputs, no model")

    # A: everything passes, human review still required
    case_a, _ = run_scenario(
        orchestrator, "DEMO-A", "all checks pass, human review still mandatory",
        synthetic_detection(0.82),
    )

    # B: low confidence -> warning -> requires review
    run_scenario(
        orchestrator, "DEMO-B", "low confidence becomes a warning and is escalated",
        synthetic_detection(0.30),
    )

    # C: tool failed -> blocked
    run_scenario(
        orchestrator, "DEMO-C", "tool did not complete, so the workflow is blocked",
        synthetic_detection(0.82, status="failed"),
    )

    # Continue case A: evidence -> report -> review -> triage -> communication
    banner("CONTINUING DEMO-A: evidence, report, human review, triage, closure")
    case = case_a

    step("4. Evidence object with provenance; only VALID evidence can reach a report")
    evidence = EvidenceItem(
        evidence_id="EV-A-1",
        case_id=case.case_id,
        evidence_type="model_output",
        source="ich_detection",
        claim="SYNTHETIC TEST INPUT: any-hemorrhage probability 0.82 (not a finding)",
        confidence=0.82,
        supporting_slices=[10, 11, 12],
        provenance=EvidenceProvenance(tool_name="ich_detection", runtime="demo stub, no model"),
    )
    case.add_evidence(evidence)
    print(f"  before verification : {evidence.status.value}")
    evidence.mark_valid("verification_passed")
    print(f"  after verification  : {evidence.status.value}")
    bad = EvidenceItem(evidence_id="EV-A-2", case_id=case.case_id, evidence_type="model_output",
                       source="ich_detection", claim="SYNTHETIC invalid example")
    case.add_evidence(bad)
    bad.invalidate("demo: failed applicability check")
    print(f"  invalidated example : {bad.status.value} (kept for audit, excluded from report)")

    step("5. Structured draft report: built only from governed evidence")
    report = create_structured_draft_report(case, "REP-A-1")
    print(f"  report status        : {report.status.value}")
    print(f"  observations         : {len(report.observations)} (from VALID evidence only)")
    print(f"  evidence references  : {report.evidence_references}")
    print(f"  human review required: {report.human_review_required}")

    step("6. Human review lifecycle: AI report is never overwritten")
    review = HumanReview(review_id="REV-A-1", case_id=case.case_id, report_id=report.report_id)
    case.add_human_review(review)
    lifecycle = ReviewLifecycle(case=case, report=report, review=review)
    lifecycle.start_review()
    lifecycle.record_review_context(["EV-A-1"], ["verification_passed"])
    try:
        lifecycle.reject("reviewer-1", reason="  ")
    except ValueError as error:
        print(f"  reject w/o reason    : refused ({error})")
    lifecycle.accept("reviewer-1", comments=["Demo review of synthetic input"])
    print(f"  review status        : {review.status.value}")
    print(f"  decision             : {review.decision.value} by {review.reviewer_id}")
    try:
        lifecycle.accept("reviewer-2")
    except ValueError as error:
        print(f"  second decision      : refused ({error})")

    step("7. Governed triage proposal needs human approval, then communication and closure")
    triage = TriageRecord(
        triage_id="TRI-A-1", case_id=case.case_id, level=TriageLevel.PRIORITY,
        reason="Workflow proposal from synthetic test input", evidence_ids=["EV-A-1"],
        verification_status="verified", requires_human_approval=True,
    )
    case.add_triage(triage)
    print(f"  approved before human: {triage.approved_by is not None}")
    triage.approve("reviewer-1")
    print(f"  approved by          : {triage.approved_by}")
    comm = CommunicationRecord(
        communication_id="COM-A-1", case_id=case.case_id,
        message="Governed workflow notification (demo)", triage_id=triage.triage_id,
        recipient_role="clinical_reviewer",
    )
    case.add_communication(comm)
    try:
        comm.close()
    except ValueError as error:
        print(f"  close before ack     : refused ({error})")
    comm.acknowledge("reviewer-1")
    comm.close()
    print(f"  communication status : {comm.status.value}")

    banner("DONE: every refusal above is the governance layer doing its job")
    print("Reminder: inputs were synthetic test data. No model ran. No finding was produced.")
    print("Research & Engineering Prototype - Not for clinical diagnosis or treatment.")


if __name__ == "__main__":
    main()
