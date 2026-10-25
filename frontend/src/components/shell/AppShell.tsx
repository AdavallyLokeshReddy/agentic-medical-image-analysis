"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { NOTICE_SHORT } from "@/lib/config";
import { cn } from "@/utils/format";
import { Icon, type IconName } from "@/components/ui/Icon";
import { useBackend } from "./BackendContext";

const NAV: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Overview", icon: "home" },
  { href: "/cases/", label: "Cases", icon: "list" },
  { href: "/workspace/", label: "Workspace", icon: "layers" },
  { href: "/governance/", label: "Governance", icon: "shield" },
  { href: "/report/", label: "Report", icon: "file" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href.replace(/\/$/, ""));
}

function BrandMark() {
  return (
    <svg width="26" height="26" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="30" height="30" rx="8" stroke="var(--line-strong)" />
      <circle cx="16" cy="16" r="8.5" stroke="var(--accent)" strokeWidth="1.5" />
      <circle cx="16" cy="16" r="3" fill="var(--accent)" />
      <path d="M16 3v5M16 24v5M3 16h5M24 16h5" stroke="var(--accent)" strokeOpacity="0.55" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function BackendPill() {
  const b = useBackend();
  const map = {
    connecting: { text: "Connecting to orchestration engine…", dot: "bg-accent anim-blink", tone: "text-dim" },
    online: { text: "Backend online", dot: "bg-live", tone: "text-ink" },
    offline: { text: "Backend connection lost", dot: "bg-danger", tone: "text-danger" },
    misconfigured: { text: "Backend URL not configured", dot: "bg-warn", tone: "text-warn" },
  }[b.state];

  return (
    <button
      type="button"
      onClick={b.recheck}
      title="Click to re-check the backend connection"
      className={cn(
        "chip hidden max-w-[22rem] items-center gap-2 border-line2 bg-white/[0.03] px-2.5 py-1 hover:bg-white/[0.07] sm:inline-flex",
        map.tone,
      )}
    >
      <span className={cn("h-2 w-2 shrink-0 rounded-full", map.dot)} />
      <span className="truncate">{map.text}</span>
      {b.state === "online" && (
        <span className="num text-faint">
          v{b.version} · {b.latencyMs} ms
        </span>
      )}
    </button>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-solid focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      <header className="no-print sticky top-0 z-40 border-b border-line bg-bg/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-[1680px] items-center gap-4 px-4 lg:px-6">
          <Link href="/" className="flex items-center gap-2.5" aria-label="Agentic Medical Image Analysis — home">
            <BrandMark />
            <span className="hidden leading-tight sm:block">
              <span className="block text-[13px] font-semibold tracking-tight">Agentic Medical Image Analysis</span>
              <span className="panel-title block !text-[10px]">Governed workflow research platform</span>
            </span>
          </Link>

          <nav aria-label="Primary" className="ml-2 flex min-w-0 items-center gap-0.5 overflow-x-auto">
            {NAV.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[13px] transition-colors",
                    active ? "bg-white/[0.08] text-ink" : "text-dim hover:bg-white/[0.05] hover:text-ink",
                  )}
                >
                  <Icon name={item.icon} size={15} className={active ? "text-accent" : undefined} />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto">
            <BackendPill />
          </div>
        </div>

        <div role="note" className="border-t border-warn/20 bg-warn/[0.07]">
          <p className="mx-auto flex max-w-[1680px] items-center justify-center gap-2 px-4 py-1 text-center text-[11px] font-medium uppercase tracking-[0.12em] text-warn lg:px-6">
            <Icon name="alert" size={12} />
            {NOTICE_SHORT}
          </p>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-[1680px] flex-1 px-4 py-6 lg:px-6">
        {children}
      </main>
    </div>
  );
}
