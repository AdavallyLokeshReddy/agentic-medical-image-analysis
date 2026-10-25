"use client";

import Link from "next/link";
import { api } from "@/api/endpoints";
import { useBackend } from "@/components/shell/BackendContext";
import { Icon } from "@/components/ui/Icon";
import { Panel, Skeleton } from "@/components/ui/Panel";
import { StateBlock } from "@/components/ui/StateBlock";
import { ArchitectureStrip } from "@/features/overview/ArchitectureStrip";
import { CapabilityMatrix } from "@/features/overview/CapabilityMatrix";
import { SystemStatus } from "@/features/overview/SystemStatus";
import { useAsync } from "@/hooks/useAsync";
import { NOTICE_LONG } from "@/lib/config";
import { formatRelative } from "@/utils/format";

const CHAIN = [
  { label: "Model output", note: "one component", model: true },
  { label: "Evidence" },
  { label: "Verification" },
  { label: "Governance" },
  { label: "Human oversight" },
  { label: "Report" },
  { label: "Audit" },
];

export default function OverviewPage() {
  const backend = useBackend();
  const online = backend.state === "online";
  const gov = useAsync((signal) => api.governanceStatus({ signal }), [online], { enabled: online });
  const cases = useAsync((signal) => api.listCases({ signal }), [online], { enabled: online });

  return (
    <div className="space-y-6">
      {/* hero */}
      <section className="panel relative overflow-hidden p-6 sm:p-8">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(600px 220px at 85% 0%, rgba(90,209,230,0.10), transparent 70%), radial-gradient(500px 260px at 0% 100%, rgba(165,149,255,0.08), transparent 70%)",
          }}
        />
        <div className="relative grid gap-8 lg:grid-cols-[1.1fr_1fr] lg:items-center">
          <div>
            <p className="panel-title mb-3 !text-accent">Agentic AI · autonomous medical image analysis · clinical workflow</p>
            <h1 className="text-3xl font-semibold leading-[1.12] tracking-tight sm:text-[40px]">
              The model is not the system.
              <span className="block text-dim">The governed workflow around it is.</span>
            </h1>
            <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-dim">
              A research platform for non-contrast head CT that treats model inference as one tool inside a larger,
              accountable pipeline: typed evidence, verification, a safety contract, human review, structured
              reporting and an audit trail.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-2.5">
              <Link href="/cases/" className="btn btn-primary px-4">
                <Icon name="plus" size={15} /> Start a case
              </Link>
              <Link href="/governance/" className="btn px-4">
                <Icon name="shield" size={15} /> Explore governance
              </Link>
            </div>
          </div>

          <div aria-label="Model output is one step in a governed chain" className="relative">
            <ol className="space-y-1.5">
              {CHAIN.map((c, i) => (
                <li key={c.label} className="flex items-center gap-3">
                  <span className="num w-5 text-right text-[11px] text-faint">{String(i + 1).padStart(2, "0")}</span>
                  <span
                    className={
                      c.model
                        ? "flex flex-1 items-center justify-between rounded-lg border border-model/50 bg-model/10 px-3.5 py-2 text-[13px] font-medium text-model"
                        : "flex flex-1 items-center justify-between rounded-lg border border-line bg-white/[0.03] px-3.5 py-2 text-[13px] font-medium"
                    }
                  >
                    {c.label}
                    {c.note && <span className="num text-[11px] font-normal opacity-80">{c.note}</span>}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* live status + capability matrix */}
      <div className="grid gap-6 lg:grid-cols-2">
        <SystemStatus gov={gov} />
        <CapabilityMatrix gov={gov} />
      </div>

      {/* architecture */}
      <Panel title="Architecture">
        <div className="p-4">
          <ArchitectureStrip />
        </div>
      </Panel>

      {/* recent cases */}
      <Panel
        title="Cases on this backend"
        right={
          <Link href="/cases/" className="text-xs text-accent hover:underline">
            All cases →
          </Link>
        }
      >
        {!online ? (
          <StateBlock compact kind="unavailable" title="Backend not connected" message="Cases load once the API is reachable." />
        ) : cases.status === "loading" && !cases.data ? (
          <div className="space-y-2 p-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : cases.status === "error" ? (
          <StateBlock compact kind="error" title="Could not list cases" error={cases.error} onRetry={cases.reload} />
        ) : cases.data && cases.data.count === 0 ? (
          <StateBlock compact kind="empty" title="No cases yet" message="Create the first case to begin the walkthrough." />
        ) : (
          <ul className="divide-y divide-line">
            {cases.data?.cases.slice(0, 5).map((c) => (
              <li key={c.case_id}>
                <Link
                  href={`/workspace/?case=${encodeURIComponent(c.case_id)}`}
                  className="flex items-center justify-between gap-3 px-4 py-2.5 transition-colors hover:bg-white/[0.04]"
                >
                  <span className="num text-[13px] font-medium">{c.case_id}</span>
                  <span className="num text-xs text-faint">
                    {c.series_count} series · {c.file_count} files · {formatRelative(c.updated_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <p className="px-1 text-center text-xs leading-relaxed text-faint">{NOTICE_LONG}</p>
    </div>
  );
}
