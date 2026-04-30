"use client";

import { visualForAgent } from "@/lib/agentVisuals";

type AgentInfo = { id: string; name: string; description: string };

type Props = {
  agents: AgentInfo[];
};

export function AgentInfoPanel({ agents }: Props) {
  return (
    <div className="card" style={{ padding: "0.95rem", marginBottom: "0.75rem" }}>
      <h4 className="section-heading">Meet the Agents</h4>
      {agents.map((a) => (
        <div key={a.id} className="soft-block" style={{ marginBottom: "0.55rem" }}>
          <div className="panel-title-row">
            <strong style={{ fontSize: "0.9rem" }}>{visualForAgent(a.id).icon} {a.name}</strong>
            <span className="tag">{visualForAgent(a.id).roleTag}</span>
          </div>
          <div className="muted" style={{ fontSize: "0.84rem" }}>{a.description}</div>
        </div>
      ))}
    </div>
  );
}
