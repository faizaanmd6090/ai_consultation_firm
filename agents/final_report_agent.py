"""
Founder-facing final report layer.

Takes outputs from intake, finance, operations, strategy, and reviewer,
and turns them into a short CEO/founder report.

Primary path uses OpenAI for concise synthesis. If OpenAI fails or returns
empty content, falls back to a deterministic summary built from existing outputs.
"""

from __future__ import annotations

import json
import re

from services.openai_client import generate_agent_response
from utils.prompt_loader import load_prompt


def _json_block(label: str, payload: dict) -> str:
    return f"{label} (JSON):\n{json.dumps(payload, ensure_ascii=False, indent=2)}"


def _take(field: str, output: dict, default: list[str]) -> list[str]:
    value = output.get(field, default)
    return value if isinstance(value, list) else default


_SECTION_ORDER = [
    "Executive Summary",
    "Top 3 to 5 Core Problems",
    "Immediate Priorities",
    "Biggest Risks",
    "30/60/90 Day Action Plan",
    "Key Metrics to Watch",
]

_GENERIC_PATTERNS = (
    "improve efficiency",
    "reassess strategy",
    "reduce marketing spend",
    "optimize operations",
    "enhance performance",
    "take a holistic approach",
)


def _normalize_line_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _looks_generic(text: str) -> bool:
    lowered = text.strip().lower()
    return any(pattern in lowered for pattern in _GENERIC_PATTERNS)


def _is_quantified(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("%","weekly","monthly","days","weeks","months","<",">"," to ","-"))


def _sharpen_generic_line(text: str, fallback: str) -> str:
    if not _looks_generic(text):
        return text
    if _is_quantified(text):
        return text
    return fallback


def _flatten_value_to_lines(value: object) -> list[str]:
    """
    Flatten nested model output values (dict/list/str) into readable lines.
    """
    out: list[str] = []
    if isinstance(value, str):
        value_lines = [line.strip() for line in value.splitlines() if line.strip()]
        if value_lines and all(line.startswith("-") for line in value_lines):
            out.extend([line.lstrip("-").strip() for line in value_lines])
        else:
            out.extend(value_lines or [value.strip()])
        return [x for x in out if x]

    if isinstance(value, list):
        for item in value:
            out.extend(_flatten_value_to_lines(item))
        return [x for x in out if x]

    if isinstance(value, dict):
        for key, item in value.items():
            nested = _flatten_value_to_lines(item)
            if nested:
                out.append(f"{key}: {nested[0]}")
                out.extend(nested[1:])
            else:
                out.append(str(key).strip())
        return [x for x in out if x]

    if value is not None:
        return [str(value).strip()]
    return []


def _format_model_report_text(raw_text: str) -> str:
    """
    Keep founder output readable even if the model returns JSON.
    """
    text = raw_text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    if not isinstance(parsed, dict):
        return text
    if "report" in parsed and isinstance(parsed["report"], dict):
        parsed = parsed["report"]

    section_order = _SECTION_ORDER
    sharpen_defaults = {
        "Immediate Priorities": "Set weekly burn targets, cap discretionary spend, and run a weekly CAC/payback channel cut decision.",
        "Biggest Risks": "If burn remains above plan for two consecutive weeks, liquidity risk accelerates before fixes take hold.",
        "30/60/90 Day Action Plan": "Sequence actions by week with owners and measurable thresholds before scaling.",
        "Key Metrics to Watch": "Track weekly burn, CAC payback, gross margin, discount rate, and retention by cohort.",
    }

    seen_lines: set[str] = set()
    lines: list[str] = []
    for section in section_order:
        value = parsed.get(section)
        if value is None:
            numbered_key = next(
                (k for k in parsed.keys() if section.lower() in str(k).lower()), None
            )
            value = parsed.get(numbered_key) if numbered_key else None
        if value is None:
            continue
        lines.append(section)
        section_items: list[str] = []
        section_items.extend(_flatten_value_to_lines(value))

        if not section_items:
            lines.append("")
            continue

        cleaned_items: list[str] = []
        for item in section_items:
            sharpened = _sharpen_generic_line(
                item, sharpen_defaults.get(section, item)
            ).strip()
            if not sharpened:
                continue
            key = _normalize_line_key(sharpened)
            if key in seen_lines:
                continue
            seen_lines.add(key)
            cleaned_items.append(sharpened)

        for idx, item in enumerate(cleaned_items):
            if section == "30/60/90 Day Action Plan":
                if item.lower().startswith("30") or item.lower().startswith("60") or item.lower().startswith("90"):
                    lines.append(f"- {item}")
                elif idx == 0:
                    lines.append(f"- 30 Days: {item}")
                elif idx == 1:
                    lines.append(f"- 60 Days: {item}")
                else:
                    lines.append(f"- 90 Days: {item}")
            else:
                lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines).strip() or text


def _fallback_founder_report(
    intake_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
    reviewer_output: dict,
) -> str:
    """Deterministic fallback report if OpenAI is unavailable."""
    review_summary = str(reviewer_output.get("summary", "")).strip()
    review_risks = _take("risks", reviewer_output, [])
    review_priority = _take("priority_order", reviewer_output, [])

    finance_findings = _take("findings", finance_output, [])
    ops_findings = _take("findings", operations_output, [])
    strategy_findings = _take("findings", strategy_output, [])

    core_problems: list[str] = []
    if finance_findings:
        core_problems.append(finance_findings[0])
    if ops_findings:
        core_problems.append(ops_findings[0])
    if strategy_findings:
        core_problems.append(strategy_findings[0])
    if len(core_problems) < 3:
        core_problems.extend(
            _take("findings", reviewer_output, [])[: 3 - len(core_problems)]
        )

    immediate_priorities = review_priority[:5] or _take(
        "recommendations", reviewer_output, []
    )[:5]

    d30 = [
        "Install a weekly cash control room: set burn target, owner, and escalation trigger if burn is >10% above plan for 2 weeks.",
        "Run channel-level CAC/payback review; pause paid channels with payback above target range (for example >9-12 months).",
    ]
    d60 = [
        "Test pricing and offer redesign on highest-volume segments: reduce discount depth and track close-rate impact weekly.",
        "Launch retention experiments for at-risk cohorts (save offers, onboarding fixes, success calls) and publish weekly cohort retention.",
    ]
    d90 = [
        "Scale profitable channels and offers; reallocate budget from weak channels to high-conversion sources.",
        "Lock governance: discount approval thresholds, weekly margin bridge review, and monthly product/service mix decisions.",
    ]

    metrics = [
        "Weekly net burn vs plan (target range and variance trigger)",
        "Runway weeks at current burn and at committed plan burn",
        "CAC and payback by channel (review weekly; cut channels above target payback)",
        "Gross/contribution margin by segment and offer",
        "Retention/churn by cohort and save-rate on at-risk accounts",
        "Average discount rate and share of deals above discount threshold",
    ]

    lines: list[str] = []
    lines.append("Executive Summary")
    lines.append(
        "- "
        + (
            review_summary
            or "Leadership should prioritize cash stability, operational discipline, and focused growth execution."
        )
    )
    lines.append("- (Fallback founder report: OpenAI unavailable.)")
    lines.append("")

    lines.append("Top 3 to 5 Core Problems")
    for item in core_problems[:5]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("Immediate Priorities")
    for item in immediate_priorities[:4]:
        lines.append(f"- {_sharpen_generic_line(item, 'Set weekly targets, owners, and thresholds for each action so execution can be measured.')}")
    lines.append("- Set weekly burn, CAC payback, and discount-threshold targets; review in a single founder scorecard.")
    lines.append("")

    lines.append("Biggest Risks")
    for item in review_risks[:4]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("30/60/90 Day Action Plan")
    lines.append("- 30 Days:")
    for item in d30:
        lines.append(f"  - {item}")
    lines.append("- 60 Days:")
    for item in d60:
        lines.append(f"  - {item}")
    lines.append("- 90 Days:")
    for item in d90:
        lines.append(f"  - {item}")
    lines.append("")

    lines.append("Key Metrics to Watch")
    for item in metrics:
        lines.append(f"- {item}")

    return "\n".join(lines).strip()


def run_final_report_agent(
    intake_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
    reviewer_output: dict,
) -> str:
    """
    Build the concise founder-facing final report.

    Returns plain text with fixed sections for quick CEO review.
    """
    markdown_instructions = load_prompt("prompts/final_report_prompt.md").strip()

    user_message = (
        "Create one concise founder-facing report from these five agent outputs.\n\n"
        + _json_block("Intake", intake_output)
        + "\n\n"
        + _json_block("Finance", finance_output)
        + "\n\n"
        + _json_block("Operations", operations_output)
        + "\n\n"
        + _json_block("Strategy", strategy_output)
        + "\n\n"
        + _json_block("Reviewer", reviewer_output)
        + "\n\nQuality checklist:\n"
        + "- Avoid repeated bullets across sections.\n"
        + "- Use operator language and concrete actions.\n"
        + "- Prefer quantified targets/ranges/thresholds whenever input allows.\n"
        + "- 30/60/90 plan must be clearly sequenced with distinct actions.\n"
        + "- Include weekly metrics that a founder can track in one dashboard.\n"
        + "\nFocus on practical priorities and avoid repeating full raw details."
    )

    try:
        raw_text = generate_agent_response(
            instructions=markdown_instructions,
            user_input=user_message,
        )
    except Exception as exc:
        print(f"Final report OpenAI failed: {exc}")
        print("Using fallback founder report.")
        return _fallback_founder_report(
            intake_output,
            finance_output,
            operations_output,
            strategy_output,
            reviewer_output,
        )

    if not raw_text:
        print("Final report OpenAI returned empty text.")
        print("Using fallback founder report.")
        return _fallback_founder_report(
            intake_output,
            finance_output,
            operations_output,
            strategy_output,
            reviewer_output,
        )

    return _format_model_report_text(raw_text)
