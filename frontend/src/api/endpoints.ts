/**
 * One typed function per REAL backend route. If a route is not here, the
 * backend does not expose it — the UI must show a "not exposed" state rather
 * than invent a call.
 */
import { blobToDataUrl, requestBlob, requestJson, uploadFiles, type RequestOptions } from "./client";
import type {
  CaseCreated,
  CaseList,
  CaseRecord,
  CtData,
  GovernanceAudit,
  GovernancePlan,
  GovernanceStatus,
  GovernanceTools,
  HealthInfo,
  ImageInfo,
  PreviewResult,
  RootInfo,
  SeriesInfo,
  SeriesList,
  UploadResult,
} from "@/types/api";

type Opts = Pick<RequestOptions, "signal" | "label" | "timeoutMs" | "silent">;

const enc = encodeURIComponent;

export const api = {
  /* ---- service ---- */
  root: (o?: Opts) => requestJson<RootInfo>("/", { label: "Backend root", ...o }),
  health: (o?: Opts) => requestJson<HealthInfo>("/health", { label: "Health check", timeoutMs: 8_000, ...o }),

  /* ---- cases ---- */
  createCase: (o?: Opts) => requestJson<CaseCreated>("/cases", { method: "POST", label: "Case created", ...o }),
  listCases: (o?: Opts) => requestJson<CaseList>("/cases", { label: "Case list", ...o }),
  getCase: (id: string, o?: Opts) => requestJson<CaseRecord>(`/cases/${enc(id)}`, { label: "Case record", ...o }),

  uploadSeries: (
    id: string,
    files: File[],
    onProgress?: (loaded: number, total: number) => void,
    signal?: AbortSignal,
  ) => uploadFiles<UploadResult>(`/cases/${enc(id)}/upload`, files, onProgress, signal),

  /* ---- imaging ---- */
  listSeries: (id: string, o?: Opts) => requestJson<SeriesList>(`/cases/${enc(id)}/series`, { label: "Series listing", ...o }),
  imageInfo: (id: string, o?: Opts) => requestJson<ImageInfo>(`/cases/${enc(id)}/image-info`, { label: "Image info", ...o }),
  seriesInfo: (id: string, o?: Opts) =>
    requestJson<SeriesInfo>(`/cases/${enc(id)}/series-info`, { label: "Series validation", timeoutMs: 120_000, ...o }),
  ctData: (id: string, o?: Opts) =>
    requestJson<CtData>(`/cases/${enc(id)}/ct-data`, { label: "Preprocessing", timeoutMs: 120_000, ...o }),

  /** Returns the PNG as a data URL plus the slice metadata from the response headers. */
  preview: async (id: string, o?: Opts): Promise<PreviewResult> => {
    const { blob, headers } = await requestBlob(`/cases/${enc(id)}/preview`, {
      label: "CT preview",
      timeoutMs: 120_000,
      ...o,
    });
    const num = (h: string) => {
      const v = headers.get(h);
      return v !== null && v !== "" && !Number.isNaN(Number(v)) ? Number(v) : null;
    };
    return {
      src: await blobToDataUrl(blob),
      sliceIndex: num("X-Slice-Index"),
      sliceCount: num("X-Slice-Count"),
      seriesUid: headers.get("X-Series-Instance-UID"),
      bytes: blob.size,
    };
  },

  /* ---- governance (read-only router) ---- */
  governanceStatus: (o?: Opts) =>
    requestJson<GovernanceStatus>("/governance/status", { label: "Governance status", ...o }),
  governanceTools: (o?: Opts) => requestJson<GovernanceTools>("/governance/tools", { label: "Tool registry", ...o }),
  governancePlan: (id: string, bodyRegion: string, clinicalQuestion?: string, o?: Opts) =>
    requestJson<GovernancePlan>(`/governance/cases/${enc(id)}/plan`, {
      label: "Orchestrator plan",
      query: { body_region: bodyRegion, clinical_question: clinicalQuestion },
      ...o,
    }),
  governanceAudit: (id: string, o?: Opts) =>
    requestJson<GovernanceAudit>(`/governance/cases/${enc(id)}/audit`, { label: "Audit read", ...o }),
};
