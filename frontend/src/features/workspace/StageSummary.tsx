import { PROVENANCE, type Provenance } from "@/lib/provenance";
import type { StageState } from "@/features/workflow/derive";
import { STAGES, type StageId } from "@/features/workflow/stages";

/**
 * One segment per workflow stage, coloured by where its data comes from.
 * The sentence underneath counts exactly what the segments show.
 */
export function StageSummary({ states }: { states: Record<StageId, StageState> }) {
  const kinds = STAGES.map((s) => states[s.id].provenance);
  const count = (k: Provenance) => kinds.filter((x) => x === k).length;
  const live = count("live");
  const notExposed = count("not_exposed");

  return (
    <div className="border-b border-line px-4 py-3">
      <div className="flex gap-1" role="img" aria-label={`${live} of ${kinds.length} stages backed by live backend data`}>
        {STAGES.map((s, i) => (
          <span
            key={s.id}
            title={`${s.label}: ${PROVENANCE[kinds[i]].label}`}
            className="h-1.5 flex-1 rounded-full transition-colors duration-500"
            style={{
              background: kinds[i] === "not_exposed" ? "transparent" : PROVENANCE[kinds[i]].color,
              border: kinds[i] === "not_exposed" ? "1px dashed rgba(148,170,200,0.4)" : "none",
              opacity: kinds[i] === "ready" ? 0.4 : 1,
            }}
          />
        ))}
      </div>
      <p className="num mt-2 text-[11px] text-dim">
        {live} of {kinds.length} stages backed by live data · {notExposed} not exposed over HTTP
      </p>
    </div>
  );
}
