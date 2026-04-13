"""
Intake agent (engagement manager / problem framing).

Reads the client's free-text problem and produces a structured case brief.
Every agent returns the same six keys: agent_name, summary, findings, risks,
recommendations, assumptions.
"""

from __future__ import annotations

from agents._output import standard_report


def run_intake_agent(client_problem: str) -> dict:
    """
    Structure the client narrative into a consulting-style case brief.

    Input: raw problem statement from the client (string).
    Output: standard_report dict (mock logic for Phase 1–2).
    """
    text = (client_problem or "").strip()
    lowered = text.lower()

    # Light keyword hints make mocks feel tied to the client's story (still deterministic).
    mentions_cash = "cash" in lowered
    mentions_margin = "margin" in lowered
    mentions_retention = "retention" in lowered or "customer" in lowered
    mentions_discount = "discount" in lowered

    summary = (
        "The client presents a turnaround situation: meaningful revenue scale coexists "
        "with sustained losses, eroding margins, and liquidity pressure. "
        "Commercial symptoms (pricing/discounting and retention) suggest both "
        "P&L and go-to-market issues that need coordinated finance, operations, "
        "and strategy workstreams."
    )
    if text:
        summary += " The narrative below anchors the case on the client's own words."

    findings = [
        "Revenue exists at scale, but profit conversion is weak—multi-year losses point to structural drivers, not a one-off shock.",
        "Rising costs and shrinking margins indicate either unit economics pressure, mix shift toward lower-margin revenue, or both.",
        "Cash constraints increase execution risk: turnaround actions must be sequenced with a clear liquidity guardrail.",
    ]
    if mentions_cash:
        findings.append(
            "Explicit cash runway concerns imply near-term decisions on payables, capex, and working capital need early attention."
        )
    if mentions_margin:
        findings.append(
            "Margin compression should be decomposed into price, variable cost, and fixed cost buckets to prioritize levers."
        )
    if mentions_retention or mentions_discount:
        findings.append(
            "Falling retention and aggressive discounting often signal weak pricing architecture and/or service delivery gaps."
        )

    risks = [
        "Without a single source of truth on cash and covenant headroom, the team may recommend actions the business cannot fund.",
        "If leadership treats this as purely a cost-cutting exercise, revenue quality can deteriorate further during the fix.",
        "Data gaps on customer-level profitability can mis-prioritize segments and worsen losses while appearing 'busy'.",
    ]

    recommendations = [
        "Issue a 2-week data request list: monthly P&L bridge, cash forecast, AR/AP aging, customer cohort retention, and discount policy.",
        "Stand up a weekly turnaround cadence: liquidity first, then margin levers, then growth reinvestment—no parallel unfunded initiatives.",
        "Define a baseline 'must-win' quarter: stop-loss rules on discounting and a short list of highest-value customer segments.",
    ]

    assumptions = [
        "Management can produce management accounts and a 13-week cash view within the next few business days.",
        "No material undisclosed litigation or regulatory freeze is blocking operational change.",
        "Revenue is not collapsing imminently; the primary near-term failure mode is liquidity and margin discipline.",
    ]

    return standard_report(
        agent_name="intake",
        summary=summary,
        findings=findings,
        risks=risks,
        recommendations=recommendations,
        assumptions=assumptions,
    )
