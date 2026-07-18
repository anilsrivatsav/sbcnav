"use client";

import { Panel } from "../ui";

export function ReportTemplatesPanel({ templates, onApply }) {
  return (
    <Panel title="Report Templates" subtitle="Start from a guided operational report, then refine filters and export or drill down.">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {templates.map((template) => {
          const Icon = template.icon;
          return (
            <button
              key={template.id}
              type="button"
              onClick={() => onApply(template)}
              className="group rounded-2xl border border-line bg-surface/75 p-4 text-left transition hover:-translate-y-0.5 hover:border-accent hover:bg-surfaceStrong hover:shadow-glow"
            >
              <div className="flex items-start gap-3">
                <div className="rounded-xl bg-accentSoft p-2 text-accentStrong">
                  <Icon size={18} />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-black text-ink">{template.label}</div>
                  <div className="mt-1 text-xs font-semibold text-muted">{template.description}</div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </Panel>
  );
}
