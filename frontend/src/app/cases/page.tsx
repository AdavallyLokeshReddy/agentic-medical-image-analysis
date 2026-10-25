"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { api } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { useBackend } from "@/components/shell/BackendContext";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, Skeleton } from "@/components/ui/Panel";
import { StateBlock } from "@/components/ui/StateBlock";
import { useAsync } from "@/hooks/useAsync";
import { rememberCase } from "@/lib/rememberedCases";
import { cn, formatDateTime, formatRelative } from "@/utils/format";

const STATUS_TONE: Record<string, string> = {
  created: "border-accent/40 bg-accent/10 text-accent",
  uploaded: "border-live/40 bg-live/10 text-live",
  existing: "border-line2 bg-white/[0.03] text-dim",
};

export default function CasesPage() {
  const router = useRouter();
  const backend = useBackend();
  const online = backend.state === "online";
  const list = useAsync((signal) => api.listCases({ signal }), [online], { enabled: online });

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<ApiError | null>(null);

  const statuses = useMemo(() => Array.from(new Set(list.data?.cases.map((c) => c.status) ?? [])), [list.data]);
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (list.data?.cases ?? []).filter(
      (c) => (status === "all" || c.status === status) && (!q || c.case_id.toLowerCase().includes(q)),
    );
  }, [list.data, query, status]);

  async function createCase() {
    setCreating(true);
    setCreateError(null);
    try {
      const created = await api.createCase();
      rememberCase(created.case_id);
      router.push(`/workspace/?case=${encodeURIComponent(created.case_id)}`);
    } catch (e) {
      setCreateError(e instanceof ApiError ? e : null);
      setCreating(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Case management"
        title="Cases"
        description="Cases held by the connected backend. A case is the unit of work: identity, uploaded series and workflow state."
        actions={
          <button type="button" className="btn btn-primary px-4" onClick={createCase} disabled={!online || creating}>
            <Icon name="plus" size={15} />
            {creating ? "Creating case…" : "New case"}
          </button>
        }
      />

      {createError && (
        <div className="panel mb-4">
          <StateBlock compact kind="error" title="Could not create the case" error={createError} />
        </div>
      )}

      <Panel
        title={list.data ? `${rows.length} of ${list.data.count} cases` : "Cases"}
        right={
          <div className="flex items-center gap-2">
            <label className="relative">
              <span className="sr-only">Search cases</span>
              <Icon name="search" size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search case ID"
                className="num h-8 w-44 rounded-lg border border-line2 bg-black/30 pl-8 pr-2 text-xs outline-none placeholder:text-faint focus:border-accent/60"
              />
            </label>
            <label className="sr-only" htmlFor="status-filter">
              Filter by status
            </label>
            <select
              id="status-filter"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="h-8 rounded-lg border border-line2 bg-black/30 px-2 text-xs outline-none focus:border-accent/60"
            >
              <option value="all">All statuses</option>
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <button type="button" className="btn btn-icon" onClick={list.reload} aria-label="Refresh case list" title="Refresh">
              <Icon name="refresh" size={14} />
            </button>
          </div>
        }
      >
        {!online ? (
          <StateBlock
            kind={backend.state === "misconfigured" ? "unavailable" : "error"}
            title={backend.state === "connecting" ? "Connecting to orchestration engine…" : "Backend not connected"}
            message="Cases can be listed and created once the API is reachable."
            onRetry={backend.state === "connecting" ? undefined : backend.recheck}
          />
        ) : list.status === "loading" && !list.data ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : list.status === "error" ? (
          list.error?.status === 404 ? (
            <StateBlock kind="not_exposed" title="Case listing not exposed" message="This backend build has no GET /cases route. Create a case to continue." />
          ) : (
            <StateBlock kind="error" title="Could not load cases" error={list.error} onRetry={list.reload} />
          )
        ) : list.data && list.data.count === 0 ? (
          <StateBlock kind="empty" title="No cases yet" message="Create a case, then upload a CT series to it.">
            <button type="button" className="btn btn-primary mt-1" onClick={createCase} disabled={creating}>
              <Icon name="plus" size={14} /> New case
            </button>
          </StateBlock>
        ) : rows.length === 0 ? (
          <StateBlock compact kind="empty" title="No cases match the filter" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-[13px]">
              <thead>
                <tr className="border-b border-line text-faint">
                  {["Case", "Status", "Series", "Files", "Last modified", ""].map((h) => (
                    <th key={h} scope="col" className="panel-title px-4 py-2.5 font-normal">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((c) => (
                  <tr key={c.case_id} className="transition-colors hover:bg-white/[0.03]">
                    <td className="num px-4 py-3 font-medium">{c.case_id}</td>
                    <td className="px-4 py-3">
                      <span className={cn("chip", STATUS_TONE[c.status] ?? "border-line2 text-dim")}>{c.status}</span>
                    </td>
                    <td className="num px-4 py-3">{c.series_count}</td>
                    <td className="num px-4 py-3">{c.file_count}</td>
                    <td className="px-4 py-3 text-dim" title={formatDateTime(c.updated_at)}>
                      {formatRelative(c.updated_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/workspace/?case=${encodeURIComponent(c.case_id)}`}
                        onClick={() => rememberCase(c.case_id)}
                        className="btn"
                      >
                        Open workspace <Icon name="arrowRight" size={13} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <p className="mt-3 px-1 text-xs leading-relaxed text-faint">
        “Last modified” is the case folder’s filesystem time (the only timestamp the backend keeps). Case state is held in
        memory, so after a backend restart older cases appear with status “existing”.
      </p>
    </div>
  );
}
