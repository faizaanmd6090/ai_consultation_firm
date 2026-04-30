"use client";

import type { IntakeChatResponse } from "@/lib/types";

type Props = {
  summary: IntakeChatResponse["extracted_facts_summary"] | null;
};

function Group({ title, values }: { title: string; values: Record<string, string> }) {
  return (
    <article className="card" style={{ padding: "0.8rem", marginBottom: "0.65rem" }}>
      <h4 style={{ marginTop: 0 }}>{title}</h4>
      <div className="info-grid">
        {Object.entries(values).map(([k, v]) => (
          <div key={k} className="soft-block" style={{ marginBottom: "0.35rem" }}>
            <strong style={{ fontSize: "0.85rem", textTransform: "capitalize" }}>{k.replaceAll("_", " ")}:</strong>{" "}
            <span className="muted" style={{ fontSize: "0.85rem" }}>{v || "Not yet provided"}</span>
          </div>
        ))}
      </div>
    </article>
  );
}

export function ExtractedFactsTab({ summary }: Props) {
  if (!summary) {
    return (
      <div className="card" style={{ padding: "0.8rem" }}>
        <p className="muted" style={{ margin: 0 }}>No extracted facts yet.</p>
      </div>
    );
  }
  return (
    <div>
      <div className="card" style={{ padding: "0.8rem", marginBottom: "0.65rem" }}>
        <strong>Readiness: {summary.readiness_score}%</strong>
        <div className="muted" style={{ marginTop: "0.3rem" }}>
          Missing: {summary.missing_fields.length ? summary.missing_fields.join(", ") : "None"}
        </div>
      </div>
      <Group title="Business" values={summary.business} />
      <Group title="Financials" values={summary.financials} />
      <Group title="Constraints" values={summary.constraints} />
      <Group title="Problem & Goal" values={summary.problem_goal} />
    </div>
  );
}
