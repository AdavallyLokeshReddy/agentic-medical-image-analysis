import { PROVENANCE, type Provenance } from "@/lib/provenance";
import { cn } from "@/utils/format";
import { Icon } from "./Icon";

export function ProvenanceBadge({
  kind,
  label,
  className,
}: {
  kind: Provenance;
  /** Override the default label (e.g. "Not produced"). */
  label?: string;
  className?: string;
}) {
  const s = PROVENANCE[kind];
  return (
    <span className={cn("chip uppercase", s.className, className)}>
      <Icon name={s.icon} size={12} className={kind === "pending" ? "anim-blink" : undefined} />
      {label ?? s.label}
    </span>
  );
}
