"use client";

import { ExposureBadge } from "@/components/ui/ExposureBadge";
import { Panel, Skeleton } from "@/components/ui/Panel";
import { StateBlock } from "@/components/ui/StateBlock";
import type { AsyncResult } from "@/hooks/useAsync";
import type { GovernanceStatus } from "@/types/api";

/** Which repository modules does the running API actually expose? Read from the backend itself. */
export function CapabilityMatrix({ gov }: { gov: AsyncResult<GovernanceStatus> }) {
  return (
    <Panel title="Governance modules · what the API exposes">
      {gov.status === "loading" && !gov.data ? (
        <div className="space-y-2 p-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-7 w-full" />
          ))}
        </div>
      ) : gov.status === "error" ? (
        <StateBlock compact kind="not_exposed" title="Module inventory not exposed" message={gov.error?.message} onRetry={gov.reload} />
      ) : (
        <ul className="divide-y divide-line">
          {gov.data?.library_modules.map((m) => (
            <li key={m.module} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
              <span className="min-w-0">
                <span className="block text-[13px] font-medium">{m.label}</span>
                <span className="num block text-[11px] text-faint">{m.module}</span>
              </span>
              <ExposureBadge kind={m.http_exposed} />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
