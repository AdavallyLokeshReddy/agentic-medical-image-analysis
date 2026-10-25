"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useBackendHealth, type BackendHealth } from "@/hooks/useBackendHealth";

const Ctx = createContext<BackendHealth | null>(null);

/** Runs the health poll once for the whole app. */
export function BackendProvider({ children }: { children: ReactNode }) {
  const health = useBackendHealth();
  return <Ctx.Provider value={health}>{children}</Ctx.Provider>;
}

export function useBackend(): BackendHealth {
  const v = useContext(Ctx);
  if (!v) throw new Error("useBackend must be used inside <BackendProvider>");
  return v;
}
