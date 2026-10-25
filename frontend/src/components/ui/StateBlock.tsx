import type { ReactNode } from "react";
import type { ApiError } from "@/api/client";
import { cn } from "@/utils/format";
import { Icon, type IconName } from "./Icon";

export type StateKind = "loading" | "empty" | "error" | "unavailable" | "not_exposed";

const STYLE: Record<StateKind, { icon: IconName; tone: string }> = {
  loading: { icon: "activity", tone: "text-accent" },
  empty: { icon: "layers", tone: "text-faint" },
  error: { icon: "alert", tone: "text-danger" },
  unavailable: { icon: "alert", tone: "text-warn" },
  not_exposed: { icon: "lock", tone: "text-faint" },
};

/**
 * One consistent treatment for every non-happy state, so each backend
 * operation has a polished loading / empty / error / unavailable / retry story.
 */
export function StateBlock({
  kind,
  title,
  message,
  error,
  onRetry,
  compact,
  children,
}: {
  kind: StateKind;
  title: string;
  message?: string;
  error?: ApiError | null;
  onRetry?: () => void;
  compact?: boolean;
  children?: ReactNode;
}) {
  const s = STYLE[kind];
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      aria-live={kind === "loading" ? "polite" : undefined}
      className={cn(
        "flex flex-col items-center justify-center text-center",
        compact ? "gap-1.5 px-4 py-5" : "gap-2.5 px-6 py-10",
      )}
    >
      <span className={cn("grid place-items-center rounded-full border border-line2 bg-white/[0.03]", s.tone, compact ? "h-8 w-8" : "h-11 w-11")}>
        <Icon name={s.icon} size={compact ? 16 : 20} className={kind === "loading" ? "anim-blink" : undefined} />
      </span>
      <p className="text-sm font-medium text-ink">{title}</p>
      {(message || error?.message) && (
        <p className="max-w-md text-[13px] leading-relaxed text-dim">{message ?? error?.message}</p>
      )}
      {error && (
        <details className="max-w-md text-left text-xs text-faint">
          <summary className="cursor-pointer select-none text-center hover:text-dim">Technical details</summary>
          <pre className="num mt-2 whitespace-pre-wrap break-words rounded-md border border-line bg-black/30 p-2.5 text-[11px] text-dim">
            {error.technical}
          </pre>
        </details>
      )}
      {children}
      {onRetry && (
        <button type="button" className="btn mt-1" onClick={onRetry}>
          <Icon name="refresh" size={14} />
          Retry
        </button>
      )}
    </div>
  );
}
