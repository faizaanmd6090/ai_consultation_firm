export type IntakeMode = "quick" | "guided" | "detailed";

export type CaseInput = {
  company_name: string;
  industry: string;
  business_model: string;
  revenue_amount: string;
  revenue_period: string;
  profit_or_loss_amount: string;
  profit_or_loss_type: string;
  gross_margin: string;
  headcount: string;
  marketing_spend: string;
  marketing_spend_period: string;
  cash_reserves: string;
  runway: string;
  main_problem: string;
  main_goal: string;
  extra_context: string;
};

export type SessionState = "collecting_info" | "ready_to_analyze" | "analyzing" | "report_ready";
export type ChatIntent = "add_context" | "confirm_analysis" | "edit_case" | "switch_mode";

export type AgentOutput = {
  agent_name: string;
  summary: string;
  findings: string[];
  risks: string[];
  recommendations: string[];
  assumptions: string[];
  priority_order?: string[];
};

export type ClarificationQuestion = {
  target_agent: "finance" | "operations" | "strategy";
  question: string;
};

export type ReviewClarificationPlan = {
  needs_follow_up: boolean;
  top_conflicts: string[];
  top_uncertainties: string[];
  clarification_questions: ClarificationQuestion[];
};

export type ReviewClarificationAnswer = {
  agent_name: "finance" | "operations" | "strategy" | string;
  answer: string[];
};

export type AnalyzeCaseRequest = {
  mode: IntakeMode;
  case?: CaseInput;
  session_id?: string;
};

export type AnalyzeCaseResponse = {
  founder_report: string;
  agents: {
    intake: AgentOutput;
    finance: AgentOutput;
    operations: AgentOutput;
    strategy: AgentOutput;
    review: AgentOutput;
  };
  review_clarification_plan?: ReviewClarificationPlan;
  review_clarification_answers?: ReviewClarificationAnswer[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type IntakeChatRequest = {
  session_id?: string;
  mode: IntakeMode;
  user_message: string;
};

export type IntakeChatResponse = {
  session_id: string;
  assistant_message: string;
  messages: ChatMessage[];
  structured_case_draft: CaseInput;
  missing_fields: string[];
  readiness_score: number;
  can_run_analysis: boolean;
  state: SessionState;
  detected_intent: ChatIntent;
  last_follow_up_question: string;
  extracted_facts_summary: {
    business: Record<string, string>;
    financials: Record<string, string>;
    constraints: Record<string, string>;
    problem_goal: Record<string, string>;
    readiness_score: number;
    missing_fields: string[];
  };
  should_start_analysis: boolean;
};

export type AgentInfoResponse = {
  agents: Array<{ id: string; name: string; description: string }>;
  orchestration: string[];
};

export type FieldErrors = Partial<Record<keyof CaseInput, string>>;

export const EMPTY_CASE: CaseInput = {
  company_name: "",
  industry: "",
  business_model: "",
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
  extra_context: "",
};
