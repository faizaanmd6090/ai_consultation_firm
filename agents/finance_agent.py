"""
Finance agent (CFO / corporate finance lens).

Phase 5: loads prompts/finance_prompt.md, sends the intake case brief to OpenAI,
and maps the JSON reply into the shared six-field shape from schemas.agent_output.

If the API fails or the response is not valid JSON, falls back to the Phase 1-style
mock finance report and prints a short warning.
"""

from __future__ import annotations

import json

from schemas.agent_output import standard_report
from services.openai_client import generate_agent_response
from utils.consulting_json import JSON_SHAPE_INSTRUCTION, parse_model_json, standard_report_from_parsed
from utils.prompt_loader import load_prompt

# Extra instructions sent with the case brief so the model stays in CFO/restructuring voice
# and does not echo intake or sound like the Strategy Agent.
_FINANCE_USER_ADDENDUM = """
Task discipline for this response:
- Ground every bullet in the case brief JSON above; cite its themes implicitly (do not invent facts).
- Open the summary with liquidity and margin/cost pressure (cash runway, gross or contribution margin, fixed vs variable load)—not a generic "company faces challenges" opener.
- Findings and recommendations must use turnaround finance vocabulary: runway, liquidity, margin bridge, contribution, fixed/variable cost, working capital, capital allocation, spend freezes, scenario cash views.
- Do not write a strategy or positioning memo. Mention ICP or positioning only if tied to margin, discounting, or cash (e.g., unprofitable segments).
- Do not paste the intake summary verbatim; translate into financial mechanisms.
"""


def _case_brief_block(case_brief: dict) -> str:
    """Serialize intake output so the model sees structured context."""
    return json.dumps(case_brief, ensure_ascii=False, indent=2)


def _mock_finance_report(case_brief: dict) -> dict:
    """Deterministic fallback (original mock) if OpenAI is unavailable."""
    _ = case_brief  # kept for API symmetry; mock text is generic turnaround finance

    summary = (
        "Financially, this profile is consistent with a 'high revenue, negative EBITDA' trap: "
        "losses persist because gross margin after discounts does not cover operating load, "
        "and cash is absorbed by working capital and/or fixed cost inertia. "
        "The immediate objective is to stabilize liquidity while building a credible bridge back to contribution margin. "
        "(Mock finance: OpenAI unavailable.)"
    )

    findings = [
        "Loss bridge (mock): gross margin is likely squeezed by discounting and/or rising variable unit costs versus flat realized price.",
        "Cash risk (mock): if collections slow or inventory/service inputs build, liquidity can worsen even if revenue looks stable on paper.",
        "Operating leverage (mock): fixed cost base may still reflect a 'growth era' footprint that is mis-sized for current throughput.",
        "Capital allocation (mock): without hard guardrails, opex and commercial spend can remain sticky while revenue quality declines.",
    ]

    risks = [
        "Covenant or lender pressure if cash turns negative for multiple months without a communicated remediation plan.",
        "Working capital 'false comfort' if revenue is supported by discounts—AR can look healthy while economics deteriorate.",
        "One-time cuts that harm revenue engines (e.g., slashing customer success) can extend the loss runway.",
    ]

    recommendations = [
        "Publish a 13-week cash flow forecast with scenarios (base / downside) and explicit actions tied to each variance.",
        "Build a weekly contribution margin view by segment: stop serving structurally negative customers unless there is a funded path to fix.",
        "Freeze non-critical hiring and discretionary spend; reclassify projects into 'fund / pause / kill' with one accountable owner.",
        "Negotiate pragmatic supplier terms (terms extension, staged payments) aligned to a credible turnaround timeline.",
    ]

    assumptions = [
        "Management accounts approximate economic reality (no large off-balance-sheet distortions).",
        "Revenue is roughly stable over the next 90 days unless the team changes pricing or mix deliberately.",
        "No immediate mandatory debt repayment spike beyond what management has already disclosed in the narrative.",
    ]

    return standard_report(
        agent_name="finance",
        summary=summary,
        findings=findings,
        risks=risks,
        recommendations=recommendations,
        assumptions=assumptions,
    )


def run_finance_agent(case_brief: dict) -> dict:
    """
    Produce a financial diagnosis from the intake case brief.

    Input: dict from run_intake_agent.
    Output: standard_report dict.
    """
    markdown_instructions = load_prompt("prompts/finance_prompt.md").strip()
    system_instruction = (
        markdown_instructions + "\n\n" + JSON_SHAPE_INSTRUCTION.strip()
    ).strip()

    user_message = (
        "Case brief from intake (JSON):\n"
        + _case_brief_block(case_brief)
        + "\n\n"
        + _FINANCE_USER_ADDENDUM.strip()
        + "\n\nProduce the JSON object described in your instructions."
    )

    try:
        raw_text = generate_agent_response(
            instructions=system_instruction,
            user_input=user_message,
        )
    except Exception as exc:
        print(f"Finance agent OpenAI failed: {exc}")
        print("Using fallback mock finance output.")
        return _mock_finance_report(case_brief)

    if not raw_text:
        print("Finance agent OpenAI returned empty text.")
        print("Using fallback mock finance output.")
        return _mock_finance_report(case_brief)

    try:
        obj = parse_model_json(raw_text)
        return standard_report_from_parsed(obj, "finance")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Finance agent could not parse OpenAI response: {exc}")
        print("Using fallback mock finance output.")
        return _mock_finance_report(case_brief)
