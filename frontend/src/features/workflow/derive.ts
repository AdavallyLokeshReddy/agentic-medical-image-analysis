import type { ApiError } from "@/api/client";
import type { AsyncStatus } from "@/hooks/useAsync";
import type { Provenance } from "@/lib/provenance";
import type {
  AuditEvent,
  CaseRecord,
  CtData,
  GovernancePlan,
  GovernanceStatus,
  SeriesInfo,
  SeriesList,
} from "@/types/api";
import { formatNumber } from "@/utils/format";
import type { StageId } from "./stages";

interface Slice<T> {
  status: AsyncStatus;
  data: T | null;
  error: ApiError | null;
}

/** Everything the UI actually knows about a case. Nothing is assumed. */
export interface WorkflowFacts {
  caseRecord: Slice<CaseRecord>;
  series: Slice<SeriesList>;
  seriesInfo: Slice<SeriesInfo>;
  ctData: Slice<CtData>;
  plan: Slice<GovernancePlan>;
  govStatus: Slice<GovernanceStatus>;
  audit: Slice<{ available: boolean; reason: string | null; events: AuditEvent[] }>;
}

export interface StageState {
  provenance: Provenance;
  /** One line, derived only from real data (or an honest statement of absence). */
  detail: string;
  /** Extra real facts shown when the stage is expanded. */
  facts: { label: string; value: string }[];
}

type Derived = Record<StageId, StageState>;

function fromSlice<T>(s: Slice<T>, whenWaiting: StageState): StageState | null {
  if (s.status === "loading") return { provenance: "pending", detail: "Running…", facts: [] };
  if (s.status === "error")
    return {
      provenance: "error",
      detail: s.error?.detail ?? s.error?.message ?? "Request failed.",
      facts: s.error ? [{ label: "Technical", value: s.error.technical }] : [],
    };
  if (s.status === "idle") return whenWaiting;
  return null; // success — caller builds the live state
}

const NOT_PRODUCED = "Not produced — requires model execution, which no HTTP route exposes.";

export function deriveStages(f: WorkflowFacts): Derived {
  const uploaded =
    (f.series.data?.series_count ?? 0) > 0 || (f.caseRecord.data?.files_uploaded ?? 0) > 0;

  /* ---- case ---- */
  const caseState: StageState =
    fromSlice(f.caseRecord, { provenance: "ready", detail: "No case selected.", facts: [] }) ?? {
      provenance: "live",
      detail: `${f.caseRecord.data!.case_id} · status “${f.caseRecord.data!.status}”`,
      facts: [
        { label: "Case ID", value: f.caseRecord.data!.case_id },
        { label: "Status", value: f.caseRecord.data!.status },
        { label: "Files uploaded", value: String(f.caseRecord.data!.files_uploaded ?? "—") },
      ],
    };

  /* ---- input ---- */
  const input: StageState =
    fromSlice(f.series, { provenance: "ready", detail: "Awaiting upload.", facts: [] }) ??
    (f.series.data!.series_count > 0
      ? {
          provenance: "live",
          detail: `${f.series.data!.series_count} series · ${f.series.data!.series.reduce((n, s) => n + s.slice_count, 0)} slices received`,
          facts: f.series.data!.series.map((s) => ({
            label: s.series_description || "Series",
            value: `${s.modality} · ${s.slice_count} slices`,
          })),
        }
      : { provenance: "ready", detail: "No DICOM series uploaded yet.", facts: [] });

  /* ---- validation ---- */
  const validation: StageState = !uploaded
    ? { provenance: "ready", detail: "Runs after a series is uploaded.", facts: [] }
    : (fromSlice(f.seriesInfo, { provenance: "ready", detail: "Not run yet.", facts: [] }) ?? (() => {
        const si = f.seriesInfo.data!;
        if (si.series_status === "valid") {
          return {
            provenance: "live" as const,
            detail: `Series valid · ${si.modality} · ${si.slice_count} slices`,
            facts: [
              { label: "Series status", value: si.series_status },
              { label: "Modality", value: si.modality },
              {
                label: "Voxel spacing (mm)",
                value: si.voxel_spacing
                  ? `${formatNumber(si.voxel_spacing.slice_spacing_mm, 2)} × ${formatNumber(si.voxel_spacing.row_spacing_mm, 2)} × ${formatNumber(si.voxel_spacing.column_spacing_mm, 2)}`
                  : "—",
              },
            ],
          };
        }
        return {
          provenance: "error" as const,
          detail:
            si.series_status === "unsupported_modality"
              ? `Unsupported modality: ${si.modality}`
              : (si.validation_error ?? "Series failed validation."),
          facts: [{ label: "Series status", value: si.series_status }],
        };
      })());

  /* ---- preprocessing ---- */
  const preprocessing: StageState = !uploaded
    ? { provenance: "ready", detail: "Runs after a series is uploaded.", facts: [] }
    : (fromSlice(f.ctData, { provenance: "ready", detail: "Not run yet.", facts: [] }) ?? (() => {
        const d = f.ctData.data!;
        return {
          provenance: "live" as const,
          detail: `Volume ${d.volume_shape.join(" × ")} · HU ${formatNumber(d.hu_min, 0)} … ${formatNumber(d.hu_max, 0)}`,
          facts: [
            { label: "Volume shape (z, y, x)", value: d.volume_shape.join(" × ") },
            { label: "HU min / mean / max", value: `${formatNumber(d.hu_min, 0)} / ${formatNumber(d.hu_mean, 1)} / ${formatNumber(d.hu_max, 0)}` },
          ],
        };
      })());

  /* ---- model runtime (never executable over HTTP) ---- */
  const mr = f.govStatus.data?.model_runtime;
  const model: StageState = {
    provenance: "not_exposed",
    detail: "Inference is not exposed over HTTP.",
    facts: mr
      ? [
          { label: "Execution over HTTP", value: mr.execution_exposed_over_http ? "yes" : "no" },
          { label: "PyTorch installed", value: mr.torch_installed ? "yes" : "no" },
          { label: "MONAI installed", value: mr.monai_installed ? "yes" : "no" },
          { label: "skp (head CT model code)", value: mr.skp_installed ? "yes" : "no" },
          { label: "Weights source", value: mr.weights_source },
        ]
      : [],
  };

  /* ---- orchestration (real planning step) ---- */
  const planned = f.plan.data?.plan;
  let orchestration: StageState;
  if (!uploaded) {
    orchestration = { provenance: "ready", detail: "Planning runs after a series is uploaded.", facts: [] };
  } else if (f.plan.status === "loading") {
    orchestration = { provenance: "pending", detail: "Building safety contract and task graph…", facts: [] };
  } else if (f.plan.status === "error") {
    const unavailable = f.plan.error?.status === 503;
    orchestration = {
      provenance: unavailable ? "unavailable" : "error",
      detail: f.plan.error?.detail ?? f.plan.error?.message ?? "Planning failed.",
      facts: f.plan.error ? [{ label: "Technical", value: f.plan.error.technical }] : [],
    };
  } else if (planned) {
    const tasks = planned.task_graph.tasks ?? [];
    orchestration = {
      provenance: "live",
      detail: `Contract + ${tasks.length}-task graph · execution_started = ${String(planned.execution_started)}`,
      facts: [
        { label: "Contract", value: planned.safety_contract.contract_id },
        { label: "Max action tier", value: planned.safety_contract.operation_policy.maximum_action_tier },
        { label: "Approved tools", value: String(planned.safety_contract.approved_tools.length) },
        { label: "Human review required", value: planned.safety_contract.escalation_policy.human_review_required ? "yes" : "no" },
      ],
    };
  } else {
    orchestration = { provenance: "ready", detail: "Not run yet.", facts: [] };
  }

  /* ---- human review: library exists; the plan DOES define the task ---- */
  const reviewTask = planned?.task_graph.tasks?.find((t) => t.task_type === "human_review");
  const review: StageState = {
    provenance: "not_exposed",
    detail: reviewTask
      ? `Defined in plan (${reviewTask.status}); review lifecycle is not exposed.`
      : "Review lifecycle is not exposed over HTTP.",
    facts: reviewTask ? [{ label: "Plan task", value: `${reviewTask.task_id} · ${reviewTask.status}` }] : [],
  };

  /* ---- audit (real read when a database is reachable) ---- */
  let audit: StageState;
  if (f.audit.status === "loading") audit = { provenance: "pending", detail: "Reading audit history…", facts: [] };
  else if (f.audit.status === "error")
    audit = {
      provenance: "error",
      detail: f.audit.error?.message ?? "Audit read failed.",
      facts: f.audit.error ? [{ label: "Technical", value: f.audit.error.technical }] : [],
    };
  else if (f.audit.status === "idle") audit = { provenance: "ready", detail: "Not read yet.", facts: [] };
  else if (!f.audit.data!.available)
    audit = { provenance: "unavailable", detail: f.audit.data!.reason ?? "Audit store unavailable.", facts: [] };
  else
    audit = {
      provenance: "live",
      detail:
        f.audit.data!.events.length === 0
          ? "Database reachable · no audit events recorded for this case."
          : `${f.audit.data!.events.length} audit events`,
      facts: [],
    };

  return {
    case: caseState,
    input,
    validation,
    preprocessing,
    model,
    evidence: { provenance: "not_exposed", detail: NOT_PRODUCED, facts: [] },
    verification: { provenance: "not_exposed", detail: "Verification runs on model evidence; none is produced here.", facts: [] },
    orchestration,
    review,
    report: { provenance: "not_exposed", detail: "Structured reporting is not exposed over HTTP.", facts: [] },
    audit,
  };
}
