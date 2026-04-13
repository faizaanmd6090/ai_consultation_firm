"""
Strategy agent (partner / corporate strategy lens).

Frames market position, offer, pricing power, and business model choices.
Consumes the intake case brief dict.
Returns the shared six-field standard_report structure (mock for Phase 1–2).
"""

from __future__ import annotations

from agents._output import standard_report


def run_strategy_agent(case_brief: dict) -> dict:
    """
    Produce a mock strategic diagnosis aligned with the intake brief.

    Input: dict from run_intake_agent.
    Output: standard_report dict.
    """
    summary_blob = str(case_brief.get("summary", "")).lower()

    summary = (
        "Strategically, the company appears caught between competing on price and needing "
        "differentiation that customers will pay for. "
        "When retention falls alongside rising discounts, the core question is whether the "
        "value proposition is unclear, undelivered, or simply not priced for sustainable economics."
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
