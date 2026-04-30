"""
Operations agent (COO / lean operations lens).

Phase 6: loads prompts/operations_prompt.md, sends the intake case brief to OpenAI,
and maps the JSON reply into the shared six-field shape from schemas.agent_output.

Focuses on cost-to-serve, process waste, procurement, and service delivery—not
corporate finance modeling or market strategy. If the API fails or the response
is not valid JSON, falls back to a deterministic mock and prints a warning.
"""

from __future__ import annotations

import json

from schemas.agent_output import standard_report
from services.openai_client import generate_agent_response
from utils.consulting_json import JSON_SHAPE_INSTRUCTION, parse_model_json, standard_report_from_parsed
from utils.prompt_loader import load_prompt

# Keeps the model in an operational voice and out of finance/strategy territory.
_OPERATIONS_USER_ADDENDUM = """
Task discipline for this response:
- Ground every bullet in the case brief JSON above; do not invent facts.
- Write like a COO or head of operations: throughput, SLAs, fulfillment, procurement, supplier terms, capacity, queues, rework, cost-to-serve, SKU/customer mix complexity, order-to-cash friction.
- Do not produce a CFO-style liquidity or runway memo. Mention cash only when tied to working capital, payables, or inventory/service inputs.
- Do not produce a strategy or positioning memo. Mention segments or pricing only when tied to operational complexity, discount execution at the deal desk, or delivery promises.
- Do not paste the intake summary verbatim; translate into operating mechanisms and process levers.
"""


def _case_brief_block(case_brief: dict) -> str:
    """Serialize intake output so the model sees structured context."""
    return json.dumps(case_brief, ensure_ascii=False, indent=2)


def _mock_operations_report(case_brief: dict) -> dict:
    """Deterministic fallback if OpenAI is unavailable."""
    findings_text = case_brief.get("findings") or []
    has_discount_story = any(
        "discount" in str(x).lower() for x in findings_text
    ) or ("discount" in str(case_brief.get("summary", "")).lower())

    summary = (
        "Operationally, aggressive discounting combined with retention pressure usually "
        "maps to service variability, fulfillment friction, or a SKU/customer mix that is "
        "too complex for the current operating model. "
        "The goal is quick structural cost removal without breaking the few journeys that create real margin. "
        "(Mock operations: OpenAI unavailable.)"
    )

    findings = [
        "Cost-to-serve likely varies widely by customer/SKU, but reporting may hide 'hero' accounts subsidizing unprofitable volume.",
        "Retention drops often correlate with delivery failures, onboarding gaps, or support backlog—not only product gaps.",
        "Discounting can become a habit in sales workflows when targets are revenue-weighted rather than margin- and cash-weighted.",
        "Procurement and network costs may have crept up via small vendor additions and low visibility tail spend.",
    ]
    if has_discount_story:
        findings.append(
            "Commercial 'leakage' (ad hoc discounts, waived fees) is a prime candidate for controls without waiting for a full ERP overhaul."
        )

    risks = [
        "Blanket cost cuts can worsen churn if cuts hit frontline delivery capacity in high-value segments.",
        "Complexity reduction (SKU routes, policies) can stall if functions disagree on definitions of 'strategic' customers.",
        "If operations fixes are not paired with pricing discipline, savings can be given away at the deal desk immediately.",
    ]

    recommendations = [
        "Run a 30-day 'order-to-cash' diagnostic: top failure modes driving credits, rework, refunds, and late delivery.",
        "Institute deal-desk governance: discount thresholds, approval tiers, and post-close margin checks on the largest contracts.",
        "Identify top 20% of customers by margin and protect their service levels explicitly while simplifying the long tail.",
        "Launch a procurement quick win: re-bid top categories, consolidate vendors, and enforce purchase order discipline.",
    ]

    assumptions = [
        "Operational data (tickets, SLA breaches, shipment/lead times) is available at least at an aggregate level.",
        "Sales and operations can align on a small set of non-negotiable service standards within two weeks.",
    ]

    return standard_report(
        agent_name="operations",
        summary=summary,
        findings=findings,
        risks=risks,
        recommendations=recommendations,
        assumptions=assumptions,
    )


def run_operations_agent(case_brief: dict) -> dict:
    """
    Produce an operational diagnosis from the intake case brief.

    Input: dict from run_intake_agent.
    Output: standard_report dict.
    """
    markdown_instructions = load_prompt("prompts/operations_prompt.md").strip()
    system_instruction = (
        markdown_instructions + "\n\n" + JSON_SHAPE_INSTRUCTION.strip()
    ).strip()

    user_message = (
        "Case brief from intake (JSON):\n"
        + _case_brief_block(case_brief)
        + "\n\n"
        + _OPERATIONS_USER_ADDENDUM.strip()
        + "\n\nProduce the JSON object described in your instructions."
    )

    try:
        raw_text = generate_agent_response(
            instructions=system_instruction,
            user_input=user_message,
        )
    except Exception as exc:
        print(f"Operations agent OpenAI failed: {exc}")
        print("Using fallback mock operations output.")
        return _mock_operations_report(case_brief)

    if not raw_text:
        print("Operations agent OpenAI returned empty text.")
        print("Using fallback mock operations output.")
        return _mock_operations_report(case_brief)

    try:
        obj = parse_model_json(raw_text)
        return standard_report_from_parsed(obj, "operations")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Operations agent could not parse OpenAI response: {exc}")
        print("Using fallback mock operations output.")
        return _mock_operations_report(case_brief)


def run_operations_clarification(case_brief: dict, prior_output: dict, question: str) -> list[str]:
    """
    Return a short, targeted clarification answer (2-4 bullets), not a full re-analysis.
    """
    instructions = (
        "You are the Operations specialist in a reviewer-led clarification round.\n"
        "Answer ONLY the assigned question.\n"
        "Return JSON only: {\"answer\": [\"...\", \"...\"]}\n"
        "Rules: 2-4 short bullets, operations-only, execution-focused.\n"
        "Do not re-analyze the full case. Focus on delivery risk, inventory/service reliability, and execution sequencing."
    )
    user_input = (
        "Case brief:\n"
        + _case_brief_block(case_brief)
        + "\n\nPrior operations output:\n"
        + _case_brief_block(prior_output)
        + "\n\nQuestion:\n"
        + question.strip()
    )
    q_terms = [tok for tok in question.lower().replace("/", " ").split() if len(tok) > 3]
    try:
        raw = generate_agent_response(instructions=instructions, user_input=user_input)
        text = raw.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            parsed = json.loads(text[start : end + 1]) if start >= 0 and end > start else {}
        if isinstance(parsed, dict) and isinstance(parsed.get("answer"), list):
            out = [str(x).strip() for x in parsed["answer"] if str(x).strip()]
            out = [x for x in out if "placeholder" not in x.lower() and "example" not in x.lower()]
            out = [x for x in out if any(t in x.lower() for t in q_terms[:6]) or any(k in x.lower() for k in ("inventory", "service", "stockout", "fulfillment", "retention"))]
            if len(out) >= 2:
                return out[:4]
    except Exception:
        pass
    q = question.lower()
    if "protect" in q:
        return [
            "Protect hero-SKU availability and fulfillment reliability for high-repeat cohorts.",
            "Protect frontline service capacity that directly prevents churn and refund leakage.",
        ]
    if "not" in q and "first" in q:
        return [
            "Do not start by cutting fulfillment or support headcount tied to retention-critical flows.",
            "Do not broaden SKU/catalog complexity before forecast accuracy and in-stock stability improve.",
        ]
    return [
        "Inventory and service instability can directly suppress repeat purchase and retention quality.",
        "Prioritize hero-SKU in-stock reliability before expansion projects or added SKU complexity.",
        "Avoid cuts that reduce fulfillment and service reliability for high-value cohorts.",
    ]
