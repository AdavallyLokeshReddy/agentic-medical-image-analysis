import type { IconName } from "@/components/ui/Icon";

/**
 * Provenance: where does what the user is looking at come from?
 * This is the honesty mechanism of the whole UI. Every workflow stage and every
 * data panel declares exactly one of these, and each has a distinct icon + text
 * label (never color alone).
 */
export type Provenance =
  | "live" //        backed by data the backend actually returned
  | "ready" //       capability exists; not yet run for this case
  | "pending" //     request in flight
  | "not_exposed" // library code exists, but no HTTP route exposes it
  | "unavailable" // route exists but cannot run in this environment
  | "error"; //      attempted and failed

export interface ProvenanceStyle {
  label: string;
  icon: IconName;
  /** Tailwind classes for the pill. */
  className: string;
  /** Hex used by SVG strokes in the pipeline diagram. */
  color: string;
}

export const PROVENANCE: Record<Provenance, ProvenanceStyle> = {
  live: {
    label: "Live data",
    icon: "check",
    className: "border-live/40 bg-live/10 text-live",
    color: "#4ade9f",
  },
  ready: {
    label: "Ready",
    icon: "dot",
    className: "border-accent/40 bg-accent/10 text-accent",
    color: "#5ad1e6",
  },
  pending: {
    label: "Running",
    icon: "activity",
    className: "border-accent/50 bg-accent/10 text-accent",
    color: "#5ad1e6",
  },
  not_exposed: {
    label: "Not exposed",
    icon: "lock",
    className: "border-dashed border-line2 bg-white/[0.02] text-faint",
    color: "#8394ad",
  },
  unavailable: {
    label: "Unavailable",
    icon: "alert",
    className: "border-warn/40 bg-warn/10 text-warn",
    color: "#f5b94a",
  },
  error: {
    label: "Error",
    icon: "x",
    className: "border-danger/40 bg-danger/10 text-danger",
    color: "#ff7a7a",
  },
};
