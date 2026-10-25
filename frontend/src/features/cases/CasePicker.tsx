"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { Icon } from "@/components/ui/Icon";
import { Panel } from "@/components/ui/Panel";
import { StateBlock } from "@/components/ui/StateBlock";
import { useBackend } from "@/components/shell/BackendContext";
import { useAsync } from "@/hooks/useAsync";
import { rememberCase } from "@/lib/rememberedCases";
import { formatRelative } from "@/utils/format";

/** Shown when a case-scoped page is opened without `?case=`. */
export function CasePicker({ basePath, purpose }: { basePath: "/workspace/" | "/report/"; purpose: string }) {
  const router = useRouter();
  const backend = useBackend();
  const online = backend.state === "online";
  const list = useAsync((signal) => api.listCases({ signal }), [online], { enabled: online });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function create() {
    setCreating(true);
    setError(null);
    try {
      const c = await api.createCase();
      rememberCase(c.case_id);
      router.push(`${basePath}?case=${encodeURIComponent(c.case_id)}`);
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Panel title="Select a case">
        {!online ? (
          <StateBlock
            kind={backend.state === "misconfigured" ? "unavailable" : backend.state === "connecting" ? "loading" : "error"}
            title={backend.state === "connecting" ? "Connecting to orchestration engine…" : "Backend not connected"}
            message={`Select a case ${purpose} once the API is reachable.`}
            onRetry={backend.state === "connecting" ? undefined : backend.recheck}
          />
        ) : (
          <>
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <p className="text-[13px] text-dim">Choose a case {purpose}, or start a new one.</p>
              <button type="button" className="btn btn-primary" onClick={create} disabled={creating}>
                <Icon name="plus" size={14} />
                {creating ? "Creating…" : "New case"}
              </button>
            </div>
            {error && <StateBlock compact kind="error" title="Could not create the case" error={error} />}
            {list.status === "loading" && !list.data ? (
              <StateBlock compact kind="loading" title="Loading cases…" />
            ) : list.status === "error" ? (
              <StateBlock compact kind="error" title="Could not load cases" error={list.error} onRetry={list.reload} />
            ) : list.data && list.data.count === 0 ? (
              <StateBlock compact kind="empty" title="No cases yet" message="Create one to begin." />
            ) : (
              <ul className="divide-y divide-line">
                {list.data?.cases.map((c) => (
                  <li key={c.case_id}>
                    <Link
                      href={`${basePath}?case=${encodeURIComponent(c.case_id)}`}
                      onClick={() => rememberCase(c.case_id)}
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
          </>
        )}
      </Panel>
    </div>
  );
}
