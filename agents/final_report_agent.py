"""
Founder-facing final report layer.

Takes outputs from intake, finance, operations, strategy, and reviewer,
and turns them into a calibrated CEO/founder report.

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
    "Core Problems",
    "Immediate Priorities",
    "Biggest Risks",
    "Missing Critical Data",
    "30/60/90 Day Action Plan",
    "Key Metrics to Watch",
]

_SECTION_ALIASES = {
    "top 3 to 5 core problems": "Core Problems",
    "core problems": "Core Problems",
    "missing data": "Missing Critical Data",
    "missing critical data": "Missing Critical Data",
}

_GENERIC_PATTERNS = (
    "improve efficiency",
    "reassess strategy",
    "reduce marketing spend",
    "optimize operations",
    "enhance performance",
    "take a holistic approach",
)

_VAGUE_VERBS = (
    "reassess",
    "optimize",
    "improve",
    "streamline",
    "enhance",
)

_DECISION_PREFIXES = ("STOP:", "TEST:", "KEEP:", "INVESTIGATE:")


def _normalize_line_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _looks_generic(text: str) -> bool:
    lowered = text.strip().lower()
    return any(pattern in lowered for pattern in _GENERIC_PATTERNS)


def _is_quantified(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "%",
            "weekly",
            "monthly",
            "days",
            "weeks",
            "months",
            "<",
            ">",
            " to ",
            "target range",
        )
    )


def _sharpen_generic_line(text: str, fallback: str) -> str:
    if not _looks_generic(text):
        return text
    if _is_quantified(text):
        return text
    return fallback


def _flatten_value_to_lines(value: object) -> list[str]:
    """Flatten nested model output values (dict/list/str) into readable lines."""
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


def _canonical_section_name(name: str) -> str:
    key = name.strip().lower()
    if key in _SECTION_ALIASES:
        return _SECTION_ALIASES[key]
    for canonical in _SECTION_ORDER:
        if key == canonical.lower():
            return canonical
    return name


def _pick_decision_prefix(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ("pause", "cut", "stop", "freeze", "ban", "cap")):
        return "STOP:"
    if any(w in lower for w in ("test", "pilot", "experiment", "try", "a/b")):
        return "TEST:"
    if any(w in lower for w in ("keep", "protect", "maintain", "double down")):
        return "KEEP:"
    return "INVESTIGATE:"


def _normalize_immediate_priorities(items: list[str]) -> list[str]:
    """
    Enforce ranked 1-5 priorities with STOP/TEST/KEEP/INVESTIGATE prefixes.
    """
    normalized: list[str] = []
    for raw in items:
        text = raw.strip().lstrip("-").strip()
        if not text:
            continue
        # Strip any leading numbering like "1)" or "1." or "1 -".
        text = re.sub(r"^\s*\d+\s*[\)\.\-:]\s*", "", text).strip()
        if not text:
            continue
        upper = text.upper()
        if upper.startswith(_DECISION_PREFIXES):
            normalized.append(text)
        else:
            normalized.append(f"{_pick_decision_prefix(text)} {text}")

    # Deduplicate (preserve order)
    seen: set[str] = set()
    deduped: list[str] = []
    for item in normalized:
        key = _normalize_line_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    # Exactly 5 items, keep most concrete first.
    deduped = deduped[:5]
    while len(deduped) < 5:
        deduped.append("INVESTIGATE: Identify the single biggest cost or churn driver, set a weekly metric, and decide keep/cut within 2 weeks.")

    # Add ranking numbers.
    ranked = [f"{idx+1}. {item}" for idx, item in enumerate(deduped)]
    return ranked


def _contains_vague_verb_without_detail(text: str) -> bool:
    lower = text.strip().lower()
    if not any(v in lower for v in _VAGUE_VERBS):
        return False
    # If it contains a concrete connector/metric, allow it.
    concrete_markers = (" if ", " within ", " by ", " using ", " cap ", " threshold", " target", " > ", " < ", "%", " for ")
    return not any(m in lower for m in concrete_markers)


def _normalize_metric_trigger_action(items: list[str]) -> list[str]:
    """
    Ensure each metric line reads as: Metric - Trigger - Action.
    """
    out: list[str] = []
    for raw in items:
        text = raw.strip().lstrip("-").strip()
        if not text:
            continue
        if " - " in text:
            parts = [p.strip() for p in text.split(" - ") if p.strip()]
            if len(parts) >= 3:
                out.append(f"{parts[0]} - {parts[1]} - {parts[2]}")
                continue
        # If the model gives "Metric: blah", convert to a trigger/action template.
        if ":" in text and text.count(":") == 1:
            metric, rest = [p.strip() for p in text.split(":", 1)]
            out.append(f"{metric} - If {rest} drifts against plan for 2 weeks - Reduce spend/scope and investigate driver")
            continue
        out.append(f"{text} - If off plan for 2 consecutive weeks - Investigate driver and adjust the next lever")

    # Keep concise
    return out[:8]


def _extract_section(parsed: dict, section: str) -> object | None:
    # Direct match first.
    if section in parsed:
        return parsed[section]
    # Case-insensitive + alias fallback.
    for key, value in parsed.items():
        if _canonical_section_name(str(key)) == section:
            return value
    return None


def _normalize_fact_hypothesis_prefix(section: str, item: str) -> str:
    text = item.strip()
    if not text:
        return text
    if section in ("Core Problems", "Biggest Risks"):
        lower = text.lower()
        if lower.startswith("fact:") or lower.startswith("hypothesis:"):
            return text
        # Default to hypothesis unless direct factual language is obvious.
        factual_markers = ("reported", "stated", "provided", "current", "actual", "fact:")
        if any(marker in lower for marker in factual_markers):
            return f"Fact: {text}"
        return f"Hypothesis: {text}"
    return text


def _render_306090(items: list[str]) -> list[str]:
    buckets: dict[str, list[str]] = {"30 Days": [], "60 Days": [], "90 Days": []}
    current = "30 Days"

    for item in items:
        stripped = item.strip().lstrip("-").strip()
        lower = stripped.lower()
        if lower.startswith("30 days"):
            current = "30 Days"
            remainder = stripped[len("30 days") :].lstrip(":").strip()
            if remainder:
                buckets[current].append(remainder)
            continue
        if lower.startswith("60 days"):
            current = "60 Days"
            remainder = stripped[len("60 days") :].lstrip(":").strip()
            if remainder:
                buckets[current].append(remainder)
            continue
        if lower.startswith("90 days"):
            current = "90 Days"
            remainder = stripped[len("90 days") :].lstrip(":").strip()
            if remainder:
                buckets[current].append(remainder)
            continue
        buckets[current].append(stripped)

    lines = ["30 Days", "60 Days", "90 Days"]
    out: list[str] = []
    for label in lines:
        out.append(label)
        section_items = buckets[label] or ["Define owner and measurable outcome for this phase."]
        # Strip any nested label artifacts.
        cleaned: list[str] = []
        for line in section_items:
            s = line.strip()
            s = re.sub(r"^(30|60|90)\s*days\s*:\s*", "", s, flags=re.IGNORECASE).strip()
            if s:
                cleaned.append(s)
        for line in cleaned[:5]:
            out.append(f"- {line}")
        out.append("")
    return out


def _format_model_report_text(raw_text: str) -> str:
    """Keep founder output readable even if the model returns JSON."""
    text = raw_text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    if not isinstance(parsed, dict):
        return text
    if "report" in parsed and isinstance(parsed["report"], dict):
        parsed = parsed["report"]

    sharpen_defaults = {
        "Immediate Priorities": "Set owner, weekly cadence, and a conditional target range for the next action.",
        "Biggest Risks": "Hypothesis: If execution slips for two consecutive weeks, cash and confidence risk increase quickly.",
        "Missing Critical Data": "Fact: Missing cohort retention, channel CAC/payback, and true gross margin by segment.",
        "Key Metrics to Watch": "Track weekly burn, runway weeks, CAC payback, gross margin by segment, and retention by cohort.",
    }

    seen_lines: set[str] = set()
    lines: list[str] = []
    for section in _SECTION_ORDER:
        value = _extract_section(parsed, section)
        if value is None:
            continue
        lines.append(section)
        section_items = _flatten_value_to_lines(value)
        if not section_items:
            lines.append("")
            continue

        cleaned_items: list[str] = []
        for item in section_items:
            calibrated = _normalize_fact_hypothesis_prefix(section, item)
            sharpened = _sharpen_generic_line(
                calibrated, sharpen_defaults.get(section, calibrated)
            ).strip()
            if not sharpened:
                continue
            key = _normalize_line_key(sharpened)
            if key in seen_lines:
                continue
            seen_lines.add(key)
            cleaned_items.append(sharpened)

        if section == "Immediate Priorities":
            # Guard vague verbs by forcing concrete decision prefixes.
            guarded: list[str] = []
            for item in cleaned_items:
                if _contains_vague_verb_without_detail(item):
                    guarded.append(
                        "INVESTIGATE: Convert this into a decision with a trigger (what to stop/test/keep and what threshold decides)."
                    )
                else:
                    guarded.append(item)
            for item in _normalize_immediate_priorities(guarded):
                lines.append(item)
            lines.append("")
            continue

        if section == "30/60/90 Day Action Plan":
            lines.extend(_render_306090(cleaned_items))
            continue

        if section == "Key Metrics to Watch":
            for item in _normalize_metric_trigger_action(cleaned_items):
                lines.append(f"- {item}")
            lines.append("")
            continue

        for item in cleaned_items[:6]:
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
        core_problems.append(f"Hypothesis: {finance_findings[0]}")
    if ops_findings:
        core_problems.append(f"Hypothesis: {ops_findings[0]}")
    if strategy_findings:
        core_problems.append(f"Hypothesis: {strategy_findings[0]}")
    if len(core_problems) < 3:
        for item in _take("findings", reviewer_output, []):
            core_problems.append(f"Hypothesis: {item}")
            if len(core_problems) >= 3:
                break

    immediate_priorities = review_priority[:4] or _take(
        "recommendations", reviewer_output, []
    )[:4]

    missing_data = [
        "Fact: Customer cohort retention and churn by segment are not explicitly provided.",
        "Fact: Channel-level CAC and payback are missing, so budget reallocation should stay conditional.",
        "Fact: Unit economics by product/service mix are incomplete, limiting confidence in hard cost or headcount targets.",
    ]

    d30 = [
        "Validate baseline numbers: weekly burn, runway, gross margin by segment, and current discount practices.",
        "Install a weekly control rhythm with owners; use target ranges and adjust only after two weeks of observed data.",
    ]
    d60 = [
        "Run pricing and offer tests with guardrails; keep changes reversible and measure conversion plus margin impact weekly.",
        "Launch retention experiments on highest-risk cohorts and track save-rate before scaling.",
    ]
    d90 = [
        "Scale only the levers that show repeatable improvement in margin, retention, or payback.",
        "Lock governance: conditional thresholds for discount approvals, channel spend shifts, and hiring decisions.",
    ]

    metrics = [
        "Weekly burn vs plan (target range, not a single hard point)",
        "Runway weeks under base and downside assumptions",
        "Gross/contribution margin by segment and offer",
        "CAC and payback by channel (conditional thresholds)",
        "Retention/churn by cohort and save-rate on at-risk accounts",
        "Discount rate and share of deals above approval threshold",
    ]

    lines: list[str] = []
    lines.append("Executive Summary")
    lines.append(
        "- Fact: "
        + (
            review_summary
            or "Current evidence indicates pressure on cash discipline, margin quality, and execution sequencing."
        )
    )
    lines.append(
        "- Hypothesis: Some root causes remain unverified because core operating and unit-economic data are incomplete."
    )
    lines.append("- (Fallback founder report: OpenAI unavailable.)")
    lines.append("")

    lines.append("Core Problems")
    for item in core_problems[:5]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("Immediate Priorities")
    for item in immediate_priorities:
        lines.append(
            "- "
            + _sharpen_generic_line(
                item,
                "Set owner, weekly cadence, and conditional target range before committing large irreversible moves.",
            )
        )
    lines.append("")

    lines.append("Biggest Risks")
    for item in review_risks[:4]:
        lines.append(f"- Hypothesis: {item}")
    lines.append("")

    lines.append("Missing Critical Data")
    for item in missing_data:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("30/60/90 Day Action Plan")
    lines.append("30 Days")
    for item in d30:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("60 Days")
    for item in d60:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("90 Days")
    for item in d90:
        lines.append(f"- {item}")
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
        + "- Separate facts from hypotheses using explicit prefixes.\n"
        + "- Include a Missing Critical Data section and note evidence limits.\n"
        + "- Use conditional or range-based numeric framing unless strongly supported by inputs.\n"
        + "- Avoid repeated bullets across sections.\n"
        + "- 30/60/90 plan must render exactly with clean labels: 30 Days, 60 Days, 90 Days.\n"
        + "- Immediate Priorities must be ranked 1-5 and each line must start with STOP/TEST/KEEP/INVESTIGATE.\n"
        + "- Key Metrics must be decision-oriented: Metric - Trigger - Action.\n"
        + "- Keep practical founder-level actions and concise language.\n"
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
