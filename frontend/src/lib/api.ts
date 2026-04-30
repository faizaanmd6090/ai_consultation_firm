import { MOCK_RESPONSE } from "@/lib/mockData";
import { normalizeCase } from "@/lib/intakeValidation";
import type {
  AgentInfoResponse,
  AnalyzeCaseRequest,
  AnalyzeCaseResponse,
  IntakeChatRequest,
  IntakeChatResponse,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const MOCK_MODE = (process.env.NEXT_PUBLIC_USE_MOCK ?? "true").toLowerCase() === "true";

function normalizeAnalyzeCaseResponse(raw: unknown): AnalyzeCaseResponse {
  const obj = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const founder_report = typeof obj.founder_report === "string" ? obj.founder_report : "";
  const agentsRaw = (obj.agents && typeof obj.agents === "object" ? obj.agents : {}) as Record<string, unknown>;
  const baseAgent = { agent_name: "", summary: "", findings: [], risks: [], recommendations: [], assumptions: [] as string[] };
  const agentOr = (name: string) => {
    const a = agentsRaw[name];
    if (!a || typeof a !== "object") return { ...baseAgent, agent_name: name };
    const src = a as Record<string, unknown>;
    return {
      agent_name: typeof src.agent_name === "string" ? src.agent_name : name,
      summary: typeof src.summary === "string" ? src.summary : "",
      findings: Array.isArray(src.findings) ? src.findings.map(String) : [],
      risks: Array.isArray(src.risks) ? src.risks.map(String) : [],
      recommendations: Array.isArray(src.recommendations) ? src.recommendations.map(String) : [],
      assumptions: Array.isArray(src.assumptions) ? src.assumptions.map(String) : [],
      priority_order: Array.isArray(src.priority_order) ? src.priority_order.map(String) : undefined,
    };
  };
  return {
    founder_report,
    agents: {
      intake: agentOr("intake"),
      finance: agentOr("finance"),
      operations: agentOr("operations"),
      strategy: agentOr("strategy"),
      review: agentOr("review"),
    },
    review_clarification_plan: obj.review_clarification_plan as AnalyzeCaseResponse["review_clarification_plan"],
    review_clarification_answers: Array.isArray(obj.review_clarification_answers) ? (obj.review_clarification_answers as AnalyzeCaseResponse["review_clarification_answers"]) : [],
  };
}

export async function intakeChat(payload: IntakeChatRequest): Promise<IntakeChatResponse> {
  if (MOCK_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    const nextSession = payload.session_id ?? crypto.randomUUID();
    const reply = "Thanks — I captured that. What is your current revenue figure (e.g. $2M ARR or 500k yearly)?";
    return {
      session_id: nextSession,
      assistant_message: reply,
      messages: [
        { role: "user", content: payload.user_message },
        { role: "assistant", content: reply },
      ],
      structured_case_draft: {
        company_name: "",
        industry: "",
        business_model: "DTC skincare company",
        revenue_amount: "",
        revenue_period: "",
        profit_or_loss_amount: "",
        profit_or_loss_type: "",
        gross_margin: "",
        headcount: "",
        marketing_spend: "",
        marketing_spend_period: "",
        cash_reserves: "",
        runway: "",
        main_problem: "",
        main_goal: "",
        extra_context: payload.user_message.slice(0, 220),
      },
      missing_fields: ["revenue_amount", "main_problem", "main_goal"],
      readiness_score: 35,
      can_run_analysis: false,
      state: "collecting_info",
      detected_intent: "add_context",
      last_follow_up_question: "What is your current revenue figure?",
      extracted_facts_summary: {
        business: {
          company_name: "Not yet provided",
          industry: "Not yet provided",
          business_model: "DTC skincare company",
        },
        financials: {
          revenue_amount: "Not yet provided",
          revenue_period: "Not yet provided",
          profit_or_loss_type: "Not yet provided",
          profit_or_loss_amount: "Not yet provided",
          marketing_spend: "Not yet provided",
          marketing_spend_period: "Not yet provided",
        },
        constraints: {
          headcount: "Not yet provided",
          cash_reserves: "Not yet provided",
          runway: "Not yet provided",
        },
        problem_goal: {
          main_problem: "Not yet provided",
          main_goal: "Not yet provided",
        },
        readiness_score: 35,
        missing_fields: ["revenue_amount", "main_problem", "main_goal"],
      },
      should_start_analysis: false,
    };
  }

  const response = await fetch(`${API_BASE_URL}/api/intake/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Intake chat failed (${response.status})`);
  }
  return (await response.json()) as IntakeChatResponse;
}

export async function getAgentInfo(): Promise<AgentInfoResponse> {
  if (MOCK_MODE) {
    return {
      agents: [
        { id: "intake", name: "Intake Agent", description: "Converts chat input into structured, analysis-ready business facts." },
        { id: "finance", name: "Finance Agent", description: "Evaluates cash dynamics, margin pressure, and unit economics." },
        { id: "operations", name: "Operations Agent", description: "Surfaces execution bottlenecks and process-level turnaround levers." },
        { id: "strategy", name: "Strategy Agent", description: "Prioritizes segment, positioning, and growth-direction tradeoffs." },
        { id: "review", name: "Reviewer Agent", description: "Integrates specialist output and resolves decision-critical conflicts." },
        { id: "founder_report", name: "Founder Report Layer", description: "Produces a concise founder brief with ranked, actionable calls." },
      ],
      orchestration: [
        "Founder describes company context, constraints, and goals in chat.",
        "Intake orchestration updates a structured case draft with confidence-aware extraction.",
        "System asks targeted follow-ups only for missing critical data.",
        "Finance, Operations, and Strategy agents run specialist analysis in parallel.",
        "Reviewer may trigger one controlled clarification round for key tradeoffs.",
        "Founder report returns ranked root causes, risks, cut/invest calls, and 30/60/90 priorities.",
      ],
    };
  }
  const response = await fetch(`${API_BASE_URL}/api/agent-info`);
  if (!response.ok) throw new Error(`Agent info failed (${response.status})`);
  return (await response.json()) as AgentInfoResponse;
}

export async function analyzeCase(payload: AnalyzeCaseRequest): Promise<AnalyzeCaseResponse> {
  const normalized: AnalyzeCaseRequest = payload.case
    ? {
        mode: payload.mode,
        case: normalizeCase(payload.mode, payload.case),
        session_id: payload.session_id,
      }
    : { mode: payload.mode, session_id: payload.session_id };

  if (MOCK_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    return MOCK_RESPONSE;
  }

  const response = await fetch(`${API_BASE_URL}/api/analyze-case`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(normalized),
  });

  if (!response.ok) {
    throw new Error(`Analysis failed (${response.status})`);
  }
  return normalizeAnalyzeCaseResponse(await response.json());
}
