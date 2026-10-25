"use client";

import { StateBlock } from "@/components/ui/StateBlock";
import { Skeleton } from "@/components/ui/Panel";
import type { AsyncResult } from "@/hooks/useAsync";
import type { GovernanceAudit } from "@/types/api";
import { formatDateTime } from "@/utils/format";

export function AuditTimeline({ audit }: { audit: AsyncResult<GovernanceAudit> }) {
  if (audit.status === "loading" && !audit.data) {
    return (
      <div className="space-y-2 p-4">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }
  if (audit.status === "error") {
    const missing = audit.error?.status === 404;
    return (
      <StateBlock
        compact
        kind={missing ? "not_exposed" : "error"}
        title={missing ? "Audit endpoint not exposed" : "Audit read failed"}
        error={missing ? null : audit.error}
        message={missing ? "This backend build has no governance router." : undefined}
        onRetry={audit.reload}
      />
    );
  }
  const a = audit.data;
  if (!a) return null;
  if (!a.available) {
    return (
      <StateBlock compact kind="unavailable" title="Audit store unavailable" message={a.reason ?? undefined}>
        <p className="max-w-md text-xs leading-relaxed text-faint">
          The audit trail is an append-only PostgreSQL record written by the governed workflow. Without a database the
          platform does not invent one.
        </p>
      </StateBlock>
    );
  }
  if (a.events.length === 0) {
    return (
      <StateBlock
        compact
        kind="empty"
        title="No audit events recorded for this case"
        message="The database is reachable, but the HTTP upload path does not write audit events. Audit rows are produced by the governed workflow when it runs as a library."
      />
    );
  }
  return (
    <ol className="relative space-y-0 p-4">
      {a.events.map((e) => (
        <li key={e.event_id} className="relative flex gap-3 pb-4 last:pb-0">
          <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-live" />
          <span className="absolute bottom-0 left-[3.5px] top-4 w-px bg-line last:hidden" aria-hidden="true" />
          <div className="min-w-0 text-[13px]">
            <p className="font-medium">{e.action}</p>
            <p className="num text-[11px] text-faint">
              {formatDateTime(e.timestamp)} · {e.actor_type}
              {e.actor_id ? `:${e.actor_id}` : ""} · {e.entity_type}
              {e.entity_id ? ` ${e.entity_id}` : ""}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
