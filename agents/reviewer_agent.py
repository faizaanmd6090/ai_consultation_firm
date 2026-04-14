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

from schemas.agent_output import reviewer_report
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


def _take(field: str, output: dict, default: list[str]) -> list[str]:
    value = output.get(field, default)
    return value if isinstance(value, list) else default


def _json_block(label: str, payload: dict) -> str:
    return f"{label} (JSON):\n{json.dumps(payload, ensure_ascii=False, indent=2)}"


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


def run_reviewer_agent(
    intake_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
) -> dict:
    """
    Integrate all workstreams and set an execution priority list.

    Inputs: standard_report dicts from intake, finance, operations, and strategy.
    Output: same keys as standard_report plus priority_order.
    """
    markdown_instructions = load_prompt("prompts/reviewer_prompt.md").strip()
    system_instruction = (
        markdown_instructions + "\n\n" + REVIEWER_JSON_SHAPE_INSTRUCTION.strip()
    ).strip()

    user_message = (
        "Use these four agent outputs to produce your integrated JSON response.\n\n"
        + _json_block("Intake (case framing)", intake_output)
        + "\n\n"
        + _json_block("Finance", finance_output)
        + "\n\n"
        + _json_block("Operations", operations_output)
        + "\n\n"
        + _json_block("Strategy", strategy_output)
        + "\n\n"
        + _REVIEWER_USER_ADDENDUM.strip()
        + "\n\nProduce the JSON object described in your instructions."
    )

    try:
        raw_text = generate_agent_response(
            instructions=system_instruction,
            user_input=user_message,
        )
    except Exception as exc:
        print(f"Reviewer agent OpenAI failed: {exc}")
        print("Using fallback mock reviewer output.")
        return _mock_reviewer_report(
            intake_output, finance_output, operations_output, strategy_output
        )

    if not raw_text:
        print("Reviewer agent OpenAI returned empty text.")
        print("Using fallback mock reviewer output.")
        return _mock_reviewer_report(
            intake_output, finance_output, operations_output, strategy_output
        )

    try:
        obj = parse_reviewer_model_json(raw_text)
        return reviewer_report_from_parsed(obj, "reviewer")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Reviewer agent could not parse OpenAI response: {exc}")
        print("Using fallback mock reviewer output.")
        return _mock_reviewer_report(
            intake_output, finance_output, operations_output, strategy_output
        )
