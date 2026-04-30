"""
Single place that defines how every agent formats its return value (Phase 2).

Why this file exists:
- Every specialist agent returns the same six keys so `app.py` and future code
  can rely on one predictable dictionary shape.
- The reviewer adds one extra key: `priority_order`.
- Helpers here avoid copy-pasting the same dict literals in each agent file.

This module does not call APIs or read prompts; it only builds plain dicts.
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
    """
    Build the common six-field output for intake, finance, operations, and strategy.

    Returns a dict with keys: agent_name, summary, findings, risks, recommendations, assumptions.
    """
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
    """
    Same as standard_report, plus priority_order for the reviewer agent.

    Returns the six standard keys and also priority_order (ordered execution list).
    """
    out = standard_report(
        agent_name, summary, findings, risks, recommendations, assumptions
    )
    out["priority_order"] = list(priority_order)
    return out


def reviewer_clarification_plan(
    *,
    needs_follow_up: bool,
    top_conflicts: list[str],
    top_uncertainties: list[str],
    clarification_questions: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Structured reviewer pass-1 decision payload.

    clarification_questions items must be {"target_agent": "...", "question": "..."}.
    """
    return {
        "needs_follow_up": bool(needs_follow_up),
        "top_conflicts": list(top_conflicts),
        "top_uncertainties": list(top_uncertainties),
        "clarification_questions": list(clarification_questions),
    }


def clarification_answer(*, agent_name: str, answer: list[str]) -> dict[str, Any]:
    """Structured short clarification response from one specialist."""
    return {"agent_name": agent_name, "answer": list(answer)}
