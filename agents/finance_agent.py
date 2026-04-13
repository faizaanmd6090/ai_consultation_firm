"""
Finance agent (CFO / corporate finance lens).

Diagnoses loss drivers, cash and working capital risks, and near-term financial
actions. Consumes the intake case brief dict (summary + findings).
Returns the shared six-field standard_report structure (mock for Phase 1–2).
"""

from __future__ import annotations

from agents._output import standard_report


def _brief_snippet(case_brief: dict, max_chars: int = 400) -> str:
    """Join intake fields into one line the mock can reference without being an LLM."""
    summary = str(case_brief.get("summary", "")).strip()
    findings = case_brief.get("findings") or []
    parts = [summary]
    for item in findings[:3]:
        parts.append(str(item))
    blob = " ".join(parts)
    return blob if len(blob) <= max_chars else blob[: max_chars - 3] + "..."


def run_finance_agent(case_brief: dict) -> dict:
    """
    Produce a mock financial diagnosis aligned with the intake brief.

    Input: dict from run_intake_agent (must include summary, findings).
    Output: standard_report dict.
    """
    _ = _brief_snippet(case_brief)  # reserved for future templating / LLM context

    summary = (
        "Financially, this profile is consistent with a 'high revenue, negative EBITDA' trap: "
        "losses persist because gross margin after discounts does not cover operating load, "
        "and cash is absorbed by working capital and/or fixed cost inertia. "
        "The immediate objective is to stabilize liquidity while building a credible bridge back to contribution margin."
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
