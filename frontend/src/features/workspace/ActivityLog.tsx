"use client";

import { useEffect, useRef } from "react";
import { StateBlock } from "@/components/ui/StateBlock";
import { clearEvents, useClientEvents } from "@/lib/eventLog";
import { cn, formatClock, formatMs } from "@/utils/format";

/**
 * "Workflow Activity": the real backend calls THIS browser session made, with measured
 * status and duration. It is client-observed telemetry — not the backend audit trail.
 */
export function ActivityLog() {
  const events = useClientEvents();
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [events.length]);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2 text-[11px] text-faint">
        <span>Backend calls observed by this browser · not the backend audit trail</span>
        <button type="button" className="hover:text-ink" onClick={clearEvents} disabled={events.length === 0}>
          Clear
        </button>
      </div>
      {events.length === 0 ? (
        <StateBlock compact kind="empty" title="No activity yet" message="Calls appear here as the workspace talks to the backend." />
      ) : (
        <ol className="num max-h-64 overflow-y-auto px-4 py-2 text-[12px]" aria-label="Workflow activity">
          {events.map((e) => (
            <li key={e.id} className="grid grid-cols-[4.5rem_3rem_minmax(0,1fr)_3.2rem_4.5rem] items-baseline gap-x-3 py-1">
              <span className="text-faint">{formatClock(e.ts)}</span>
              <span className="text-dim">{e.method}</span>
              <span className="min-w-0 truncate" title={e.path}>
                <span className="text-ink">{e.label ?? e.path}</span>
                <span className="ml-2 text-faint">{e.path}</span>
                {e.error && <span className="ml-2 text-danger">{e.error}</span>}
              </span>
              <span className={cn("text-right", e.ok ? "text-live" : "text-danger")}>{e.status || "ERR"}</span>
              <span className="text-right text-faint">{formatMs(e.durationMs)}</span>
            </li>
          ))}
          <div ref={end} />
        </ol>
      )}
    </div>
  );
}
