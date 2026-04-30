"use client";

import type { CaseInput } from "@/lib/types";

type Props = {
  draft: CaseInput;
  readinessScore: number;
  missingFields: string[];
  canRunAnalysis: boolean;
};

function short(v: string): string {
  const t = (v || "").trim();
  if (!t) return "—";
  return t.length > 80 ? `${t.slice(0, 77)}...` : t;
}

export function CaseDraftCard({ draft, readinessScore, missingFields, canRunAnalysis }: Props) {
  return (
    <div className="card" style={{ padding: "0.95rem", marginBottom: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", alignItems: "center" }}>
        <h4 style={{ margin: 0 }}>Case Draft (Extracted Facts)</h4>
        <span className={`status-chip ${canRunAnalysis ? "ready" : ""}`}>Readiness: {readinessScore}%</span>
      </div>
      <div style={{ marginTop: "0.5rem", height: 8, background: "#e2e8f0", borderRadius: 999, overflow: "hidden" }}>
        <div style={{ width: `${Math.min(100, Math.max(0, readinessScore))}%`, height: "100%", background: canRunAnalysis ? "#16a34a" : "#1d4ed8" }} />
      </div>

      <div style={{ marginTop: "0.65rem", display: "grid", gap: "0.45rem" }}>
        <div className="soft-block"><strong style={{ fontSize: "0.82rem" }}>Business:</strong> <span className="muted">{short(draft.business_model)}</span></div>
        <div className="soft-block"><strong style={{ fontSize: "0.82rem" }}>Revenue:</strong> <span className="muted">{short(`${draft.revenue_amount} ${draft.revenue_period}`.trim())}</span></div>
        <div className="soft-block"><strong style={{ fontSize: "0.82rem" }}>Profit/Loss:</strong> <span className="muted">{short(`${draft.profit_or_loss_type} ${draft.profit_or_loss_amount}`.trim())}</span></div>
        <div className="soft-block"><strong style={{ fontSize: "0.82rem" }}>Constraints:</strong> <span className="muted">{short(`Headcount ${draft.headcount}; Cash ${draft.cash_reserves}; Runway ${draft.runway}`)}</span></div>
        <div className="soft-block"><strong style={{ fontSize: "0.82rem" }}>Problem:</strong> <span className="muted">{short(draft.main_problem)}</span></div>
        <div className="soft-block"><strong style={{ fontSize: "0.82rem" }}>Goal:</strong> <span className="muted">{short(draft.main_goal)}</span></div>
      </div>
      {missingFields.length > 0 && (
        <div style={{ marginTop: "0.65rem" }} className="muted">
          Missing: {missingFields.join(", ")}
        </div>
      )}
    </div>
  );
}
