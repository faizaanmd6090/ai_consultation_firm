export type AgentVisual = {
  id: string;
  name: string;
  roleTag: string;
  icon: string;
  description: string;
};

export const AGENT_VISUALS: Record<string, AgentVisual> = {
  intake: {
    id: "intake",
    name: "Intake Agent",
    roleTag: "intake",
    icon: "📋",
    description: "Captures and structures case facts from chat context.",
  },
  finance: {
    id: "finance",
    name: "Finance Agent",
    roleTag: "finance",
    icon: "📈",
    description: "Assesses economics, margin pressure, and cash trajectory.",
  },
  operations: {
    id: "operations",
    name: "Operations Agent",
    roleTag: "operations",
    icon: "⚙️",
    description: "Finds process bottlenecks and execution opportunities.",
  },
  strategy: {
    id: "strategy",
    name: "Strategy Agent",
    roleTag: "strategy",
    icon: "🎯",
    description: "Prioritizes market, segment, and growth direction choices.",
  },
  review: {
    id: "review",
    name: "Reviewer Agent",
    roleTag: "synthesis",
    icon: "🛡️",
    description: "Resolves cross-agent tradeoffs into one coherent plan.",
  },
  founder_report: {
    id: "founder_report",
    name: "Founder Report Layer",
    roleTag: "founder_report",
    icon: "🧾",
    description: "Delivers an executive-ready brief for founder decisions.",
  },
};

export function visualForAgent(agentId: string): AgentVisual {
  return AGENT_VISUALS[agentId] ?? {
    id: agentId,
    name: agentId,
    roleTag: "agent",
    icon: "◦",
    description: "Specialized analysis agent.",
  };
}
