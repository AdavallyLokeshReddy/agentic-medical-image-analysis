"use client";

import { useCallback } from "react";
import { api } from "@/api/endpoints";
import { useAsync, type AsyncResult } from "@/hooks/useAsync";
import type {
  CaseRecord,
  CtData,
  GovernanceAudit,
  GovernancePlan,
  GovernanceStatus,
  ImageInfo,
  PreviewResult,
  SeriesInfo,
  SeriesList,
} from "@/types/api";

export interface PlanInputs {
  bodyRegion: string;
  clinicalQuestion: string;
}

export interface CaseData {
  caseRecord: AsyncResult<CaseRecord>;
  series: AsyncResult<SeriesList>;
  seriesInfo: AsyncResult<SeriesInfo>;
  imageInfo: AsyncResult<ImageInfo>;
  ctData: AsyncResult<CtData>;
  preview: AsyncResult<PreviewResult>;
  plan: AsyncResult<GovernancePlan>;
  govStatus: AsyncResult<GovernanceStatus>;
  audit: AsyncResult<GovernanceAudit>;
  /** True once the backend reports at least one DICOM series for this case. */
  hasSeries: boolean;
  /** Re-read everything (used after an upload). */
  refreshAll: () => void;
}

/**
 * Loads every REAL backend slice for one case.
 *
 * Gating matters: several backend routes create the case folder on demand, so
 * nothing but GET /cases/{id} (which 404s for unknown ids) is called until the
 * case is confirmed to exist. Imaging routes wait for a series to exist; the
 * orchestrator plan waits for a series as well.
 */
export function useCaseData(
  caseId: string | null,
  planInputs: PlanInputs,
  options: { skipPreview?: boolean } = {},
): CaseData {
  const has = caseId !== null;

  const caseRecord = useAsync((signal) => api.getCase(caseId!, { signal }), [caseId], { enabled: has });
  const known = caseRecord.status === "success";

  const series = useAsync((signal) => api.listSeries(caseId!, { signal }), [caseId], { enabled: known });
  const hasSeries = (series.data?.series_count ?? 0) > 0;
  // Changes whenever the uploaded imaging changes, so imaging routes re-run after a re-upload.
  const sig = series.data?.series.map((s) => `${s.series_instance_uid}:${s.slice_count}`).join("|") ?? "";

  const seriesInfo = useAsync((signal) => api.seriesInfo(caseId!, { signal }), [caseId, sig], {
    enabled: hasSeries,
  });
  const imageInfo = useAsync((signal) => api.imageInfo(caseId!, { signal }), [caseId, sig], {
    enabled: hasSeries,
  });
  const ctData = useAsync((signal) => api.ctData(caseId!, { signal }), [caseId, sig], {
    enabled: hasSeries,
  });
  const preview = useAsync((signal) => api.preview(caseId!, { signal }), [caseId, sig], {
    enabled: hasSeries && !options.skipPreview,
  });

  const plan = useAsync(
    (signal) =>
      api.governancePlan(caseId!, planInputs.bodyRegion, planInputs.clinicalQuestion || undefined, { signal }),
    [caseId, sig, planInputs.bodyRegion, planInputs.clinicalQuestion],
    { enabled: hasSeries },
  );

  const govStatus = useAsync((signal) => api.governanceStatus({ signal }), [], { enabled: true });
  const audit = useAsync((signal) => api.governanceAudit(caseId!, { signal }), [caseId], { enabled: known });

  const reloadCase = caseRecord.reload;
  const reloadSeries = series.reload;
  const reloadAudit = audit.reload;
  const refreshAll = useCallback(() => {
    reloadCase();
    reloadSeries();
    reloadAudit();
  }, [reloadCase, reloadSeries, reloadAudit]);

  return {
    caseRecord,
    series,
    seriesInfo,
    imageInfo,
    ctData,
    preview,
    plan,
    govStatus,
    audit,
    hasSeries,
    refreshAll,
  };
}
