import type { IconName } from "@/components/ui/Icon";

export type StageId =
  | "case"
  | "input"
  | "validation"
  | "preprocessing"
  | "model"
  | "evidence"
  | "verification"
  | "orchestration"
  | "review"
  | "report"
  | "audit";

/** The architecture's four layers. The model is ONE node inside a larger system. */
export type Layer = "input" | "model" | "governance" | "output";

export interface StageDef {
  id: StageId;
  label: string;
  layer: Layer;
  icon: IconName;
  /** What this stage is, in the architecture (static explanation). */
  description: string;
  /** What backs it in the repository today. */
  backing: string;
}

export const LAYERS: Record<Layer, { label: string; color: string }> = {
  input: { label: "Input & preparation", color: "#5ad1e6" },
  model: { label: "Model runtime", color: "#a595ff" },
  governance: { label: "Evidence & governance", color: "#f5b94a" },
  output: { label: "Output & accountability", color: "#4ade9f" },
};

export const STAGES: StageDef[] = [
  {
    id: "case",
    label: "Case",
    layer: "input",
    icon: "file",
    description: "A case is the unit of work: identity, status, and the series attached to it.",
    backing: "POST /cases · GET /cases/{id}",
  },
  {
    id: "input",
    label: "Input",
    layer: "input",
    icon: "upload",
    description: "DICOM files are received and grouped into a single CT series.",
    backing: "POST /cases/{id}/upload · GET /cases/{id}/series",
  },
  {
    id: "validation",
    label: "Validation",
    layer: "input",
    icon: "shield",
    description: "Modality, study/series identity, matching dimensions and pixel spacing are checked before anything else runs.",
    backing: "GET /cases/{id}/series-info",
  },
  {
    id: "preprocessing",
    label: "Preprocessing",
    layer: "input",
    icon: "layers",
    description: "Slices are ordered anatomically and converted to a Hounsfield-unit volume.",
    backing: "GET /cases/{id}/ct-data",
  },
  {
    id: "model",
    label: "Model runtime",
    layer: "model",
    icon: "cube",
    description: "A registered AI tool runs inference. It is one governed component, not the system.",
    backing: "backend/model_runtime · backend/tools (library only)",
  },
  {
    id: "evidence",
    label: "Evidence",
    layer: "governance",
    icon: "eye",
    description: "Model output becomes a typed evidence object with provenance, never a bare prediction.",
    backing: "agent.case_state.EvidenceItem (library only)",
  },
  {
    id: "verification",
    label: "Verification",
    layer: "governance",
    icon: "check",
    description: "Technical, applicability and cross-output checks decide whether evidence can be trusted.",
    backing: "backend/verification (library only)",
  },
  {
    id: "orchestration",
    label: "Safety & orchestration",
    layer: "governance",
    icon: "shield",
    description: "A case-specific safety contract bounds which tools, operations and action tiers are permitted; a task graph sequences the work.",
    backing: "GET /governance/cases/{id}/plan",
  },
  {
    id: "review",
    label: "Human review",
    layer: "governance",
    icon: "user",
    description: "When verification or policy requires it, the case escalates to a human who accepts, modifies or rejects.",
    backing: "agent.human_review · review_lifecycle (library only)",
  },
  {
    id: "report",
    label: "Report",
    layer: "output",
    icon: "file",
    description: "A structured report assembled from evidence, verification and review state.",
    backing: "backend/reporting (library only)",
  },
  {
    id: "audit",
    label: "Audit",
    layer: "output",
    icon: "database",
    description: "An append-only record of governed actions, persisted in PostgreSQL.",
    backing: "GET /governance/cases/{id}/audit (needs PostgreSQL)",
  },
];

export const STAGE_BY_ID = Object.fromEntries(STAGES.map((s) => [s.id, s])) as Record<StageId, StageDef>;
