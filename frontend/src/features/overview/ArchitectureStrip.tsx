import { Fragment } from "react";
import { Icon } from "@/components/ui/Icon";
import { LAYERS, STAGES } from "@/features/workflow/stages";

/**
 * STATIC explanatory diagram of the architecture. It carries no run state and
 * says so. Live per-case status lives in the workspace.
 */
export function ArchitectureStrip() {
  const layers = (Object.keys(LAYERS) as (keyof typeof LAYERS)[]).map((key) => ({
    key,
    ...LAYERS[key],
    stages: STAGES.filter((s) => s.layer === key),
  }));

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 px-1 pb-3">
        <span className="chip border-dashed border-line2 text-faint">
          <Icon name="info" size={12} /> Architecture diagram · static, no run state
        </span>
        <span className="text-xs text-faint">Live per-case status appears in the Workspace</span>
      </div>
      <ol className="grid gap-3 lg:grid-cols-4" aria-label="Architecture layers">
        {layers.map((layer, li) => (
          <li
            key={layer.key}
            className="relative rounded-xl border bg-black/20 p-3.5"
            style={{ borderColor: `${layer.color}55` }}
          >
            <div className="mb-3 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: layer.color }} />
              <span className="panel-title !text-[10px]" style={{ color: layer.color }}>
                {li + 1} · {layer.label}
              </span>
            </div>
            <ul className="space-y-1.5">
              {layer.stages.map((st, i) => (
                <Fragment key={st.id}>
                  <li className="flex items-start gap-2.5 rounded-lg bg-white/[0.025] px-2.5 py-2">
                    <Icon name={st.icon} size={15} className="mt-0.5 shrink-0" style={{ color: layer.color }} />
                    <span className="min-w-0">
                      <span className="block text-[13px] font-medium">{st.label}</span>
                      <span className="block text-[11.5px] leading-snug text-dim">{st.description}</span>
                    </span>
                  </li>
                  {i < layer.stages.length - 1 && (
                    <li aria-hidden="true" className="flex justify-center text-faint">
                      <Icon name="arrowDown" size={12} />
                    </li>
                  )}
                </Fragment>
              ))}
            </ul>
            {li < layers.length - 1 && (
              <Icon
                name="arrowRight"
                size={16}
                aria-hidden="true"
                className="absolute -right-[15px] top-1/2 z-10 hidden -translate-y-1/2 rounded-full bg-bg p-0.5 text-faint lg:block"
              />
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
