"""
Analysis job layer.

Connects the existing governed workflow (CaseState, orchestrator, Safety Contract, Tool Registry,
verification, evidence, structured report, human review) to real model execution behind an
asynchronous job API.

Rules this package keeps:
  * planning and execution stay separate; the orchestrator only plans,
  * a tool runs only if the orchestrator discovered it AND the Safety Contract approved it AND the
    execution adapter declares it executable,
  * verification, evidence, report and review are produced by the existing governance code, not here,
  * nothing in a GET route ever starts or advances an analysis.

Research & Engineering Prototype - Not for clinical diagnosis or treatment.
"""
