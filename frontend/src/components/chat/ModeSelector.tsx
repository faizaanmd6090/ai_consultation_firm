"use client";

import type { IntakeMode } from "@/lib/types";

type Props = {
  mode: IntakeMode;
  onChange: (mode: IntakeMode) => void;
};

export function ModeSelector({ mode, onChange }: Props) {
  const items: Array<{ value: IntakeMode; label: string; hint: string }> = [
    { value: "quick", label: "Quick", hint: "Faster, fewer follow-ups" },
    { value: "guided", label: "Guided", hint: "Recommended balance" },
    { value: "detailed", label: "Detailed", hint: "Deeper diligence" },
  ];
  return (
    <div className="card" style={{ padding: "0.8rem", marginBottom: "0.75rem" }}>
      <div className="panel-title-row">
        <h4 className="section-heading" style={{ marginBottom: 0 }}>Intake Mode</h4>
        <span className="tag">Guided recommended</span>
      </div>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {items.map((item) => (
          <button
            key={item.value}
            className={`btn ${mode === item.value ? "btn-primary" : "btn-ghost"}`}
            onClick={() => onChange(item.value)}
            title={item.hint}
          >
            {item.label}
          </button>
        ))}
      </div>
      <p className="muted" style={{ margin: "0.5rem 0 0", fontSize: "0.86rem" }}>
        Same chat UI for all modes. Mode changes follow-up depth, readiness threshold, and report depth.
      </p>
    </div>
  );
}
