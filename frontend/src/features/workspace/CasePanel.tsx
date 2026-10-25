"use client";

import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { Field, Panel, Skeleton } from "@/components/ui/Panel";
import { ProvenanceBadge } from "@/components/ui/ProvenanceBadge";
import { StateBlock } from "@/components/ui/StateBlock";
import type { CaseData } from "@/hooks/useCaseData";
import { formatNumber, shortUid } from "@/utils/format";

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-3">
      <p className="panel-title mb-1 !text-[10px]">{title}</p>
      <dl className="divide-y divide-line">{children}</dl>
    </div>
  );
}

/** Case context. Every value is read from the backend; nothing is inferred. */
export function CasePanel({ caseId, data }: { caseId: string; data: CaseData }) {
  const { caseRecord, series, imageInfo, seriesInfo, ctData } = data;
  const rec = caseRecord.data;
  const info = imageInfo.data;
  const si = seriesInfo.data;
  const ct = ctData.data;
  const sel = series.data?.series.find((s) => s.selected) ?? series.data?.series[0];

  return (
    <Panel
      title="Case"
      right={
        caseRecord.status === "success" ? (
          <ProvenanceBadge kind="live" />
        ) : caseRecord.status === "loading" ? (
          <ProvenanceBadge kind="pending" />
        ) : null
      }
    >
      {caseRecord.status === "error" ? (
        <StateBlock
          compact
          kind={caseRecord.error?.status === 404 ? "empty" : "error"}
          title={caseRecord.error?.status === 404 ? `Case ${caseId} not found` : "Could not load the case"}
          message={caseRecord.error?.status === 404 ? "It may have been removed, or the backend storage was reset." : undefined}
          error={caseRecord.error?.status === 404 ? null : caseRecord.error}
          onRetry={caseRecord.reload}
        >
          <Link href="/cases/" className="btn mt-1">
            Back to cases
          </Link>
        </StateBlock>
      ) : !rec ? (
        <div className="space-y-2 p-4">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      ) : (
        <div className="divide-y divide-line">
          <Group title="Identity">
            <Field label="Case ID">{rec.case_id}</Field>
            <Field label="Status">{rec.status}</Field>
            <Field label="Files uploaded">{rec.files_uploaded ?? "—"}</Field>
          </Group>

          <Group title="Series">
            {series.status === "loading" && !series.data ? (
              <Skeleton className="my-2 h-4 w-full" />
            ) : sel ? (
              <>
                <Field label="Modality">{sel.modality}</Field>
                <Field label="Description" mono={false} title={sel.series_description}>
                  {sel.series_description || "—"}
                </Field>
                <Field label="Slices">{sel.slice_count}</Field>
                <Field label="Series UID" title={sel.series_instance_uid}>
                  {shortUid(sel.series_instance_uid, 6)}
                </Field>
                <Field label="Series in case">{series.data?.series_count}</Field>
              </>
            ) : (
              <p className="flex items-center gap-2 py-2 text-xs text-faint">
                <Icon name="layers" size={13} /> No series uploaded yet.
              </p>
            )}
          </Group>

          {sel && (
            <Group title="Image & geometry">
              {imageInfo.status === "loading" && !info ? (
                <Skeleton className="my-2 h-4 w-full" />
              ) : info ? (
                <>
                  <Field label="Matrix">
                    {info.columns} × {info.rows}
                  </Field>
                  <Field label="Stored type">{info.data_type}</Field>
                  <Field label="Raw pixel range">
                    {formatNumber(info.min_pixel_value, 0)} … {formatNumber(info.max_pixel_value, 0)}
                  </Field>
                </>
              ) : null}
              {si?.voxel_spacing && (
                <Field label="Voxel (mm)" title="slice × row × column spacing">
                  {formatNumber(si.voxel_spacing.slice_spacing_mm, 2)} × {formatNumber(si.voxel_spacing.row_spacing_mm, 2)} ×{" "}
                  {formatNumber(si.voxel_spacing.column_spacing_mm, 2)}
                </Field>
              )}
              {ct && (
                <>
                  <Field label="Volume (z·y·x)">{ct.volume_shape.join(" × ")}</Field>
                  <Field label="HU range">
                    {formatNumber(ct.hu_min, 0)} … {formatNumber(ct.hu_max, 0)}
                  </Field>
                  <Field label="HU mean">{formatNumber(ct.hu_mean, 1)}</Field>
                </>
              )}
              {si && (
                <Field label="Validation">
                  <span className={si.series_status === "valid" ? "text-live" : "text-danger"}>{si.series_status}</span>
                </Field>
              )}
            </Group>
          )}
        </div>
      )}
    </Panel>
  );
}
