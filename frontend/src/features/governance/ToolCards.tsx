"use client";

import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Panel";
import { StateBlock } from "@/components/ui/StateBlock";
import type { AsyncResult } from "@/hooks/useAsync";
import type { GovernanceTools, ToolDescriptor } from "@/types/api";

function Chips({ items }: { items: string[] }) {
  return (
    <span className="flex flex-wrap gap-1">
      {items.map((i) => (
        <span key={i} className="chip border-line2 !text-[10.5px] text-dim">
          {i}
        </span>
      ))}
    </span>
  );
}

function ToolCard({ tool }: { tool: ToolDescriptor }) {
  return (
    <article className="rounded-xl border border-line bg-white/[0.025] p-4">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="num flex items-center gap-2 text-[14px] font-semibold">
            <Icon name="cube" size={15} className="text-model" />
            {tool.name}
          </h3>
          <p className="mt-1 text-[13px] leading-snug text-dim">{tool.description}</p>
        </div>
        <span className="chip border-model/40 bg-model/10 text-model">{tool.version}</span>
      </header>
      <dl className="mt-3 space-y-2 text-xs">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <dt className="text-faint">Modalities</dt>
          <dd>
            <Chips items={tool.supported_modalities} />
          </dd>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <dt className="text-faint">Body regions</dt>
          <dd>
            <Chips items={tool.supported_body_regions} />
          </dd>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <dt className="text-faint">Expected input</dt>
          <dd>
            <Chips items={tool.expected_inputs} />
          </dd>
        </div>
        <div>
          <dt className="text-faint">Intended use</dt>
          <dd className="mt-0.5 leading-snug text-dim">{tool.intended_use}</dd>
        </div>
        <div>
          <dt className="text-faint">Validation population</dt>
          <dd className="mt-0.5 leading-snug text-warn">{tool.validation_population}</dd>
        </div>
      </dl>
      {tool.exclusions.length > 0 && (
        <details className="mt-3 text-xs">
          <summary className="cursor-pointer select-none text-faint hover:text-dim">Declared exclusions ({tool.exclusions.length})</summary>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-dim">
            {tool.exclusions.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

export function ToolCards({ tools }: { tools: AsyncResult<GovernanceTools> }) {
  if (tools.status === "loading" && !tools.data) {
    return (
      <div className="grid gap-3 p-4 md:grid-cols-2">
        <Skeleton className="h-44" />
        <Skeleton className="h-44" />
      </div>
    );
  }
  if (tools.status === "error") {
    const missing = tools.error?.status === 404;
    return (
      <StateBlock
        kind={missing ? "not_exposed" : "error"}
        title={missing ? "Tool registry not exposed" : "Could not load the tool registry"}
        message={missing ? "This backend build has no governance router." : undefined}
        error={missing ? null : tools.error}
        onRetry={tools.reload}
      />
    );
  }
  if (tools.data && !tools.data.available) {
    return <StateBlock kind="unavailable" title="Tool registry unavailable" message={tools.data.reason ?? undefined} onRetry={tools.reload} />;
  }
  return (
    <div className="grid gap-3 p-4 md:grid-cols-2">
      {tools.data?.tools.map((t) => <ToolCard key={t.name} tool={t} />)}
    </div>
  );
}
