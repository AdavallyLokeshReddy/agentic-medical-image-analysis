"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { getApiBase } from "@/lib/config";

export type ConnectionState = "connecting" | "online" | "offline" | "misconfigured";

export interface BackendHealth {
  state: ConnectionState;
  /** Round-trip time of the last successful /health call, measured in the browser. */
  latencyMs: number | null;
  version: string | null;
  lastCheckedAt: number | null;
  error: ApiError | null;
  recheck: () => void;
}

const POLL_MS = 15_000;

export function useBackendHealth(): BackendHealth {
  const [snapshot, setSnapshot] = useState<Omit<BackendHealth, "recheck">>({
    state: "connecting",
    latencyMs: null,
    version: null,
    lastCheckedAt: null,
    error: null,
  });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!getApiBase()) {
      // Resolved asynchronously so no state is set synchronously in the effect body.
      const t = setTimeout(
        () =>
          setSnapshot({
            state: "misconfigured",
            latencyMs: null,
            version: null,
            lastCheckedAt: Date.now(),
            error: null,
          }),
        0,
      );
      return () => clearTimeout(t);
    }

    let cancelled = false;
    const check = async () => {
      const t0 = performance.now();
      try {
        const h = await api.health({ silent: true });
        if (cancelled) return;
        setSnapshot({
          state: "online",
          latencyMs: Math.round(performance.now() - t0),
          version: h.version,
          lastCheckedAt: Date.now(),
          error: null,
        });
      } catch (e) {
        if (cancelled) return;
        setSnapshot((prev) => ({
          ...prev,
          state: "offline",
          latencyMs: null,
          lastCheckedAt: Date.now(),
          error: e instanceof ApiError ? e : null,
        }));
      }
    };

    void check();
    const id = setInterval(check, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [nonce]);

  const recheck = useCallback(() => {
    setSnapshot((prev) => ({ ...prev, state: "connecting" }));
    setNonce((n) => n + 1);
  }, []);

  return { ...snapshot, recheck };
}
