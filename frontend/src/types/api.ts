/**
 * Types mirror the REAL FastAPI responses (backend/main.py and
 * backend/governance_api.py). Nothing here describes data the backend cannot
 * produce. Optional fields are optional because the backend omits them in some
 * states (e.g. /series-info for an invalid series).
 */

export interface RootInfo {
  application: string;
  version: string;
  status: string;
}

export interface HealthInfo {
  status: string;
  version: string;
}

/* ---------------------------- cases ---------------------------- */

export interface CaseCreated {
  case_id: string;
  status: string;
}

/** GET /cases/{id}. After a backend restart the registry is empty and the
 *  backend falls back to `{ case_id, status: "existing" }`. */
export interface CaseRecord {
  case_id: string;
  status: string;
  selected_series_uid?: string | null;
  files_uploaded?: number;
}

export interface CaseListItem {
  case_id: string;
  status: string;
  series_count: number;
  file_count: number;
  /** Filesystem modification time of the case folder (ISO-8601, UTC). */
  updated_at: string;
  in_memory_registry: boolean;
}

export interface CaseList {
  count: number;
  cases: CaseListItem[];
}

export interface UploadResult {
  case_id: string;
  status: string;
  uploaded_count: number;
  series_file_count: number;
  study_instance_uid: string;
  series_instance_uid: string;
  modality: string;
  files: string[];
}

/* ---------------------------- series / image ---------------------------- */

export interface SeriesSummary {
  series_instance_uid: string;
  study_instance_uid: string;
  modality: string;
  series_description: string;
  slice_count: number;
  selected: boolean;
}

export interface SeriesList {
  case_id: string;
  series_count: number;
  series: SeriesSummary[];
}

export interface ImageInfo {
  case_id: string;
  series_instance_uid: string;
  modality: string;
  rows: number;
  columns: number;
  slice_count: number;
  pixel_data_available: boolean;
  min_pixel_value: number;
  max_pixel_value: number;
  data_type: string;
}

export interface CtData {
  case_id: string;
  series_instance_uid: string;
  modality: string;
  volume_shape: number[];
  hu_min: number;
  hu_max: number;
  hu_mean: number;
}

export type SeriesStatus = "valid" | "invalid" | "unsupported_modality";

export interface SeriesInfo {
  case_id: string;
  modality: string;
  study_instance_uid: string;
  series_instance_uid: string;
  slice_count: number;
  series_status: SeriesStatus;
  validation_error?: string;
  rows?: number;
  columns?: number;
  volume_shape?: number[];
  voxel_spacing?: {
    slice_spacing_mm: number;
    row_spacing_mm: number;
    column_spacing_mm: number;
  };
  hu_min?: number;
  hu_max?: number;
  hu_mean?: number;
}

/** /preview returns a PNG; slice metadata travels in response headers. */
export interface PreviewResult {
  /** PNG as a data URL (no object-URL lifecycle to manage). */
  src: string;
  sliceIndex: number | null;
  sliceCount: number | null;
  seriesUid: string | null;
  bytes: number;
}

/* ---------------------------- governance (read-only) ---------------------------- */

export type HttpExposure = "yes" | "partial" | "plan_only" | "if_database" | "no";

export interface LibraryModule {
  module: string;
  label: string;
  http_exposed: HttpExposure;
  importable: boolean;
}

export interface GovernanceStatus {
  notice: string;
  tool_registry: { loaded: boolean; tool_count: number; error: string | null };
  model_runtime: {
    skp_installed: boolean;
    model_repo: string;
    weights_source: string;
    torch_installed: boolean;
    monai_installed: boolean;
    execution_exposed_over_http: boolean;
  };
  persistence: { configured: boolean; reachable: boolean | null; error: string | null };
  library_modules: LibraryModule[];
}

export interface ToolDescriptor {
  name: string;
  description: string;
  supported_modalities: string[];
  supported_body_regions: string[];
  intended_use: string;
  expected_inputs: string[];
  output_schema: Record<string, unknown> | null;
  validation_population: string;
  exclusions: string[];
  version: string;
  compute_requirements: Record<string, unknown>;
}

export interface GovernanceTools {
  available: boolean;
  reason: string | null;
  tools: ToolDescriptor[];
}

export interface TaskNodeDto {
  task_id: string;
  task_type: string;
  description: string;
  status: string;
  dependencies: string[];
  permitted_tools: string[];
  preconditions: string[];
  stopping_conditions: string[];
  verification_required: boolean;
  [key: string]: unknown;
}

export interface SafetyContractDto {
  contract_id: string;
  approved_tools: string[];
  task_preconditions: Record<string, string[]>;
  data_policy: {
    allowed_modalities: string[];
    allowed_body_regions: (string | null)[];
    required_data: string[];
  };
  operation_policy: { allowed_operations: string[]; maximum_action_tier: string };
  uncertainty_policy: {
    minimum_confidence: number;
    require_verification: boolean;
    abstain_on_missing_evidence: boolean;
    abstain_on_verification_failure: boolean;
  };
  escalation_policy: { escalation_paths: string[]; human_review_required: boolean };
  resource_policy: {
    maximum_retries: number;
    timeout_seconds: number;
    maximum_concurrent_tools: number;
  };
  [key: string]: unknown;
}

export interface OrchestratorPlan {
  case: {
    case_id: string;
    modality: string;
    body_region: string | null;
    clinical_question: string | null;
    image_count: number;
    status: string;
  };
  available_tools: Partial<ToolDescriptor>[];
  safety_contract: SafetyContractDto;
  task_graph: { tasks?: TaskNodeDto[]; [key: string]: unknown };
  ready_tasks: TaskNodeDto[];
  selected_tools: string[];
  execution_started: boolean;
}

export interface GovernancePlan {
  notice: string;
  source: string;
  inputs: {
    body_region: string;
    body_region_source: string;
    clinical_question: string | null;
    modality: string;
    modality_source: string;
  };
  plan: OrchestratorPlan;
}

export interface AuditEvent {
  event_id: string;
  timestamp: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  metadata: Record<string, unknown> | null;
}

export interface GovernanceAudit {
  available: boolean;
  reason: string | null;
  events: AuditEvent[];
}
