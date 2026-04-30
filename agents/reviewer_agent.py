"""
Reviewer agent (senior partner / QA synthesis).

Phase 6: loads prompts/reviewer_prompt.md, sends intake plus finance, operations,
and strategy outputs to OpenAI, and maps the JSON into the standard six fields
plus priority_order (schemas.agent_output.reviewer_report).

If the API fails or the response is not valid JSON, falls back to a deterministic
mock and prints a warning.
"""

from __future__ import annotations

import json
import time

from schemas.agent_output import clarification_answer, reviewer_clarification_plan, reviewer_report
from services.openai_client import generate_agent_response
from utils.consulting_json import (
    REVIEWER_JSON_SHAPE_INSTRUCTION,
    parse_reviewer_model_json,
    reviewer_report_from_parsed,
)
from utils.prompt_loader import load_prompt

# Nudges synthesis across all four workstreams without echoing a single agent.
_REVIEWER_USER_ADDENDUM = """
Task discipline for this response:
- You have four JSON inputs: intake (facts/frame), finance, operations, strategy. Synthesize them like a senior partner closing a steering meeting.
- Resolve tensions explicitly (e.g., cash vs growth, cuts vs service); do not list each agent in parallel paragraphs.
- Findings should integrate themes across workstreams; avoid copying one agent's bullets wholesale.
- Recommendations and priority_order must be actionable, sequenced, and grounded in the shared case—name trade-offs where needed.
- priority_order: 5–10 short imperative lines, most urgent first, mixing finance, ops, and strategy levers as one integrated plan.
"""

_ALLOWED_TARGETS = {"finance", "operations", "strategy"}
_GENERIC_QUESTION_STEMS = (
    "can you elaborate",
    "what do you think",
    "please explain",
    "tell me more",
    "any thoughts",
)
_HIGH_LEVERAGE_TERMS = (
    "cut",
    "protect",
    "primary",
    "secondary",
    "not do",
    "not-do",
    "sequence",
    "first",
    "tradeoff",
)


def _take(field: str, output: dict, default: list[str]) -> list[str]:
    value = output.get(field, default)
    return value if isinstance(value, list) else default


def _json_block(label: str, payload: dict) -> str:
    return f"{label} (JSON):\n{json.dumps(payload, ensure_ascii=False, indent=2)}"


def _parse_json_object(raw: str) -> dict[str, object]:
    text = (raw or "").strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(text[start : end + 1])
                return obj if isinstance(obj, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _limit_clarification_plan(plan: dict[str, object]) -> dict[str, object]:
    raw_q = plan.get("clarification_questions")
    if not isinstance(raw_q, list):
        raw_q = []
    bounded: list[dict[str, str]] = []
    seen_questions: set[str] = set()
    for item in raw_q:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target_agent", "")).strip().lower()
        question = str(item.get("question", "")).strip()
        q_norm = " ".join(question.lower().split())
        if target not in _ALLOWED_TARGETS or not question:
            continue
        if any(stem in q_norm for stem in _GENERIC_QUESTION_STEMS):
            continue
        if not any(term in q_norm for term in _HIGH_LEVERAGE_TERMS):
            continue
        if q_norm in seen_questions:
            continue
        seen_questions.add(q_norm)
        bounded.append({"target_agent": target, "question": question})
        if len(bounded) >= 3:
            break
    top_conflicts = _take("top_conflicts", plan, [])
    top_uncertainties = _take("top_uncertainties", plan, [])
    if not top_conflicts:
        top_conflicts = ["Primary conflict: cash-preserving spend cuts versus protecting growth and retention drivers."]
    if not top_uncertainties:
        top_uncertainties = ["Primary uncertainty: whether deterioration is mainly acquisition efficiency, retention execution, or operating reliability."]
    return reviewer_clarification_plan(
        needs_follow_up=bool(plan.get("needs_follow_up", False)) and len(bounded) > 0,
        top_conflicts=top_conflicts[:2],
        top_uncertainties=top_uncertainties[:2],
        clarification_questions=bounded,
    )


def _mock_reviewer_pass1(
    intake_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
) -> dict[str, object]:
    _ = intake_output
    _ = operations_output
    _ = strategy_output
    finance_recs = " ".join(_take("recommendations", finance_output, [])).lower()
    conflicts = [
        "Finance may push faster spend cuts while strategy may want to protect high-quality growth channels."
    ]
    uncertainties = [
        "Whether retention weakness is primarily acquisition-quality driven or operational/service driven."
    ]
    questions: list[dict[str, str]] = []
    if "cut" in finance_recs or "freeze" in finance_recs:
        questions.append(
            {
                "target_agent": "finance",
                "question": "If spend must be reduced, what should be cut first and what must be protected?",
            }
        )
        questions.append(
            {
                "target_agent": "operations",
                "question": "How likely are service/inventory issues to be driving retention weakness versus pure commercial factors?",
            }
        )
        questions.append(
            {
                "target_agent": "strategy",
                "question": "Which channels or segments should be protected even under profitability-focused cuts?",
            }
        )
    return reviewer_clarification_plan(
        needs_follow_up=len(questions) > 0,
        top_conflicts=conflicts,
        top_uncertainties=uncertainties,
        clarification_questions=questions[:3],
    )


def _mock_reviewer_report(
    intake_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
) -> dict:
    """Deterministic fallback if OpenAI is unavailable."""
    int_rec = _take("recommendations", intake_output, [])
    fin_rec = _take("recommendations", finance_output, [])
    ops_rec = _take("recommendations", operations_output, [])
    strat_rec = _take("recommendations", strategy_output, [])

    summary = (
        "Across workstreams, the story is consistent: liquidity and margin discipline must "
        "come first, while commercial controls and strategic focus prevent savings and "
        "restructuring from leaking back out through discounting and complexity. "
        "The highest-risk gap is executing pricing and retention fixes without a clear cash guardrail. "
        "(Mock reviewer: OpenAI unavailable.)"
    )

    findings = [
        "Intake frames urgency and facts; finance, operations, and strategy should be read as one narrative, not three silos.",
        "Finance centers on cash runway and contribution margin transparency—this should anchor weekly leadership decisions.",
        "Operations highlights cost-to-serve and deal-desk leakage—quick wins exist if sales and ops align on rules.",
        "Strategy emphasizes ICP clarity and pricing architecture—necessary, but it will fail if near-term cash breaks first.",
        "No major contradiction between workstreams; sequencing and accountability are the main integration challenge.",
    ]

    risks = [
        "Too many parallel initiatives could overwhelm management and burn cash before any lever shows results.",
        "If discount governance is seen as 'sales blocking', adoption risk rises unless incentives are updated simultaneously.",
        "Weak segment profitability data could cause the team to protect low-value revenue while cutting high-value capacity.",
    ]

    recommendations = [
        "Name a single turnaround integrator (executive sponsor) who owns sequencing across finance, ops, and strategy.",
        "Adopt a 'fewer, bigger' initiative list: fund liquidity instrumentation first, then margin levers, then growth bets.",
        "Require every material recommendation to state its cash impact in 30/60/90 days and its owner.",
    ]

    assumptions = [
        "Intake, finance, operations, and strategy outputs reflect the same underlying case facts and time horizon.",
        "Leadership can enforce cross-functional decisions even when functions disagree on short-term revenue effects.",
    ]

    priority_order: list[str] = []
    priority_order.extend(int_rec[:1])
    priority_order.extend(fin_rec[:2])
    priority_order.extend(ops_rec[:2])
    priority_order.extend(strat_rec[:2])
    priority_order.append(
        "Governance: one executive integrator sequences work weekly and reports cash, margin, and initiative load on one page."
    )
    priority_order = priority_order[:8]

    if not priority_order:
        priority_order = [
            "Establish cash visibility and governance.",
            "Tighten commercial policy and discounting.",
            "Clarify target segments and simplify the offer.",
        ]

    return reviewer_report(
        agent_name="reviewer",
        summary=summary,
        findings=findings,
        risks=risks,
        recommendations=recommendations,
        assumptions=assumptions,
        priority_order=priority_order,
    )


def _has_explicit_tradeoff_resolution(report: dict) -> bool:
    summary = str(report.get("summary", "")).lower()
    findings = " ".join(_take("findings", report, [])).lower()
    recommendations = " ".join(_take("recommendations", report, [])).lower()
    blob = f"{summary} {findings} {recommendations}"
    has_resolution = any(
        term in blob
        for term in ("therefore", "so the decision", "resolved tradeoff", "primary", "secondary", "cut", "protect")
    )
    return has_resolution


def run_reviewer_pass1(
    intake_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
) -> dict[str, object]:
    """
    Reviewer pass 1: decide whether clarification is needed and ask up to 3 targeted questions.
    """
    instructions = (
        "You are reviewer pass 1 in a controlled consulting clarification process.\n"
        "Given intake, finance, operations, and strategy outputs, decide if targeted follow-up is needed for a decision-critical tradeoff.\n"
        "Return JSON ONLY with keys:\n"
        "- needs_follow_up (boolean)\n"
        "- top_conflicts (array of strings)\n"
        "- top_uncertainties (array of strings)\n"
        "- clarification_questions (array of objects: {target_agent, question})\n"
        "Rules:\n"
        "- Trigger follow-up ONLY when unresolved tension would change cut/protect/sequence decisions.\n"
        "- top_conflicts[0] should state the main tradeoff to resolve.\n"
        "- target_agent must be one of finance, operations, strategy.\n"
        "- ask 0 to 3 questions max.\n"
        "- questions must be short, high-leverage, and action-oriented.\n"
        "- each question should force a decision such as what to cut first, what to protect, what is primary vs secondary, or what not to do first.\n"
        "- never ask generic prompts like 'can you elaborate' or 'what do you think'.\n"
        "- if outputs are already aligned, set needs_follow_up=false and questions=[]."
    )
    user_message = (
        _json_block("Intake", intake_output)
        + "\n\n"
        + _json_block("Finance", finance_output)
        + "\n\n"
        + _json_block("Operations", operations_output)
        + "\n\n"
        + _json_block("Strategy", strategy_output)
    )
    t0 = time.perf_counter()
    try:
        raw = generate_agent_response(instructions=instructions, user_input=user_message)
    except Exception:
        print(f"[timing] reviewer_pass1 elapsed_ms={int((time.perf_counter() - t0) * 1000)} fallback=mock")
        return _mock_reviewer_pass1(intake_output, finance_output, operations_output, strategy_output)
    parsed = _parse_json_object(raw)
    if not parsed:
        print(f"[timing] reviewer_pass1 elapsed_ms={int((time.perf_counter() - t0) * 1000)} fallback=mock")
        return _mock_reviewer_pass1(intake_output, finance_output, operations_output, strategy_output)
    print(f"[timing] reviewer_pass1 elapsed_ms={int((time.perf_counter() - t0) * 1000)}")
    return _limit_clarification_plan(parsed)


def run_reviewer_final_with_clarifications(
    intake_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
    clarification_answers: list[dict[str, object]] | None = None,
) -> dict:
    """
    Reviewer pass 2: integrate all workstreams and explicit clarifications into final synthesis.

    Inputs: standard_report dicts from intake, finance, operations, and strategy.
    Output: same keys as standard_report plus priority_order.
    """
    clarifications = clarification_answers or []
    markdown_instructions = load_prompt("prompts/reviewer_prompt.md").strip()
    system_instruction = (
        markdown_instructions + "\n\n" + REVIEWER_JSON_SHAPE_INSTRUCTION.strip()
    ).strip()

    user_message = (
        "Use these outputs to produce your final integrated JSON response.\n\n"
        + _json_block("Intake (case framing)", intake_output)
        + "\n\n"
        + _json_block("Finance", finance_output)
        + "\n\n"
        + _json_block("Operations", operations_output)
        + "\n\n"
        + _json_block("Strategy", strategy_output)
        + "\n\n"
        + _json_block("Clarification answers", {"answers": clarifications})
        + "\n\n"
        + _REVIEWER_USER_ADDENDUM.strip()
        + "\n"
        + "Explicitly resolve tradeoffs and disagreements using clarification answers where provided.\n"
        + "State what to cut, protect, and test in priority_order.\n"
        + "In summary/findings, explicitly state: what finance got right, what operations got right, what strategy got right, and the final resolved decision."
        + "\n\nProduce the JSON object described in your instructions."
    )

    t0 = time.perf_counter()
    try:
        raw_text = generate_agent_response(
            instructions=system_instruction,
            user_input=user_message,
        )
    except Exception as exc:
        print(f"Reviewer agent OpenAI failed: {exc}")
        print("Using fallback mock reviewer output.")
        print(f"[timing] reviewer_pass2 elapsed_ms={int((time.perf_counter() - t0) * 1000)} fallback=mock")
        return _mock_reviewer_report(
            intake_output, finance_output, operations_output, strategy_output
        )

    if not raw_text:
        print("Reviewer agent OpenAI returned empty text.")
        print("Using fallback mock reviewer output.")
        print(f"[timing] reviewer_pass2 elapsed_ms={int((time.perf_counter() - t0) * 1000)} fallback=mock")
        return _mock_reviewer_report(
            intake_output, finance_output, operations_output, strategy_output
        )

    try:
        obj = parse_reviewer_model_json(raw_text)
        out = reviewer_report_from_parsed(obj, "reviewer")
        if not _has_explicit_tradeoff_resolution(out):
            raise ValueError("Reviewer synthesis missing explicit tradeoff resolution.")
        print(f"[timing] reviewer_pass2 elapsed_ms={int((time.perf_counter() - t0) * 1000)}")
        return out
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Reviewer agent could not parse OpenAI response: {exc}")
        print("Using fallback mock reviewer output.")
        print(f"[timing] reviewer_pass2 elapsed_ms={int((time.perf_counter() - t0) * 1000)} fallback=mock")
        return _mock_reviewer_report(
            intake_output, finance_output, operations_output, strategy_output
        )


def run_reviewer_agent(
    intake_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
) -> dict:
    """
    Backward-compatible single-call reviewer wrapper.
    """
    return run_reviewer_final_with_clarifications(
        intake_output, finance_output, operations_output, strategy_output, clarification_answers=[]
    )


def build_clarification_answer(agent_name: str, lines: list[str]) -> dict[str, object]:
    return clarification_answer(agent_name=agent_name, answer=lines[:4])
