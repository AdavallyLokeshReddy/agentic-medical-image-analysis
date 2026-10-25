/**
 * Remembers case IDs this browser has touched (localStorage).
 *
 * Only IDs are stored — no imaging data, no clinical content. It is a fallback
 * so the case list still works against a backend build that predates GET /cases.
 */
import { useMemo, useSyncExternalStore } from "react";

const KEY = "ami.recent-cases.v1";
const MAX = 20;
const listeners = new Set<() => void>();

function readRaw(): string {
  try {
    return window.localStorage.getItem(KEY) ?? "[]";
  } catch {
    return "[]";
  }
}

export function rememberCase(caseId: string): void {
  try {
    const current: string[] = JSON.parse(readRaw());
    const next = [caseId, ...current.filter((c) => c !== caseId)].slice(0, MAX);
    window.localStorage.setItem(KEY, JSON.stringify(next));
    listeners.forEach((l) => l());
  } catch {
    /* storage unavailable (private mode etc.) — non-fatal */
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function useRememberedCases(): string[] {
  const raw = useSyncExternalStore(subscribe, readRaw, () => "[]");
  return useMemo(() => {
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
    } catch {
      return [];
    }
  }, [raw]);
}
