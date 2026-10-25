/**
 * Client-side event log.
 *
 * Records the REAL backend calls this browser session makes (method, path,
 * HTTP status, measured duration). It is "Workflow Activity" telemetry as
 * observed from the client. It is NOT the backend's audit trail, and the UI
 * labels it that way.
 */
import { useSyncExternalStore } from "react";

export interface ClientEvent {
  id: number;
  ts: string; // ISO-8601, client clock
  method: string;
  path: string;
  /** HTTP status, or 0 when the request never completed. */
  status: number;
  ok: boolean;
  durationMs: number;
  /** Optional human label for the stage this call belongs to. */
  label?: string;
  error?: string;
}

const MAX_EVENTS = 300;
let events: ClientEvent[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit() {
  // New array identity so useSyncExternalStore subscribers re-render.
  events = events.slice();
  listeners.forEach((l) => l());
}

export function recordEvent(e: Omit<ClientEvent, "id" | "ts">): void {
  events.push({ ...e, id: nextId++, ts: new Date().toISOString() });
  if (events.length > MAX_EVENTS) events.splice(0, events.length - MAX_EVENTS);
  emit();
}

export function clearEvents(): void {
  events = [];
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const EMPTY: ClientEvent[] = [];

export function useClientEvents(): ClientEvent[] {
  return useSyncExternalStore(
    subscribe,
    () => events,
    () => EMPTY,
  );
}
