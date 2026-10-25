"use client";

import { useCallback, useEffect, useEffectEvent, useState } from "react";
import { ApiError } from "@/api/client";

export type AsyncStatus = "idle" | "loading" | "success" | "error";

export interface AsyncResult<T> {
  status: AsyncStatus;
  /** Latest successful data; kept while a reload is in flight (no flash of empty). */
  data: T | null;
  error: ApiError | null;
  reload: () => void;
}

interface Settled<T> {
  key: string;
  data: T | null;
  error: ApiError | null;
}

function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  return new ApiError({
    kind: "network",
    message: err instanceof Error ? err.message : "Unexpected error.",
    technical: String(err),
  });
}

/**
 * Loads data with explicit idle / loading / success / error states.
 *
 * Status is DERIVED during render from "which request key has settled", so no
 * state is set synchronously inside the effect and stale results can never be
 * shown as current.
 */
export function useAsync<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: ReadonlyArray<string | number | boolean | null | undefined>,
  options: { enabled?: boolean } = {},
): AsyncResult<T> {
  const enabled = options.enabled ?? true;
  const [nonce, setNonce] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);

  const depsKey = JSON.stringify(deps);
  const key = `${nonce}|${depsKey}`;

  const run = useEffectEvent((signal: AbortSignal) => load(signal));

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    run(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setSettled({ key, data, error: null });
      },
      (err) => {
        if (controller.signal.aborted) return;
        setSettled((prev) => ({ key, data: prev?.data ?? null, error: toApiError(err) }));
      },
    );
    return () => controller.abort();
  }, [enabled, key]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  let status: AsyncStatus;
  if (!enabled) status = "idle";
  else if (!settled || settled.key !== key) status = "loading";
  else status = settled.error ? "error" : "success";

  return {
    status,
    data: settled?.data ?? null,
    error: status === "error" ? (settled?.error ?? null) : null,
    reload,
  };
}
