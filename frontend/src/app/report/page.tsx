"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type ReactNode } from "react";
import { Icon } from "@/components/ui/Icon";
import { Panel } from "@/components/ui/Panel";
import { ProvenanceBadge } from "@/components/ui/ProvenanceBadge";
import { StateBlock } from "@/components/ui/StateBlock";
import { CasePicker } from "@/features/cases/CasePicker";
import { useCaseData } from "@/hooks/useCaseData";
import { NOTICE_LONG } from "@/lib/config";
import type { Provenance } from "@/lib/provenance";
import { formatDateTime, formatNumber, shortUid } from "@/utils/format";

const PLAN_DEFAULTS = { bodyRegion: "head", clinicalQuestion: "" };

function Section({
  n,
  title,
  kind,
  badge,
  children,
}: {
  n: number;
  title: string;
  kind: Provenance;
  badge?: string;
  children: ReactNode;
}) {
  return (
    <section className="break-inside-avoid border-t border-line px-6 py-5 first:border-t-0">
      <header className="mb-3 flex items-center justify-between gap-3">
        <h2 className="flex items-baseline gap-2.5 text-[15px] font-semibold">
          <span className="num text-xs text-faint">{String(n).padStart(2, "0")}</span>
          {title}
        </h2>
        <ProvenanceBadge kind={kind} label={badge} />
      </header>
      {children}
    </section>
  );
}

function Rows({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid gap-x-8 sm:grid-cols-2">
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-baseline justify-between gap-4 border-b border-line py-1.5 text-[13px]">
          <dt className="shrink-0 text-faint">{k}</dt>
          <dd className="num min-w-0 break-words text-right">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function NotProduced({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-line2 bg-white/[0.02] px-3.5 py-3 text-[13px] leading-relaxed text-dim">
      {children}
    </p>
  );
}

function Report({ caseId }: { caseId: string }) {
  const data = useCaseData(caseId, PLAN_DEFAULTS, { skipPreview: true });
  const [generatedAt] = useState(() => new Date().toISOString());
  const rec = data.caseRecord.data;
  const sel = data.series.data?.series.find((s) => s.selected) ?? data.series.data?.series[0];
  const si = data.seriesInfo.data;
  const info = data.imageInfo.data;
  const ct = data.ctData.data;
  const plan = data.plan.data?.plan;
  const audit = data.audit.data;

  if (data.caseRecord.status === "error") {
    return (
      <Panel>
        <StateBlock
          kind={data.caseRecord.error?.status === 404 ? "empty" : "error"}
          title={data.caseRecord.error?.status === 404 ? `Case ${caseId} not found` : "Could not load the case"}
          error={data.caseRecord.error?.status === 404 ? null : data.caseRecord.error}
          onRetry={data.caseRecord.reload}
        >
          <Link href="/cases/" className="btn mt-1">
            Back to cases
          </Link>
        </StateBlock>
      </Panel>
    );
  }

  const loading = data.caseRecord.status === "loading" || (data.hasSeries && (data.seriesInfo.status === "loading" || data.plan.status === "loading"));

  return (
    <>
      <div className="no-print mb-4 flex flex-wrap items-center justify-between gap-3">
        <Link href={`/workspace/?case=${encodeURIComponent(caseId)}`} className="btn">
          <Icon name="arrowRight" size={14} className="rotate-180" /> Back to workspace
        </Link>
        <button type="button" className="btn btn-primary" onClick={() => window.print()} disabled={loading}>
          <Icon name="printer" size={14} /> Print / save as PDF
        </button>
      </div>

      <article className="panel print-sheet mx-auto max-w-4xl overflow-hidden" aria-busy={loading}>
        <header className="px-6 py-6">
          <p className="panel-title !text-accent">Case workflow record</p>
          <h1 className="num mt-1 text-2xl font-semibold tracking-tight">{caseId}</h1>
          <p className="mt-1 text-[13px] text-dim">
            Assembled from what the backend reports for this case. Generated {formatDateTime(generatedAt)} (browser clock).
          </p>
          <p className="mt-3 rounded-lg border border-warn/30 bg-warn/[0.07] px-3 py-2 text-xs font-medium uppercase tracking-wider text-warn">
            Research &amp; engineering prototype — not for clinical diagnosis or treatment
          </p>
        </header>

        <Section n={1} title="Case" kind={rec ? "live" : "pending"}>
          {rec && (
            <Rows
              rows={[
                ["Case ID", rec.case_id],
                ["Status", rec.status],
                ["Files uploaded", rec.files_uploaded ?? "—"],
                ["Series in case", data.series.data?.series_count ?? "—"],
              ]}
            />
          )}
        </Section>

        <Section n={2} title="Imaging input" kind={sel ? "live" : data.series.status === "loading" ? "pending" : "ready"} badge={sel ? undefined : "No input"}>
          {sel ? (
            <Rows
              rows={[
                ["Modality", sel.modality],
                ["Series description", sel.series_description || "—"],
                ["Slices", sel.slice_count],
                ["Series UID", <span key="u" title={sel.series_instance_uid}>{shortUid(sel.series_instance_uid, 10)}</span>],
                ["Study UID", <span key="s" title={sel.study_instance_uid}>{shortUid(sel.study_instance_uid, 10)}</span>],
                ["Matrix", info ? `${info.columns} × ${info.rows}` : "—"],
              ]}
            />
          ) : (
            <NotProduced>No DICOM series has been uploaded to this case.</NotProduced>
          )}
        </Section>

        <Section
          n={3}
          title="Validation & preprocessing"
          kind={si ? (si.series_status === "valid" ? "live" : "error") : data.hasSeries ? "pending" : "ready"}
          badge={si && si.series_status !== "valid" ? si.series_status : undefined}
        >
          {si ? (
            <Rows
              rows={[
                ["Series status", si.series_status],
                ["Validation message", si.validation_error ?? "none"],
                [
                  "Voxel spacing (mm)",
                  si.voxel_spacing
                    ? `${formatNumber(si.voxel_spacing.slice_spacing_mm, 2)} × ${formatNumber(si.voxel_spacing.row_spacing_mm, 2)} × ${formatNumber(si.voxel_spacing.column_spacing_mm, 2)}`
                    : "—",
                ],
                ["Volume (z·y·x)", ct ? ct.volume_shape.join(" × ") : (si.volume_shape?.join(" × ") ?? "—")],
                ["HU min / mean / max", ct ? `${formatNumber(ct.hu_min, 0)} / ${formatNumber(ct.hu_mean, 0)} / ${formatNumber(ct.hu_max, 0)}` : "—"],
              ]}
            />
          ) : (
            <NotProduced>Runs once a series is uploaded.</NotProduced>
          )}
        </Section>

        <Section n={4} title="Governance plan" kind={plan ? "live" : data.plan.status === "error" ? "unavailable" : "ready"} badge={plan ? "Planned, not executed" : undefined}>
          {plan ? (
            <>
              <Rows
                rows={[
                  ["Safety contract", plan.safety_contract.contract_id],
                  ["Approved tools", plan.safety_contract.approved_tools.join(", ") || "none"],
                  ["Maximum action tier", plan.safety_contract.operation_policy.maximum_action_tier],
                  ["Verification required", plan.safety_contract.uncertainty_policy.require_verification ? "yes" : "no"],
                  ["Human review required", plan.safety_contract.escalation_policy.human_review_required ? "yes" : "no"],
                  ["execution_started", String(plan.execution_started)],
                ]}
              />
              <ol className="mt-4 space-y-1.5 text-[13px]">
                {(plan.task_graph.tasks ?? []).map((t, i) => (
                  <li key={t.task_id} className="flex items-baseline gap-3">
                    <span className="num w-5 text-right text-xs text-faint">{i + 1}</span>
                    <span className="capitalize">{t.task_type.replace(/_/g, " ").replace(/\bich\b/gi, "ICH")}</span>
                    <span className="num text-xs text-faint">{t.status}{t.verification_required ? " · verification required" : ""}</span>
                  </li>
                ))}
              </ol>
            </>
          ) : data.plan.status === "error" ? (
            <NotProduced>Orchestrator planning is unavailable: {data.plan.error?.detail ?? data.plan.error?.message}</NotProduced>
          ) : (
            <NotProduced>Planning runs after a series is uploaded.</NotProduced>
          )}
        </Section>

        <Section n={5} title="Evidence, verification & findings" kind="not_exposed">
          <NotProduced>
            <strong className="text-ink">Not produced.</strong> Evidence, verification results and findings come from running a
            model, which no HTTP route exposes in this deployment (the external model code and weights are not part of the
            repository). No finding, probability or diagnosis is stated or implied by this record.
          </NotProduced>
        </Section>

        <Section n={6} title="Human review" kind="not_exposed">
          <NotProduced>
            The review lifecycle is implemented as library code and is not exposed over HTTP. No review decision exists for this
            case
            {plan?.task_graph.tasks?.some((t) => t.task_type === "human_review")
              ? "; the plan defines a human-review task that is triggered only when verification requires it."
              : "."}
          </NotProduced>
        </Section>

        <Section
          n={7}
          title="Audit trail"
          kind={audit?.available ? "live" : data.audit.status === "loading" ? "pending" : "unavailable"}
        >
          {audit?.available ? (
            audit.events.length === 0 ? (
              <NotProduced>Database reachable; no audit events are recorded for this case.</NotProduced>
            ) : (
              <ol className="space-y-1 text-[13px]">
                {audit.events.map((e) => (
                  <li key={e.event_id} className="num">
                    {formatDateTime(e.timestamp)} · {e.actor_type} · {e.action} · {e.entity_type}
                  </li>
                ))}
              </ol>
            )
          ) : (
            <NotProduced>{audit?.reason ?? "Audit information is unavailable."}</NotProduced>
          )}
        </Section>

        <footer className="border-t border-line px-6 py-4 text-[11.5px] leading-relaxed text-faint">{NOTICE_LONG}</footer>
      </article>
    </>
  );
}

function ReportRoute() {
  const caseId = useSearchParams().get("case");
  if (!caseId) return <CasePicker basePath="/report/" purpose="to summarise" />;
  return <Report key={caseId} caseId={caseId} />;
}

export default function ReportPage() {
  return (
    <Suspense fallback={<StateBlock kind="loading" title="Loading report…" />}>
      <ReportRoute />
    </Suspense>
  );
}
