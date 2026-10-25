"use client";

import { api } from "@/api/endpoints";
import { useBackend } from "@/components/shell/BackendContext";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { ProvenanceBadge } from "@/components/ui/ProvenanceBadge";
import { StateBlock } from "@/components/ui/StateBlock";
import { CapabilityMatrix } from "@/features/overview/CapabilityMatrix";
import { SystemStatus } from "@/features/overview/SystemStatus";
import { ToolCards } from "@/features/governance/ToolCards";
import { useAsync } from "@/hooks/useAsync";

const NOT_EXPOSED = [
  ["Evidence generation", "Typed evidence objects with provenance are produced when a model tool runs."],
  ["Evidence verification", "Technical, applicability and cross-output checks run on that evidence."],
  ["Human-review lifecycle", "Accept / modify / reject decisions and review state transitions."],
  ["Structured report", "Assembled from evidence, verification and review state."],
];

export default function GovernancePage() {
  const backend = useBackend();
  const online = backend.state === "online";
  const gov = useAsync((signal) => api.governanceStatus({ signal }), [online], { enabled: online });
  const tools = useAsync((signal) => api.governanceTools({ signal }), [online], { enabled: online });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Governance"
        title="Tools, policy and what is actually exposed"
        description="Everything on this page is read from the running backend. The governance code is real and tested; this page shows precisely which parts the HTTP API surfaces, and why model execution is not one of them."
      />

      {!online && (
        <Panel>
          <StateBlock
            kind={backend.state === "connecting" ? "loading" : backend.state === "misconfigured" ? "unavailable" : "error"}
            title={backend.state === "connecting" ? "Connecting to orchestration engine…" : "Backend not connected"}
            onRetry={backend.state === "connecting" ? undefined : backend.recheck}
          />
        </Panel>
      )}

      {online && (
        <>
          <Panel
            title="Approved tool registry"
            right={<ProvenanceBadge kind="live" label="Metadata only · never executed here" />}
          >
            <ToolCards tools={tools} />
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            <SystemStatus gov={gov} />
            <CapabilityMatrix gov={gov} />
          </div>

          <Panel title="Not exposed over HTTP — and why">
            <div className="p-4">
              <p className="max-w-3xl text-[13px] leading-relaxed text-dim">
                These stages are produced by <em>running a model</em>. Running a model needs PyTorch, the external{" "}
                <span className="num">skp</span> research code and downloaded weights, so no HTTP route triggers it. The
                platform therefore never fabricates their output — it shows them as not exposed.
              </p>
              <ul className="mt-4 grid gap-3 md:grid-cols-2">
                {NOT_EXPOSED.map(([title, note]) => (
                  <li key={title} className="rounded-lg border border-dashed border-line2 bg-white/[0.02] p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[13px] font-medium">{title}</span>
                      <ProvenanceBadge kind="not_exposed" />
                    </div>
                    <p className="mt-1 text-xs leading-snug text-dim">{note}</p>
                  </li>
                ))}
              </ul>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
