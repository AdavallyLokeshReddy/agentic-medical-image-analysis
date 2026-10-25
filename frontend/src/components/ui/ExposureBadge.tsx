import type { HttpExposure } from "@/types/api";
import { cn } from "@/utils/format";
import { Icon, type IconName } from "./Icon";

const MAP: Record<HttpExposure, { label: string; icon: IconName; cls: string; hint: string }> = {
  yes: {
    label: "HTTP · read-only",
    icon: "check",
    cls: "border-live/40 bg-live/10 text-live",
    hint: "Exposed by the read-only governance router.",
  },
  plan_only: {
    label: "HTTP · plan only",
    icon: "check",
    cls: "border-live/40 bg-live/10 text-live",
    hint: "Its planning output is exposed; nothing is executed.",
  },
  partial: {
    label: "HTTP · partial",
    icon: "check",
    cls: "border-accent/40 bg-accent/10 text-accent",
    hint: "Some of this module is reflected in HTTP responses.",
  },
  if_database: {
    label: "HTTP · needs PostgreSQL",
    icon: "database",
    cls: "border-warn/40 bg-warn/10 text-warn",
    hint: "Readable over HTTP only when a PostgreSQL database is reachable.",
  },
  no: {
    label: "Library only",
    icon: "lock",
    cls: "border-dashed border-line2 bg-white/[0.02] text-faint",
    hint: "Implemented and tested as Python code; no HTTP route exposes it.",
  },
};

export function ExposureBadge({ kind }: { kind: HttpExposure }) {
  const s = MAP[kind] ?? MAP.no;
  return (
    <span className={cn("chip", s.cls)} title={s.hint}>
      <Icon name={s.icon} size={12} />
      {s.label}
    </span>
  );
}
