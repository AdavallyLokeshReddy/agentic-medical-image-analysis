"use client";

import { Field, Panel, Skeleton } from "@/components/ui/Panel";
import { ProvenanceBadge } from "@/components/ui/ProvenanceBadge";
import { StateBlock } from "@/components/ui/StateBlock";
import { useBackend } from "@/components/shell/BackendContext";
import type { AsyncResult } from "@/hooks/useAsync";
import type { GovernanceStatus } from "@/types/api";

function yesNo(v: boolean) {
  return v ? "installed" : "not installed";
}

/** Every value here is read from the running backend (/health, /governance/status). */
export function SystemStatus({ gov }: { gov: AsyncResult<GovernanceStatus> }) {
  const backend = useBackend();
  const g = gov.data;

  return (
    <Panel
      title="Live system status"
      right={<ProvenanceBadge kind={backend.state === "online" ? "live" : backend.state === "connecting" ? "pending" : "error"} />}
    >
      <div className="space-y-4 p-4">
        <dl className="divide-y divide-line">
          <Field label="API connection">
            {backend.state === "online"
              ? `online · v${backend.version} · ${backend.latencyMs} ms`
              : backend.state === "connecting"
                ? "connecting…"
                : backend.state === "misconfigured"
                  ? "URL not configured"
                  : "connection lost"}
          </Field>
        </dl>

        {gov.status === "loading" && !g && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-4 w-3/5" />
          </div>
        )}

        {gov.status === "error" && (
          <StateBlock
            compact
            kind={gov.error?.status === 404 ? "not_exposed" : "error"}
            title={gov.error?.status === 404 ? "Governance endpoint not exposed" : "Governance status unavailable"}
            message={
              gov.error?.status === 404
                ? "This backend build does not include the read-only governance router."
                : gov.error?.message
            }
            error={gov.error?.status === 404 ? null : gov.error}
            onRetry={gov.reload}
          />
        )}

        {g && (
          <>
            <dl className="divide-y divide-line">
              <Field label="Tool registry">
                {g.tool_registry.loaded ? `${g.tool_registry.tool_count} tools · metadata only` : "unavailable"}
              </Field>
              <Field label="Model execution over HTTP">{g.model_runtime.execution_exposed_over_http ? "yes" : "no — by design"}</Field>
              <Field label="PyTorch">{yesNo(g.model_runtime.torch_installed)}</Field>
              <Field label="MONAI">{yesNo(g.model_runtime.monai_installed)}</Field>
              <Field label="skp (head-CT model code)">{yesNo(g.model_runtime.skp_installed)}</Field>
              <Field label="PostgreSQL (audit store)">
                {!g.persistence.configured
                  ? "not configured"
                  : g.persistence.reachable
                    ? "reachable"
                    : `unreachable${g.persistence.error ? ` (${g.persistence.error})` : ""}`}
              </Field>
            </dl>
            {!g.model_runtime.skp_installed && (
              <p className="rounded-lg border border-warn/25 bg-warn/[0.06] p-3 text-xs leading-relaxed text-warn">
                Model runtime unavailable in this environment: the external <span className="num">skp</span> research
                code and model weights are not part of the repository. The platform therefore shows the governed
                workflow honestly and does not produce evidence, findings or reports.
              </p>
            )}
          </>
        )}
      </div>
    </Panel>
  );
}
