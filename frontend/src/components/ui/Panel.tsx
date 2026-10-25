import type { ReactNode } from "react";
import { cn } from "@/utils/format";

export function Panel({
  title,
  right,
  children,
  className,
  bodyClassName,
  as: Tag = "section",
}: {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  as?: "section" | "div" | "aside" | "article";
}) {
  return (
    <Tag className={cn("panel flex min-h-0 flex-col", className)}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <h2 className="panel-title">{title}</h2>
          {right}
        </header>
      )}
      <div className={cn("min-h-0 flex-1", bodyClassName)}>{children}</div>
    </Tag>
  );
}

/** Label / value row used for dense metadata. */
export function Field({
  label,
  children,
  mono = true,
  title,
}: {
  label: string;
  children: ReactNode;
  mono?: boolean;
  title?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-[13px]">
      <dt className="shrink-0 text-faint">{label}</dt>
      <dd title={title} className={cn("min-w-0 truncate text-right text-ink", mono && "num")}>
        {children}
      </dd>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("anim-blink rounded-md bg-white/[0.06]", className)} aria-hidden="true" />;
}
