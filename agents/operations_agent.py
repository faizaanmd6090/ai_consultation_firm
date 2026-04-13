"""
Operations agent (COO / lean operations lens).

Focuses on cost-to-serve, process waste, procurement, and service delivery
drivers of margin and retention. Consumes the intake case brief dict.
Returns the shared six-field standard_report structure (mock for Phase 1–2).
"""

from __future__ import annotations

from agents._output import standard_report


def run_operations_agent(case_brief: dict) -> dict:
    """
    Produce a mock operational diagnosis aligned with the intake brief.

    Input: dict from run_intake_agent.
    Output: standard_report dict.
    """
    findings_text = case_brief.get("findings") or []
    has_discount_story = any(
        "discount" in str(x).lower() for x in findings_text
    ) or any("discount" in str(case_brief.get("summary", "")).lower())

    summary = (
        "Operationally, aggressive discounting combined with retention pressure usually "
        "maps to service variability, fulfillment friction, or a SKU/customer mix that is "
        "too complex for the current operating model. "
        "The goal is quick structural cost removal without breaking the few journeys that create real margin."
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
