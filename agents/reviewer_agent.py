"""
Reviewer agent (senior partner / QA synthesis).

Reads finance, operations, and strategy outputs and produces an integrated view.
Returns the standard six fields plus priority_order (mock for Phase 1–2).
"""

from __future__ import annotations

from agents._output import reviewer_report


def _take(field: str, output: dict, default: list[str]) -> list[str]:
    value = output.get(field, default)
    return value if isinstance(value, list) else default


def run_reviewer_agent(
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
) -> dict:
    """
    Integrate the three workstreams and set an execution priority list.

    Inputs: standard_report dicts from finance, operations, and strategy agents.
    Output: same keys as standard_report plus priority_order.
    """
    fin_rec = _take("recommendations", finance_output, [])
    ops_rec = _take("recommendations", operations_output, [])
    strat_rec = _take("recommendations", strategy_output, [])

    summary = (
        "Across workstreams, the story is consistent: liquidity and margin discipline must "
        "come first, while commercial controls and strategic focus prevent savings and "
        "restructuring from leaking back out through discounting and complexity. "
        "The highest-risk gap is executing pricing and retention fixes without a clear cash guardrail."
    )

    findings = [
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
        "Finance, operations, and strategy outputs reflect the same underlying case facts and time horizon.",
        "Leadership can enforce cross-functional decisions even when functions disagree on short-term revenue effects.",
    ]

    # Build execution order from upstream recommendations (finance → ops → strategy), then governance.
    priority_order: list[str] = []
    priority_order.extend(fin_rec[:3])
    priority_order.extend(ops_rec[:2])
    priority_order.extend(strat_rec[:2])
    priority_order.append(
        "Governance: name one executive integrator to sequence work, resolve overlaps weekly, "
        "and report cash + margin + initiative load on a single page."
    )
    # Keep the list readable and within the 5–8 item guideline.
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
