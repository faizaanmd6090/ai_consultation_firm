"use client";

import { useMemo, useState } from "react";

import { ExtractedFactsTab } from "@/components/chat/ExtractedFactsTab";
import { visualForAgent } from "@/lib/agentVisuals";
import type { AnalyzeCaseResponse, AgentOutput, IntakeChatResponse } from "@/lib/types";

type Props = {
  data: AnalyzeCaseResponse | null;
  loading: boolean;
  error: string | null;
  onReset: () => void;
  extractedFacts: IntakeChatResponse["extracted_facts_summary"] | null;
  activeTab?: "founder" | "facts" | "agents";
  onTabChange?: (tab: "founder" | "facts" | "agents") => void;
};

function toLines(raw: string): string[] {
  return raw.split("\n").map((s) => s.trimEnd()).filter((s) => s.trim().length > 0);
}

function sanitizeFounderReportForDisplay(raw: string): string {
  const lines = raw.split("\n");
  const deny = ["placeholder", "requires validation", "if (example)", "set a concrete action with owner and threshold"];
  while (lines.length > 0 && /^\s*[\]\},]+\s*$/.test(lines[lines.length - 1] ?? "")) {
    lines.pop();
  }
  return lines
    .filter((line) => !deny.some((token) => line.toLowerCase().includes(token)))
    .filter((line) => !/^\s*[\{\}\[\]\",:]+\s*$/.test(line))
    .join("\n")
    .trim();
}

const KNOWN_SECTIONS = new Set([
  "Executive Summary",
  "Rough Economics Snapshot",
  "Most Likely Root Causes (Ranked)",
  "Biggest Risks",
  "What to Cut Now",
  "What to Invest In Now",
  "What Not to Do",
  "30/60/90 Day Action Plan",
  "Weekly Metrics to Track",
  "Missing Critical Data",
]);

function normalizeHeader(line: string): string {
  const cleaned = line.replace(/^#+\s*/, "").trim();
  for (const section of KNOWN_SECTIONS) {
    if (cleaned.toLowerCase() === section.toLowerCase()) return section;
  }
  return cleaned;
}

function parseFounderSections(raw: string): Array<{ title: string; lines: string[] }> {
  const cleaned = sanitizeFounderReportForDisplay(raw).replace(/\r\n/g, "\n");
  const out: Array<{ title: string; lines: string[] }> = [];
  let current: { title: string; lines: string[] } | null = null;
  for (const lineRaw of cleaned.split("\n")) {
    const line = lineRaw.trim();
    if (!line) continue;
    const maybeHeader = normalizeHeader(line);
    if (KNOWN_SECTIONS.has(maybeHeader)) {
      if (current && current.lines.length > 0) out.push(current);
      current = { title: maybeHeader, lines: [] };
      continue;
    }
    if (!current) current = { title: "Founder Report", lines: [] };
    current.lines.push(line.replace(/^-\s*/, ""));
  }
  if (current && current.lines.length > 0) out.push(current);
  // Safety net: if no canonical headers were found, reconstruct minimally
  // so the UI never shows one giant unstructured blob.
  const foundKnown = out.some((s) => KNOWN_SECTIONS.has(s.title));
  if (!foundKnown && out.length > 0) {
    const blobLines = out.flatMap((s) => s.lines);
    const summary = blobLines.slice(0, 5);
    const metrics = blobLines.filter((l) => /cac|retention|margin|burn|runway|inventory/i.test(l)).slice(0, 8);
    return [
      { title: "Executive Summary", lines: summary.length ? summary : ["Report generated with partial formatting recovery."] },
      { title: "Weekly Metrics to Track", lines: metrics.length ? metrics : ["Add weekly CAC, retention, gross margin, and burn tracking lines."] },
      { title: "Missing Critical Data", lines: ["Source report arrived malformed; some sections were reconstructed for readability."] },
    ];
  }
  return out;
}

function SectionCard({ title, lines }: { title: string; lines: string[] }) {
  const sectionIcon = title.includes("Risk") ? "⚠️" : title.includes("Metrics") ? "📊" : title.includes("Action") ? "🧭" : "▸";
  return (
    <article className="card fade-in" style={{ padding: "0.95rem", marginBottom: "0.75rem" }}>
      <h4 style={{ margin: "0 0 0.5rem" }}>{sectionIcon} {title}</h4>
      <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
        {lines.map((line, idx) => (
          <li key={`${title}-${idx}`} style={{ marginBottom: "0.3rem" }}>{line}</li>
        ))}
      </ul>
    </article>
  );
}

function AgentCard({ name, output }: { name: string; output: AgentOutput }) {
  const visual = visualForAgent(name);
  const sections: Array<[string, string[]]> = [
    ["Summary", [output.summary]],
    ["Findings", output.findings],
    ["Risks", output.risks],
    ["Recommendations", output.recommendations],
    ["Assumptions", output.assumptions],
  ];
  if (output.priority_order) {
    sections.push(["Priority Order", output.priority_order]);
  }

  return (
    <article className="card" style={{ padding: "0.85rem", marginBottom: "0.65rem" }}>
      <div className="panel-title-row">
        <h4 style={{ margin: 0, textTransform: "capitalize" }}>{visual.icon} {visual.name}</h4>
        <span className="tag">{visual.roleTag}</span>
      </div>
      {sections.map(([title, lines]) => (
        <div key={title} style={{ marginBottom: "0.5rem" }}>
          <strong style={{ fontSize: "0.9rem" }}>{title}</strong>
          <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1rem" }}>
            {lines.map((line, idx) => (
              <li key={`${name}-${title}-${idx}`} className="muted">{line}</li>
            ))}
          </ul>
        </div>
      ))}
    </article>
  );
}

function ClarificationRoundCard({ data }: { data: AnalyzeCaseResponse }) {
  const plan = data.review_clarification_plan;
  const answers = data.review_clarification_answers ?? [];
  if (!plan && answers.length === 0) return null;
  return (
    <article className="card" style={{ padding: "0.85rem", marginBottom: "0.65rem" }}>
      <h4 style={{ marginTop: 0 }}>🛡️ Clarification Round</h4>
      {plan && (
        <>
          <p className="muted" style={{ marginTop: 0 }}>
            {plan.needs_follow_up ? "Reviewer requested targeted follow-up." : "Reviewer proceeded without follow-up."}
          </p>
          {plan.top_conflicts.length > 0 && (
            <div style={{ marginBottom: "0.5rem" }}>
              <strong style={{ fontSize: "0.9rem" }}>Top Conflicts</strong>
              <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1rem" }}>
                {plan.top_conflicts.map((line, idx) => <li key={`conflict-${idx}`} className="muted">{line}</li>)}
              </ul>
            </div>
          )}
          {plan.clarification_questions.length > 0 && (
            <div style={{ marginBottom: "0.5rem" }}>
              <strong style={{ fontSize: "0.9rem" }}>Reviewer Questions</strong>
              <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1rem" }}>
                {plan.clarification_questions.map((q, idx) => (
                  <li key={`question-${idx}`} className="muted"><strong>{q.target_agent}:</strong> {q.question}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      {answers.length > 0 && (
        <div>
          <strong style={{ fontSize: "0.9rem" }}>Specialist Answers</strong>
          {answers.map((a, idx) => (
            <div key={`answer-${idx}`} style={{ marginTop: "0.35rem" }}>
              <div className="muted" style={{ textTransform: "capitalize" }}>{a.agent_name}</div>
              <ul style={{ margin: "0.2rem 0 0", paddingLeft: "1rem" }}>
                {a.answer.map((line, j) => <li key={`a-${idx}-${j}`} className="muted">{line}</li>)}
              </ul>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

export function ResultsPanel({ data, loading, error, onReset, extractedFacts, activeTab = "founder", onTabChange }: Props) {
  const [localTab, setLocalTab] = useState<"founder" | "facts" | "agents">(activeTab);
  const tab = onTabChange ? activeTab : localTab;
  const setTab = onTabChange ?? setLocalTab;

  const founderSections = useMemo(() => {
    if (!data?.founder_report) return [];
    return parseFounderSections(data.founder_report);
  }, [data?.founder_report]);

  async function copyReport() {
    if (!data?.founder_report) return;
    await navigator.clipboard.writeText(sanitizeFounderReportForDisplay(data.founder_report));
  }

  return (
    <section className="pane-scroll" style={{ maxHeight: "calc(100vh - 140px)" }}>
      <div className="surface-elevated" style={{ padding: "0.55rem", marginBottom: "0.65rem", display: "flex", gap: "0.45rem", flexWrap: "wrap", position: "sticky", top: 0, zIndex: 4 }}>
        <button className={`btn ${tab === "founder" ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab("founder")}>🧾 Founder Report</button>
        <button className={`btn ${tab === "facts" ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab("facts")}>📌 Extracted Facts</button>
        <button className={`btn ${tab === "agents" ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab("agents")}>🧠 Agent Outputs</button>
      </div>
      {!data && !loading && !error && (
        <div className="card fade-in" style={{ padding: "1rem" }}>
          <h3 style={{ marginTop: 0 }}>Founder Report</h3>
          <p className="muted" style={{ marginBottom: 0 }}>
            Submit intake details to generate your executive report. Detailed agent outputs appear below the founder report.
          </p>
        </div>
      )}

      {loading && (
        <div className="card fade-in" style={{ padding: "1rem" }}>
          <h3 style={{ marginTop: 0 }}>Running analysis...</h3>
          <p className="muted">Finance, operations, strategy, and reviewer agents are generating recommendations.</p>
        </div>
      )}

      {error && (
        <div className="card fade-in" style={{ padding: "1rem", borderColor: "#fecaca" }}>
          <h3 style={{ marginTop: 0, color: "#b91c1c" }}>Analysis failed</h3>
          <p className="muted">{error}</p>
        </div>
      )}

      {data && !loading && (
        <>
          {tab === "founder" && (
            <>
              <div className="card fade-in" style={{ padding: "1rem", marginBottom: "0.85rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.7rem", flexWrap: "wrap" }}>
                  <h3 style={{ margin: 0 }}>🧾 Founder Report</h3>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button className="btn btn-ghost" onClick={copyReport}>Copy founder report</button>
                    <button className="btn btn-primary" onClick={onReset}>Edit and rerun</button>
                  </div>
                </div>
              </div>
              {founderSections.map((section, idx) => (
                <SectionCard key={`${section.title}-${idx}`} title={section.title} lines={toLines(section.lines.join("\n"))} />
              ))}
            </>
          )}
          {tab === "facts" && <ExtractedFactsTab summary={extractedFacts} />}
          {tab === "agents" && (
            <div>
              <ClarificationRoundCard data={data} />
              {Object.entries(data.agents).map(([name, output]) => (
                <AgentCard key={name} name={name} output={output} />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
