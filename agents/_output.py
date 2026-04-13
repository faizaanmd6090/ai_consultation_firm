"""
Shared helpers for agent responses.

Every specialist agent returns the same keys so the pipeline and future API
code can treat outputs uniformly. The reviewer adds one extra field.
"""

from __future__ import annotations

from typing import Any


def standard_report(
    agent_name: str,
    summary: str,
    findings: list[str],
    risks: list[str],
    recommendations: list[str],
    assumptions: list[str],
) -> dict[str, Any]:
    """Build the common six-field dictionary all non-reviewer agents use."""
    return {
        "agent_name": agent_name,
        "summary": summary,
        "findings": list(findings),
        "risks": list(risks),
        "recommendations": list(recommendations),
        "assumptions": list(assumptions),
    }


def reviewer_report(
    agent_name: str,
    summary: str,
    findings: list[str],
    risks: list[str],
    recommendations: list[str],
    assumptions: list[str],
    priority_order: list[str],
) -> dict[str, Any]:
    """Same as standard_report plus priority_order for the reviewer agent."""
    out = standard_report(
        agent_name, summary, findings, risks, recommendations, assumptions
    )
    out["priority_order"] = list(priority_order)
    return out
