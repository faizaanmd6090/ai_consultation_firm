"""
Strategy agent (partner / corporate strategy lens).

Phase 5: loads prompts/strategy_prompt.md, sends the intake case brief to OpenAI,
and maps the JSON reply into the shared six-field shape from schemas.agent_output.

If the API fails or the response is not valid JSON, falls back to the Phase 1-style
mock strategy report and prints a short warning.
"""

from __future__ import annotations

import json

from schemas.agent_output import standard_report
from services.openai_client import generate_agent_response
from utils.consulting_json import JSON_SHAPE_INSTRUCTION, parse_model_json, standard_report_from_parsed
from utils.prompt_loader import load_prompt

# Extra instructions sent with the case brief so the model stays in commercial strategy voice
# and does not echo intake or sound like the Finance Agent.
_STRATEGY_USER_ADDENDUM = """
Task discipline for this response:
- Ground every bullet in the case brief JSON above; cite its themes implicitly (do not invent facts).
- Open the summary with pricing, positioning, segments, or competitive pressure—not liquidity or covenant detail.
- Findings and recommendations must emphasize commercial policy: pricing architecture, discount governance, ICP, segmentation, offer/mix, where to compete or exit, growth quality.
- Do not lead with 13-week cash forecasts, working-capital tactics, supplier terms, or covenant mechanics (that is finance-owned). Mention cash only when it supports a strategic pricing or portfolio choice.
- Do not paste the intake summary verbatim; translate into market and offer choices.
"""


def _case_brief_block(case_brief: dict) -> str:
    """Serialize intake output so the model sees structured context."""
    return json.dumps(case_brief, ensure_ascii=False, indent=2)


def _mock_strategy_report(case_brief: dict) -> dict:
    """Deterministic fallback (original mock) if OpenAI is unavailable."""
    summary_blob = str(case_brief.get("summary", "")).lower()

    summary = (
        "Strategically, the company appears caught between competing on price and needing "
        "differentiation that customers will pay for. "
        "When retention falls alongside rising discounts, the core question is whether the "
        "value proposition is unclear, undelivered, or simply not priced for sustainable economics. "
        "(Mock strategy: OpenAI unavailable.)"
    )

    findings = [
        "Share-of-wallet may be stable while profit share collapses—classic symptom of commoditization and weak pricing architecture.",
        "If discounts are used to 'buy' retention, the business may be retaining customers who are economically negative at the contribution line.",
        "Competitive intensity may be overstated internally: sometimes the bigger issue is offer sprawl and unclear ICP (ideal customer profile).",
        "A turnaround strategy must choose where not to play: shrinking the footprint can restore pricing power faster than 'more features'.",
    ]
    if "retention" in summary_blob or "customer" in summary_blob:
        findings.append(
            "Retention work should segment by gross margin cohort—otherwise the firm optimizes for revenue retention, not value retention."
        )

    risks = [
        "A vague 'premium positioning' push without operational proof points can increase CAC and worsen losses.",
        "If sales incentives remain revenue-first, any strategic price increase will be undermined in the field.",
        "Waiting for a 'big bang' new product delays the commercial policy fixes that could stabilize margins this quarter.",
    ]

    recommendations = [
        "Clarify ICP and 'must-win' use cases; align marketing, sales, and success narratives to those segments only.",
        "Redesign pricing: fewer SKUs/bundles, clearer value metrics, and explicit list-to-net discount rules tied to contract value.",
        "Establish a churn council: exit offers, win-back rules, and service recovery investments prioritized by margin potential.",
        "Define a 180-day portfolio roadmap: one flagship initiative funded by stopping two low-impact experiments.",
    ]

    assumptions = [
        "The underlying market is not in total structural decline; there is a reachable segment with willingness to pay.",
        "Leadership can enforce strategic focus trade-offs even under short-term revenue pressure.",
    ]

    return standard_report(
        agent_name="strategy",
        summary=summary,
        findings=findings,
        risks=risks,
        recommendations=recommendations,
        assumptions=assumptions,
    )


def run_strategy_agent(case_brief: dict) -> dict:
    """
    Produce a strategic diagnosis from the intake case brief.

    Input: dict from run_intake_agent.
    Output: standard_report dict.
    """
    markdown_instructions = load_prompt("prompts/strategy_prompt.md").strip()
    system_instruction = (
        markdown_instructions + "\n\n" + JSON_SHAPE_INSTRUCTION.strip()
    ).strip()

    user_message = (
        "Case brief from intake (JSON):\n"
        + _case_brief_block(case_brief)
        + "\n\n"
        + _STRATEGY_USER_ADDENDUM.strip()
        + "\n\nProduce the JSON object described in your instructions."
    )

    try:
        raw_text = generate_agent_response(
            instructions=system_instruction,
            user_input=user_message,
        )
    except Exception as exc:
        print(f"Strategy agent OpenAI failed: {exc}")
        print("Using fallback mock strategy output.")
        return _mock_strategy_report(case_brief)

    if not raw_text:
        print("Strategy agent OpenAI returned empty text.")
        print("Using fallback mock strategy output.")
        return _mock_strategy_report(case_brief)

    try:
        obj = parse_model_json(raw_text)
        return standard_report_from_parsed(obj, "strategy")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Strategy agent could not parse OpenAI response: {exc}")
        print("Using fallback mock strategy output.")
        return _mock_strategy_report(case_brief)
