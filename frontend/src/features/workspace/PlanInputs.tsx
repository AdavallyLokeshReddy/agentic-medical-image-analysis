"use client";

import { useState } from "react";
import { Icon } from "@/components/ui/Icon";
import type { PlanInputs } from "@/hooks/useCaseData";

const REGIONS = ["head", "brain", "chest"];

/**
 * The orchestrator needs a body region and (optionally) a clinical question.
 * The backend does NOT infer these; they are supplied here, and the UI says so.
 */
export function PlanInputsPanel({
  value,
  onApply,
  disabled,
}: {
  value: PlanInputs;
  onApply: (v: PlanInputs) => void;
  disabled?: boolean;
}) {
  const [region, setRegion] = useState(value.bodyRegion);
  const [question, setQuestion] = useState(value.clinicalQuestion);
  const dirty = region !== value.bodyRegion || question.trim() !== value.clinicalQuestion;

  return (
    <form
      className="flex flex-wrap items-end gap-3 border-b border-line px-4 py-3"
      onSubmit={(e) => {
        e.preventDefault();
        onApply({ bodyRegion: region, clinicalQuestion: question.trim() });
      }}
    >
      <label className="block text-xs text-dim">
        Body region
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          disabled={disabled}
          className="mt-1 block h-9 w-32 rounded-lg border border-line2 bg-black/30 px-2.5 text-[13px] text-ink outline-none focus:border-accent/60"
        >
          {REGIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </label>
      <label className="block min-w-[14rem] flex-1 text-xs text-dim">
        Clinical question <span className="text-faint">(optional)</span>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={disabled}
          maxLength={300}
          placeholder="e.g. Evaluate for intracranial hemorrhage"
          className="mt-1 block h-9 w-full rounded-lg border border-line2 bg-black/30 px-2.5 text-[13px] text-ink outline-none placeholder:text-faint focus:border-accent/60"
        />
      </label>
      <button type="submit" className="btn" disabled={disabled || !dirty}>
        <Icon name="refresh" size={14} /> Re-run planning
      </button>
      <p className="basis-full text-[11px] leading-relaxed text-faint">
        Supplied by you, not inferred by the backend. Planning builds a safety contract and task graph; it does not run any model.
      </p>
    </form>
  );
}
