"use client";

import { Fragment } from "react";
import { Icon } from "@/components/ui/Icon";
import { ProvenanceBadge } from "@/components/ui/ProvenanceBadge";
import { Skeleton } from "@/components/ui/Panel";
import { StateBlock } from "@/components/ui/StateBlock";
import type { AsyncResult } from "@/hooks/useAsync";
import type { GovernancePlan, SafetyContractDto, TaskNodeDto } from "@/types/api";
import { cn } from "@/utils/format";

function pretty(s: string) {
  return s.replace(/_/g, " ").replace(/\bich\b/gi, "ICH");
}

function Tag({ children, tone }: { children: React.ReactNode; tone?: "warn" | "live" | "model" }) {
  return (
    <span
      className={cn(
        "chip !text-[10.5px]",
        tone === "warn" && "border-warn/40 bg-warn/10 text-warn",
        tone === "live" && "border-live/40 bg-live/10 text-live",
        tone === "model" && "border-model/40 bg-model/10 text-model",
        !tone && "border-line2 text-dim",
      )}
    >
      {children}
    </span>
  );
}

function TaskCard({ task, index }: { task: TaskNodeDto; index: number }) {
  return (
    <details className="group rounded-lg border border-line bg-white/[0.025] open:bg-white/[0.04]">
      <summary className="flex cursor-pointer list-none items-start gap-3 px-3 py-2.5">
        <span className="num mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border border-line2 text-[10px] text-faint">
          {index + 1}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="text-[13px] font-medium capitalize">{pretty(task.task_type)}</span>
            <Tag>{task.status}</Tag>
            {task.verification_required && <Tag tone="warn">verification required</Tag>}
            {task.permitted_tools.map((t) => (
              <Tag key={t} tone="model">
                {t}
              </Tag>
            ))}
          </span>
          <span className="mt-1 block text-xs leading-snug text-dim">{task.description}</span>
        </span>
        <Icon name="chevron" size={14} className="mt-1 shrink-0 text-faint transition-transform group-open:rotate-180" />
      </summary>
      <div className="grid gap-3 border-t border-line px-3 py-2.5 text-xs sm:grid-cols-2">
        <div>
          <p className="panel-title mb-1 !text-[10px]">Preconditions</p>
          <ul className="list-disc space-y-0.5 pl-4 text-dim">
            {task.preconditions.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="panel-title mb-1 !text-[10px]">Stopping conditions</p>
          <ul className="list-disc space-y-0.5 pl-4 text-dim">
            {task.stopping_conditions.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
        <p className="num text-[11px] text-faint sm:col-span-2">
          {task.task_id}
          {task.dependencies.length > 0 && ` · depends on ${task.dependencies.join(", ")}`}
        </p>
      </div>
    </details>
  );
}

function Contract({ c }: { c: SafetyContractDto }) {
  const rows: { label: string; value: React.ReactNode }[] = [
    { label: "Approved tools", value: c.approved_tools.join(", ") || "none" },
    { label: "Allowed modalities", value: c.data_policy.allowed_modalities.join(", ") },
    { label: "Allowed body regions", value: c.data_policy.allowed_body_regions.filter(Boolean).join(", ") },
    { label: "Allowed operations", value: c.operation_policy.allowed_operations.join(" · ") },
    { label: "Maximum action tier", value: c.operation_policy.maximum_action_tier },
    { label: "Verification required", value: c.uncertainty_policy.require_verification ? "yes" : "no" },
    { label: "Minimum confidence", value: String(c.uncertainty_policy.minimum_confidence) },
    { label: "Abstain on missing evidence", value: c.uncertainty_policy.abstain_on_missing_evidence ? "yes" : "no" },
    { label: "Abstain on failed verification", value: c.uncertainty_policy.abstain_on_verification_failure ? "yes" : "no" },
    { label: "Human review required", value: c.escalation_policy.human_review_required ? "yes" : "no" },
    { label: "Escalation path", value: c.escalation_policy.escalation_paths.join(", ") },
    { label: "Retries / timeout", value: `${c.resource_policy.maximum_retries} / ${c.resource_policy.timeout_seconds} s` },
    { label: "Concurrent tools", value: String(c.resource_policy.maximum_concurrent_tools) },
  ];
  return (
    <dl className="divide-y divide-line">
      {rows.map((r) => (
        <div key={r.label} className="flex items-baseline justify-between gap-4 py-1.5 text-[13px]">
          <dt className="shrink-0 text-faint">{r.label}</dt>
          <dd className="num min-w-0 break-words text-right">{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function PlanView({ plan, hasSeries }: { plan: AsyncResult<GovernancePlan>; hasSeries: boolean }) {
  if (!hasSeries) {
    return (
      <StateBlock compact kind="empty" title="Planning runs after a series is uploaded" message="The orchestrator needs imaging input to build a case-specific plan." />
    );
  }
  if (plan.status === "loading" && !plan.data) {
    return (
      <div className="space-y-2 p-4" role="status" aria-label="Building safety contract and task graph">
        <p className="text-xs text-dim">Building safety contract and task graph…</p>
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }
  if (plan.status === "error") {
    const unavailable = plan.error?.status === 503;
    const missing = plan.error?.status === 404;
    return (
      <StateBlock
        compact
        kind={unavailable ? "unavailable" : missing ? "not_exposed" : "error"}
        title={unavailable ? "Orchestrator planning unavailable" : missing ? "Governance endpoint not exposed" : "Planning failed"}
        message={missing ? "This backend build has no governance router." : undefined}
        error={plan.error}
        onRetry={plan.reload}
      />
    );
  }
  const p = plan.data;
  if (!p) return null;
  const tasks = p.plan.task_graph.tasks ?? [];

  return (
    <div className="grid gap-5 p-4 lg:grid-cols-[1.15fr_1fr]">
      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h3 className="panel-title">Task graph · {tasks.length} tasks</h3>
          <Tag tone={p.plan.execution_started ? "warn" : "live"}>execution_started = {String(p.plan.execution_started)}</Tag>
          <ProvenanceBadge kind="live" label="Planned, not executed" />
        </div>
        <div className="space-y-1">
          {tasks.map((t, i) => (
            <Fragment key={t.task_id}>
              <TaskCard task={t} index={i} />
              {i < tasks.length - 1 && (
                <div className="flex justify-start pl-[22px] text-faint" aria-hidden="true">
                  <Icon name="arrowDown" size={12} />
                </div>
              )}
            </Fragment>
          ))}
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-faint">
          Source: <span className="num">{p.source}</span>. Tasks are “proposed”: the backend plans the work and enforces
          policy, but no HTTP route runs the model, so nothing below has been executed for this case.
        </p>
      </div>
      <div>
        <h3 className="panel-title mb-2">Safety contract · {p.plan.safety_contract.contract_id}</h3>
        <Contract c={p.plan.safety_contract} />
        <p className="mt-3 text-[11px] leading-relaxed text-faint">
          Inputs — body region “{p.inputs.body_region}” ({p.inputs.body_region_source}); modality {p.inputs.modality} (
          {p.inputs.modality_source}).
        </p>
      </div>
    </div>
  );
}
