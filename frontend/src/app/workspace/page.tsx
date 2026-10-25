"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { StateBlock } from "@/components/ui/StateBlock";
import { CasePicker } from "@/features/cases/CasePicker";
import { CtViewer } from "@/features/viewer/CtViewer";
import { deriveStages } from "@/features/workflow/derive";
import { WorkflowPipeline } from "@/features/workflow/WorkflowPipeline";
import { ActivityLog } from "@/features/workspace/ActivityLog";
import { AuditTimeline } from "@/features/workspace/AuditView";
import { CasePanel } from "@/features/workspace/CasePanel";
import { PlanInputsPanel } from "@/features/workspace/PlanInputs";
import { PlanView } from "@/features/workspace/PlanView";
import { StageSummary } from "@/features/workspace/StageSummary";
import { UploadPanel, type UploadProgress } from "@/features/workspace/UploadPanel";
import { useCaseData, type PlanInputs } from "@/hooks/useCaseData";
import { rememberCase } from "@/lib/rememberedCases";
import { cn } from "@/utils/format";

type DockTab = "plan" | "activity" | "audit";
const TABS: { id: DockTab; label: string }[] = [
  { id: "plan", label: "Orchestrator plan" },
  { id: "activity", label: "Workflow activity" },
  { id: "audit", label: "Audit trail" },
];

function Workspace({ caseId }: { caseId: string }) {
  const [planInputs, setPlanInputs] = useState<PlanInputs>({ bodyRegion: "head", clinicalQuestion: "" });
  const [tab, setTab] = useState<DockTab>("plan");
  const [upload, setUpload] = useState<UploadProgress>({ phase: "idle", fraction: 0 });
  const data = useCaseData(caseId, planInputs);

  useEffect(() => {
    rememberCase(caseId);
  }, [caseId]);

  const states = useMemo(() => {
    const s = deriveStages({
      caseRecord: data.caseRecord,
      series: data.series,
      seriesInfo: data.seriesInfo,
      ctData: data.ctData,
      plan: data.plan,
      govStatus: data.govStatus,
      audit: data.audit,
    });
    if (upload.phase === "uploading" || upload.phase === "processing") {
      return {
        ...s,
        input: {
          provenance: "pending" as const,
          detail:
            upload.phase === "uploading"
              ? `Uploading DICOM series… ${Math.round(upload.fraction * 100)}%`
              : "Validating imaging series…",
          facts: [],
        },
      };
    }
    return s;
  }, [data.caseRecord, data.series, data.seriesInfo, data.ctData, data.plan, data.govStatus, data.audit, upload]);

  const onProgress = useCallback((p: UploadProgress) => setUpload(p), []);
  const caseMissing = data.caseRecord.status === "error" && data.caseRecord.error?.status === 404;

  return (
    <div>
      <PageHeader
        eyebrow="Analysis workspace"
        title={<span className="num">{caseId}</span>}
        description="Case context, imaging and the governed workflow in one place. Every value shown is read from the backend; stages that no HTTP route exposes are labelled as such."
        actions={
          <>
            <Link href="/cases/" className="btn">
              <Icon name="list" size={14} /> Cases
            </Link>
            <Link href={`/report/?case=${encodeURIComponent(caseId)}`} className="btn btn-primary">
              <Icon name="file" size={14} /> Case report
            </Link>
          </>
        }
      />

      {caseMissing ? (
        <Panel>
          <StateBlock
            kind="empty"
            title={`Case ${caseId} not found`}
            message="It may never have existed, or the backend’s storage was reset."
          >
            <Link href="/cases/" className="btn btn-primary mt-1">
              Choose another case
            </Link>
          </StateBlock>
        </Panel>
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[310px_minmax(0,1fr)_370px]">
          {/* LEFT: case, input, inputs */}
          <div className="space-y-4">
            <CasePanel caseId={caseId} data={data} />
            <UploadPanel caseId={caseId} onUploaded={data.refreshAll} onProgress={onProgress} />
          </div>

          {/* CENTER: viewer */}
          <div className="min-w-0 lg:sticky lg:top-28 lg:h-[calc(100vh-8rem)] lg:min-h-[560px] lg:max-h-[820px] [&>div]:h-full">
            <CtViewer
              caseId={caseId}
              hasSeries={data.hasSeries}
              preview={data.preview}
              imageInfo={data.imageInfo}
              seriesInfo={data.seriesInfo}
            />
          </div>

          {/* RIGHT: workflow */}
          <Panel
            title="Workflow · agent operations"
            className="lg:col-span-2 xl:col-span-1"
            bodyClassName="overflow-hidden"
          >
            <StageSummary states={states} />
            <div className="p-3">
              <WorkflowPipeline states={states} />
            </div>
          </Panel>
        </div>
      )}

      {/* BOTTOM: dock */}
      {!caseMissing && (
        <Panel
          className="mt-4"
          title={
            <span role="tablist" aria-label="Workspace detail" className="flex items-center gap-1 normal-case tracking-normal">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  role="tab"
                  type="button"
                  id={`tab-${t.id}`}
                  aria-selected={tab === t.id}
                  aria-controls={`panel-${t.id}`}
                  onClick={() => setTab(t.id)}
                  className={cn(
                    "rounded-md px-2.5 py-1 font-sans text-[12.5px] transition-colors",
                    tab === t.id ? "bg-white/[0.09] text-ink" : "text-dim hover:text-ink",
                  )}
                >
                  {t.label}
                </button>
              ))}
            </span>
          }
        >
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === "plan" && (
              <>
                <PlanInputsPanel value={planInputs} onApply={setPlanInputs} disabled={!data.hasSeries} />
                <PlanView plan={data.plan} hasSeries={data.hasSeries} />
              </>
            )}
            {tab === "activity" && <ActivityLog />}
            {tab === "audit" && <AuditTimeline audit={data.audit} />}
          </div>
        </Panel>
      )}
    </div>
  );
}

function WorkspaceRoute() {
  const params = useSearchParams();
  const caseId = params.get("case");

  if (!caseId) return <CasePicker basePath="/workspace/" purpose="to analyse" />;
  // `key` resets all case-scoped state when the case changes.
  return <Workspace key={caseId} caseId={caseId} />;
}

export default function WorkspacePage() {
  return (
    <Suspense fallback={<StateBlock kind="loading" title="Loading workspace…" />}>
      <WorkspaceRoute />
    </Suspense>
  );
}
