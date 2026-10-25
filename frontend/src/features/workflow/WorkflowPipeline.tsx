"use client";

import { Fragment, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { ProvenanceBadge } from "@/components/ui/ProvenanceBadge";
import { PROVENANCE, type Provenance } from "@/lib/provenance";
import { cn } from "@/utils/format";
import type { StageState } from "./derive";
import { LAYERS, STAGES, type StageId } from "./stages";

type States = Record<StageId, StageState>;

function NodeMark({ kind }: { kind: Provenance }) {
  const s = PROVENANCE[kind];
  return (
    <span
      className={cn(
        "relative grid h-8 w-8 shrink-0 place-items-center rounded-full border bg-solid transition-colors duration-300",
        kind === "not_exposed" ? "border-dashed" : "border-solid",
        kind === "pending" && "anim-pulse",
      )}
      style={{ borderColor: s.color, color: s.color }}
    >
      {kind === "live" ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path className="anim-check" d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
      ) : (
        <Icon name={s.icon} size={15} className={kind === "pending" ? "anim-blink" : undefined} />
      )}
    </span>
  );
}

/** Vertical connector between two nodes. Flows only where data is genuinely moving. */
function Connector({ above, below }: { above: Provenance; below: Provenance }) {
  const flowing = above === "live" && below === "pending";
  const solid = above === "live" && below === "live";
  const color = solid ? PROVENANCE.live.color : flowing ? PROVENANCE.pending.color : "rgba(148,170,200,0.22)";
  return (
    <svg width="32" height="22" viewBox="0 0 32 22" className="shrink-0" aria-hidden="true">
      <line
        x1="16"
        y1="0"
        x2="16"
        y2="22"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        className={flowing ? "anim-flow" : undefined}
        strokeDasharray={solid || flowing ? undefined : "2 5"}
      />
    </svg>
  );
}

export function WorkflowPipeline({
  states,
  className,
}: {
  states: States;
  className?: string;
}) {
  const [open, setOpen] = useState<StageId | null>(null);

  return (
    <ol className={cn("flex flex-col", className)} aria-label="Workflow stages">
      {STAGES.map((stage, i) => {
        const st = states[stage.id];
        const prev = i > 0 ? states[STAGES[i - 1].id] : null;
        const showLayer = i === 0 || STAGES[i - 1].layer !== stage.layer;
        const expanded = open === stage.id;
        const detailId = `stage-${stage.id}-detail`;

        return (
          <Fragment key={stage.id}>
            {showLayer && (
              <li
                aria-hidden="true"
                className={cn("flex items-center gap-2 pb-1.5 pl-1", i > 0 && "pt-3")}
              >
                <span className="h-px w-3" style={{ background: LAYERS[stage.layer].color }} />
                <span className="panel-title !text-[10px]" style={{ color: LAYERS[stage.layer].color }}>
                  {LAYERS[stage.layer].label}
                </span>
              </li>
            )}
            <li className="flex gap-3">
              <div className="flex flex-col items-center">
                {prev && !showLayer ? (
                  <Connector above={prev.provenance} below={st.provenance} />
                ) : (
                  <span className="h-1" />
                )}
                <NodeMark kind={st.provenance} />
              </div>

              <div className={cn("min-w-0 flex-1", prev && !showLayer ? "pt-[22px]" : "pt-1")}>
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-controls={detailId}
                  onClick={() => setOpen(expanded ? null : stage.id)}
                  className="group flex w-full items-start justify-between gap-2 rounded-lg px-2 py-1 text-left transition-colors hover:bg-white/[0.04]"
                >
                  <span className="min-w-0">
                    <span className="block text-[13px] font-medium text-ink">{stage.label}</span>
                    <span
                      className={cn(
                        "block text-xs leading-snug",
                        st.provenance === "error" ? "text-danger" : st.provenance === "unavailable" ? "text-warn" : "text-dim",
                      )}
                    >
                      {st.detail}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5 pt-0.5">
                    <ProvenanceBadge kind={st.provenance} />
                    <Icon
                      name="chevron"
                      size={14}
                      className={cn("text-faint transition-transform duration-200", expanded && "rotate-180")}
                    />
                  </span>
                </button>

                {expanded && (
                  <div id={detailId} className="anim-rise mx-2 mb-2 mt-1 rounded-lg border border-line bg-black/20 p-3 text-xs">
                    <p className="leading-relaxed text-dim">{stage.description}</p>
                    <p className="num mt-2 text-[11px] text-faint">Backed by: {stage.backing}</p>
                    {st.facts.length > 0 && (
                      <dl className="mt-2 divide-y divide-line border-t border-line">
                        {st.facts.map((f) => (
                          <div key={f.label} className="flex items-baseline justify-between gap-3 py-1">
                            <dt className="text-faint">{f.label}</dt>
                            <dd className="num min-w-0 break-words text-right text-ink">{f.value}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                  </div>
                )}
              </div>
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
}
