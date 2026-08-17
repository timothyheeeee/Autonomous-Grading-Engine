"use client";

import type { AuditStep } from "@/lib/api";

export default function AuditTrail({ steps }: { steps: AuditStep[] }) {
  if (!steps.length) return null;
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-medium text-neutral-500">Audit trail</h2>
      <div className="divide-y divide-neutral-200 rounded-2xl border border-neutral-200 bg-white">
        {steps
          .slice()
          .sort((a, b) => a.step - b.step)
          .map((step) => (
            <details key={`${step.step}-${step.title}`} className="group px-5 py-4" open={step.step === steps.length}>
              <summary className="cursor-pointer list-none text-sm font-medium">
                <span className="mr-2 text-neutral-400">{String(step.step).padStart(2, "0")}</span>
                {step.title}
                <span className={`ml-2 text-xs ${step.ok ? "text-neutral-400" : "text-red-600"}`}>
                  {step.ok ? "ok" : "halted"}
                </span>
              </summary>
              <p className="mt-2 text-sm leading-6 text-neutral-600">{step.detail}</p>
            </details>
          ))}
      </div>
    </section>
  );
}
