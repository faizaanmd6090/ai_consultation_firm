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
import time

from services.openai_client import generate_agent_response
from utils.prompt_loader import load_prompt


def _json_block(label: str, payload: dict) -> str:
    return f"{label} (JSON):\n{json.dumps(payload, ensure_ascii=False, indent=2)}"


def _take(field: str, output: dict, default: list[str]) -> list[str]:
    value = output.get(field, default)
    return value if isinstance(value, list) else default


def _safe_float_from_token(value: str) -> float | None:
    t = value.strip().lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)(?:\s*(k|m|b|%)\b)?", t)
    if not m:
        return None
    n = float(m.group(1))
    suffix = m.group(2)
    if suffix == "k":
        n *= 1_000
    elif suffix == "m":
        n *= 1_000_000
    elif suffix == "b":
        n *= 1_000_000_000
    return n


def _period_multiplier(period: str) -> float | None:
    p = period.strip().lower()
    if "annual" in p or "year" in p:
        return 1 / 12
    if "quarter" in p:
        return 1 / 3
    if "month" in p:
        return 1.0
    if "week" in p:
        return 52 / 12
    return None


def _extract_intake_fact(text: str, label: str) -> str:
    m = re.search(rf"(?im)^{re.escape(label)}:\s*(.+)$", text)
    return m.group(1).strip() if m else ""


def _build_economics_snapshot_from_case_text(case_text: str) -> dict[str, object]:
    """
    Lightweight deterministic economics preprocessing from labeled case narrative text.
    Returns rough metrics + assumptions/uncertainties for founder report grounding.
    """
    source = case_text or ""

    # Revenue: supports both "Revenue (annual): 4200000" and "Revenue: 4200000".
    revenue_raw = _extract_intake_fact(source, "Revenue")
    rev_period_raw = ""
    rev_m = re.search(r"(?im)^Revenue\s*\(([^)]+)\)\s*:\s*(.+)$", source)
    if rev_m:
        rev_period_raw = rev_m.group(1).strip()
        revenue_raw = rev_m.group(2).strip()

    profitability_raw = _extract_intake_fact(source, "Profitability")
    marketing_raw = _extract_intake_fact(source, "Marketing spend")
    marketing_period_raw = ""
    ms_m = re.search(r"(?im)^Marketing spend\s*\(([^)]+)\)\s*:\s*(.+)$", source)
    if ms_m:
        marketing_period_raw = ms_m.group(1).strip()
        marketing_raw = ms_m.group(2).strip()

    runway_raw = _extract_intake_fact(source, "Runway") or _extract_intake_fact(source, "Cash / runway")
    headcount_raw = _extract_intake_fact(source, "Headcount")
    margin_raw = _extract_intake_fact(source, "Gross margin")

    assumptions: list[str] = []
    uncertainties: list[str] = []
    metrics: dict[str, str] = {}

    revenue_value = _safe_float_from_token(revenue_raw) if revenue_raw else None
    period_mult = _period_multiplier(rev_period_raw or "annual")
    monthly_revenue: float | None = None
    if revenue_value is not None and period_mult is not None:
        monthly_revenue = revenue_value * period_mult
        metrics["monthly_revenue_estimate"] = f"{int(round(monthly_revenue))}"
        if not rev_period_raw:
            assumptions.append("Revenue period assumed annual because no explicit period was provided.")
    elif revenue_value is not None:
        uncertainties.append("Revenue period was unclear, so monthly conversion is uncertain.")

    margin_pct = None
    if margin_raw:
        margin_pct = _safe_float_from_token(margin_raw)
    else:
        gm = re.search(r"(?i)gross margin\D{0,8}(\d+(?:\.\d+)?)\s*%", source)
        if gm:
            margin_pct = float(gm.group(1))
    if margin_pct is not None:
        metrics["gross_margin_percent"] = f"{margin_pct:.1f}%".replace(".0%", "%")
    if monthly_revenue is not None and margin_pct is not None:
        gp = monthly_revenue * (margin_pct / 100.0)
        metrics["monthly_gross_profit_estimate"] = f"{int(round(gp))}"

    marketing_value = _safe_float_from_token(marketing_raw) if marketing_raw else None
    if marketing_value is not None:
        m_mult = _period_multiplier(marketing_period_raw or "monthly") or 1.0
        monthly_marketing = marketing_value * m_mult
        metrics["monthly_marketing_spend_estimate"] = f"{int(round(monthly_marketing))}"
        if marketing_period_raw and "month" not in marketing_period_raw.lower():
            assumptions.append(
                f"Marketing spend normalized to monthly using reported period: {marketing_period_raw}."
            )
        if monthly_revenue and monthly_revenue > 0:
            ratio = (monthly_marketing / monthly_revenue) * 100
            metrics["marketing_as_percent_of_monthly_revenue_estimate"] = f"{ratio:.1f}%"
    if metrics.get("monthly_gross_profit_estimate") and metrics.get("monthly_marketing_spend_estimate"):
        gp = float(metrics["monthly_gross_profit_estimate"])
        mk = float(metrics["monthly_marketing_spend_estimate"])
        metrics["monthly_gross_profit_minus_marketing_estimate"] = f"{int(round(gp - mk))}"

    loss_value = None
    profitability_period = ""
    if profitability_raw:
        loss_value = _safe_float_from_token(profitability_raw)
        if "loss" in profitability_raw.lower():
            metrics["profitability_direction"] = "loss"
        elif "profit" in profitability_raw.lower():
            metrics["profitability_direction"] = "profit"
        p_match = re.search(r"(weekly|monthly|quarterly|annual|yearly|per month|per year|per quarter)", profitability_raw, flags=re.I)
        profitability_period = p_match.group(1) if p_match else ""
    if loss_value is not None and metrics.get("profitability_direction") == "loss":
        pmult = _period_multiplier(profitability_period or "annual")
        if pmult is not None:
            burn = loss_value * pmult
            metrics["monthly_loss_or_burn_estimate"] = f"{int(round(burn))}"

    runway_months = None
    if runway_raw:
        r = re.search(r"(\d+(?:\.\d+)?)\s*(months?|weeks?)", runway_raw, flags=re.I)
        if r:
            runway_months = float(r.group(1))
            if "week" in r.group(2).lower():
                runway_months = runway_months / 4.345
            metrics["runway_months_estimate"] = f"{runway_months:.1f}".rstrip("0").rstrip(".")
    if runway_months is not None and metrics.get("monthly_loss_or_burn_estimate"):
        burn = float(metrics["monthly_loss_or_burn_estimate"])
        implied_cash = runway_months * burn
        metrics["implied_cash_buffer_estimate"] = f"{int(round(implied_cash))}"

    if headcount_raw:
        hc = re.search(r"\d+", headcount_raw)
        if hc:
            metrics["headcount_reported"] = hc.group(0)
            if monthly_revenue is not None:
                rev_per_emp = monthly_revenue / max(float(hc.group(0)), 1.0)
                metrics["monthly_revenue_per_employee_estimate"] = f"{int(round(rev_per_emp))}"

    if not metrics:
        uncertainties.append("Insufficient structured numeric signals to compute rough economics.")

    return {
        "metrics": metrics,
        "assumptions": assumptions,
        "uncertainties": uncertainties,
    }


_SECTION_ORDER = [
    "Executive Summary",
    "Rough Economics Snapshot",
    "Most Likely Root Causes (Ranked)",
    "Biggest Risks",
    "What to Cut Now",
    "What to Invest In Now",
    "What Not to Do",
    "30/60/90 Day Action Plan",
    "Weekly Metrics to Track",
    "Missing Critical Data",
]

_SECTION_ALIASES = {
    "core problems": "Most Likely Root Causes (Ranked)",
    "most likely root causes": "Most Likely Root Causes (Ranked)",
    "most likely root causes ranked": "Most Likely Root Causes (Ranked)",
    "immediate priorities": "What to Cut Now",
    "key metrics to watch": "Weekly Metrics to Track",
    "weekly metrics": "Weekly Metrics to Track",
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
_FORBIDDEN_OUTPUT_TOKENS = (
    "placeholder",
    "if (example)",
    "requires validation",
    "set a concrete action with owner and threshold",
)
_REQUIRED_SECTIONS = {
    "Executive Summary",
    "Rough Economics Snapshot",
    "Most Likely Root Causes (Ranked)",
    "Biggest Risks",
    "What to Cut Now",
    "What to Invest In Now",
    "What Not to Do",
    "30/60/90 Day Action Plan",
    "Weekly Metrics to Track",
    "Missing Critical Data",
}


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
    seen: set[str] = set()
    for raw in items:
        text = raw.strip().lstrip("-").strip()
        if not text:
            continue
        if " - " in text:
            parts = [p.strip() for p in text.split(" - ", 2) if p.strip()]
            if len(parts) >= 3:
                line = f"{parts[0]} - {parts[1]} - {parts[2]}"
                key = _normalize_line_key(line)
                if key not in seen:
                    seen.add(key)
                    out.append(line)
                continue
        # If the model gives "Metric: blah", convert to a trigger/action template.
        if ":" in text and text.count(":") == 1:
            metric, rest = [p.strip() for p in text.split(":", 1)]
            line = f"{metric} - Watch weekly; if {rest} worsens materially - Review drivers and adjust action"
            key = _normalize_line_key(line)
            if key not in seen:
                seen.add(key)
                out.append(line)
            continue
        line = f"{text} - Watch weekly; if trend worsens materially - Review driver and adjust plan"
        key = _normalize_line_key(line)
        if key not in seen:
            seen.add(key)
            out.append(line)

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


def _extract_sections_from_plain_text(text: str) -> dict[str, list[str]]:
    """
    Best-effort parser for malformed plain text when model does not return valid JSON.
    Keeps backend as source of truth by reconstructing canonical sections.
    """
    sections: dict[str, list[str]] = {name: [] for name in _SECTION_ORDER}
    current = "Executive Summary"
    lines = [ln.strip() for ln in _sanitize_founder_report_text(text).splitlines() if ln.strip()]
    for line in lines:
        header_candidate = _canonical_section_name(re.sub(r"^#+\s*", "", line).strip())
        if header_candidate in sections:
            current = header_candidate
            continue
        clean = re.sub(r"^\-\s*", "", line).strip()
        if re.fullmatch(r"[\{\}\[\]\",:]+", clean):
            continue
        sections[current].append(clean)
    return sections


def _normalize_fact_hypothesis_prefix(section: str, item: str) -> str:
    text = item.strip()
    if not text:
        return text
    if section in ("Executive Summary", "Biggest Risks"):
        lower = text.lower()
        if lower.startswith("fact:") or lower.startswith("hypothesis:"):
            return text
        return text
    if section == "Rough Economics Snapshot":
        lower = text.lower()
        if lower.startswith("fact:") or lower.startswith("hypothesis:"):
            return text
        if re.search(r"\d|%|=", text):
            return f"Fact: {text}"
        return text
    if section == "Missing Critical Data":
        lower = text.lower()
        if lower.startswith("fact:"):
            return text
        if lower.startswith("hypothesis:"):
            return text[len("hypothesis:") :].strip()
        return text
    return text


def _normalize_ranked_root_causes(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        text = raw.strip().lstrip("-").strip()
        text = re.sub(r"^\s*\d+\s*[\)\.\-:]\s*", "", text).strip()
        if not text:
            continue
        if " - " not in text:
            text = f"{text} - strongest near-term impact on cash efficiency"
        key = _normalize_line_key(text)
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= 5:
            break
    while len(out) < 3:
        out.append("Evidence gap to be validated - confidence limited by missing cohort and unit-economics detail")
    ranked = [f"{idx + 1}. {item}" for idx, item in enumerate(out[:5])]
    return ranked


def _normalize_operator_action_bullets(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for raw in items:
        text = raw.strip().lstrip("-").strip()
        if not text:
            continue
        if _contains_vague_verb_without_detail(text):
            # Drop vague filler instead of replacing with generic boilerplate.
            continue
        cleaned.append(text)
    return cleaned[:6]


def _collect_guided_recommendation_pool(
    reviewer_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
) -> list[str]:
    """
    Build a deterministic recommendation pool with reviewer-first priority.
    """
    weighted_sources = [
        _take("priority_order", reviewer_output, []),
        _take("recommendations", reviewer_output, []),
        _take("recommendations", finance_output, []),
        _take("recommendations", operations_output, []),
        _take("recommendations", strategy_output, []),
    ]
    out: list[str] = []
    seen: set[str] = set()
    for source in weighted_sources:
        for raw in source:
            text = str(raw).strip().lstrip("-").strip()
            text = re.sub(r"^\s*\d+\s*[\)\.\-:]\s*", "", text).strip()
            if not text:
                continue
            low = text.lower()
            if "no data provided" in low:
                continue
            if "define owner and measurable outcome for this phase" in low:
                continue
            if any(tok in low for tok in _FORBIDDEN_OUTPUT_TOKENS):
                continue
            if _contains_vague_verb_without_detail(text):
                continue
            key = _normalize_line_key(text)
            if key in seen:
                continue
            seen.add(key)
            out.append(text)
    return out


def _score_action_for_phase(text: str, phase: str) -> int:
    low = text.lower()
    score = 0
    if phase == "30 Days":
        if any(k in low for k in ("cut", "pause", "stop", "burn", "runway", "cac", "leak", "instrument", "dashboard", "weekly")):
            score += 4
        if any(k in low for k in ("retention", "onboarding", "pipeline", "sales cycle")):
            score += 1
    elif phase == "60 Days":
        if any(k in low for k in ("onboarding", "retention", "roll out", "implement", "validate", "segment", "handoff", "playbook", "pipeline")):
            score += 4
        if any(k in low for k in ("refine", "test", "experiment")):
            score += 2
        if any(k in low for k in ("scale", "institutionalize", "cadence", "lock in")):
            score -= 2
    else:  # 90 Days
        if any(k in low for k in ("scale", "governance", "cadence", "institutionalize", "standardize", "lock in", "team alignment")):
            score += 4
        if any(k in low for k in ("sustain", "operating rhythm", "sunset", "double down")):
            score += 2
    if re.search(r"\d|%|weekly|monthly|quarter", low):
        score += 1
    return score


def _actionify_for_phase(text: str, phase: str) -> str:
    t = text.strip().rstrip(".")
    if phase == "30 Days":
        if not any(v in t.lower() for v in ("cut", "pause", "stop", "audit", "cap", "install", "triage", "stabilize", "enforce", "reduce")):
            return f"Audit and control {t.lower()} with weekly owner accountability."
        return t
    if phase == "60 Days":
        if not any(v in t.lower() for v in ("launch", "roll out", "implement", "rework", "validate", "redesign")):
            return f"Implement and validate {t.lower()} with cohort-level measurement."
        return t
    if not any(v in t.lower() for v in ("scale", "institutionalize", "lock", "standardize", "align")):
        return f"Scale what worked from {t.lower()} and institutionalize weekly operating cadence."
    return t


def _build_guided_306090_from_recommendations(
    reviewer_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
) -> dict[str, list[str]]:
    pool = _collect_guided_recommendation_pool(
        reviewer_output,
        finance_output,
        operations_output,
        strategy_output,
    )
    buckets: dict[str, list[str]] = {"30 Days": [], "60 Days": [], "90 Days": []}
    phases = ("30 Days", "60 Days", "90 Days")

    for phase in phases:
        ranked = sorted(pool, key=lambda line: _score_action_for_phase(line, phase), reverse=True)
        for item in ranked:
            shaped = _actionify_for_phase(item, phase)
            if shaped in buckets[phase]:
                continue
            if _score_action_for_phase(shaped, phase) <= 0 and len(buckets[phase]) >= 2:
                continue
            buckets[phase].append(shaped)
            if len(buckets[phase]) >= 4:
                break

    # Strong deterministic minimum for Guided analysis-ready cases.
    if len(buckets["30 Days"]) < 2:
        buckets["30 Days"].extend([
            "Audit and cut lowest-ROI acquisition channels first; cap spend until CAC payback stabilizes.",
            "Install a weekly burn, CAC, onboarding activation, and pipeline-conversion control cadence with clear owners.",
        ])
    if len(buckets["60 Days"]) < 2:
        buckets["60 Days"].extend([
            "Launch retention and onboarding interventions for at-risk cohorts; validate impact on activation and churn.",
            "Rework pipeline-to-customer-success handoff and segment qualification to reduce sales-cycle leakage.",
        ])
    if len(buckets["90 Days"]) < 2:
        buckets["90 Days"].extend([
            "Scale only channels and segments with validated payback and expansion potential; reduce failed experiments.",
            "Institutionalize weekly operating governance across burn, CAC, retention, and expansion metrics.",
        ])
    for phase in phases:
        buckets[phase] = buckets[phase][:5]
    return buckets


def _render_306090(
    items: list[str],
    *,
    guided_buckets: dict[str, list[str]] | None = None,
    forbid_generic_fallback: bool = False,
) -> list[str]:
    buckets: dict[str, list[str]] = {"30 Days": [], "60 Days": [], "90 Days": []}
    current = "30 Days"

    for item in items:
        stripped = item.strip().lstrip("-").strip()
        lower = stripped.lower()
        if re.match(r"^(30\s*days?|day\s*30|30[-\s]*day)", lower):
            current = "30 Days"
            remainder = re.sub(r"^(30\s*days?|day\s*30|30[-\s]*day)\s*[:\-]?\s*", "", stripped, flags=re.I).strip()
            if remainder:
                buckets[current].append(remainder)
            continue
        if re.match(r"^(60\s*days?|day\s*60|60[-\s]*day)", lower):
            current = "60 Days"
            remainder = re.sub(r"^(60\s*days?|day\s*60|60[-\s]*day)\s*[:\-]?\s*", "", stripped, flags=re.I).strip()
            if remainder:
                buckets[current].append(remainder)
            continue
        if re.match(r"^(90\s*days?|day\s*90|90[-\s]*day)", lower):
            current = "90 Days"
            remainder = re.sub(r"^(90\s*days?|day\s*90|90[-\s]*day)\s*[:\-]?\s*", "", stripped, flags=re.I).strip()
            if remainder:
                buckets[current].append(remainder)
            continue
        buckets[current].append(stripped)

    lines = ["30 Days", "60 Days", "90 Days"]
    out: list[str] = []
    for label in lines:
        out.append(label)
        section_items = buckets[label]
        if not section_items and guided_buckets:
            section_items = guided_buckets.get(label, [])
        if not section_items:
            section_items = (
                ["Set one concrete action, owner, and weekly decision metric for this phase."]
                if forbid_generic_fallback
                else ["Define owner and measurable outcome for this phase."]
            )
        # Strip any nested label artifacts.
        cleaned: list[str] = []
        for line in section_items:
            s = line.strip()
            s = re.sub(r"^(30|60|90)\s*days\s*:\s*", "", s, flags=re.IGNORECASE).strip()
            low = s.lower()
            if low in {"no data provided.", "no data provided"}:
                continue
            if "define owner and measurable outcome for this phase" in low:
                continue
            if s:
                cleaned.append(s)
        if not cleaned and guided_buckets:
            cleaned = guided_buckets.get(label, [])
        for line in cleaned[:5]:
            out.append(f"- {line}")
        out.append("")
    return out


def _strip_trailing_json_artifact_lines(text: str) -> str:
    """
    Remove trailing standalone JSON-closing artifact lines like `]`, `}`, `],`, `},`.
    """
    lines = text.splitlines()
    while lines and re.fullmatch(r"\s*[\]\}\,]+\s*", lines[-1] or ""):
        lines.pop()
    return "\n".join(lines).rstrip()


def _extract_first_balanced_json_object(text: str) -> str | None:
    """
    Find first balanced {...} block in text, ignoring braces inside strings.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def _sanitize_founder_report_text(text: str) -> str:
    """
    Final defensive cleanup for hybrid outputs: remove trailing JSON-tail artifacts.
    """
    cleaned = _strip_trailing_json_artifact_lines(text.strip())
    lines = cleaned.splitlines()
    safe_lines: list[str] = []
    for line in lines:
        low = line.lower()
        if any(tok in low for tok in _FORBIDDEN_OUTPUT_TOKENS):
            continue
        if re.fullmatch(r"\s*[\{\}\[\]\",:]+\s*", line):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines).strip()


def _has_forbidden_output_tokens(text: str) -> bool:
    low = (text or "").lower()
    return any(tok in low for tok in _FORBIDDEN_OUTPUT_TOKENS)


def _looks_repetitive_or_dummy(text: str) -> bool:
    lines = [ln.strip().lower() for ln in text.splitlines() if ln.strip().startswith("-")]
    if not lines:
        return False
    return len(set(lines)) <= max(2, len(lines) // 2)


def _format_model_report_text(
    raw_text: str,
    *,
    mode: str = "guided",
    recommendation_context: dict[str, dict] | None = None,
) -> str:
    """Keep founder output readable even if the model returns JSON."""
    text = raw_text.strip()
    parsed: dict | None = None
    try:
        as_obj = json.loads(text)
        if isinstance(as_obj, dict):
            parsed = as_obj
    except json.JSONDecodeError:
        parsed = None

    if parsed is None:
        candidate = _extract_first_balanced_json_object(text)
        if candidate:
            try:
                as_obj = json.loads(candidate)
                if isinstance(as_obj, dict):
                    parsed = as_obj
            except json.JSONDecodeError:
                parsed = None

    if parsed is None:
        parsed = _extract_sections_from_plain_text(text)
    if "report" in parsed and isinstance(parsed["report"], dict):
        parsed = parsed["report"]

    sharpen_defaults = {
        "Rough Economics Snapshot": "Hypothesis: Use monthly revenue, gross margin, and spend ratios as rough operating estimates before committing large changes.",
        "Most Likely Root Causes (Ranked)": "Hypothesis: Marketing efficiency deterioration is likely the main root cause pending cohort-level validation.",
        "Biggest Risks": "Hypothesis: If execution slips for two consecutive weeks, cash and confidence risk increase quickly.",
        "What to Cut Now": "Stop low-ROI spend first with clear decision thresholds and owner accountability.",
        "What to Invest In Now": "Invest in highest payback retention and unit-economics instrumentation first.",
        "What Not to Do": "Do not cut high-signal growth channels blindly before validating payback and contribution.",
        "Missing Critical Data": "Fact: Missing cohort retention, channel CAC/payback, and true gross margin by segment.",
        "Weekly Metrics to Track": "Track weekly burn, runway weeks, CAC payback, gross margin by segment, and retention by cohort.",
    }

    guided_fallback_buckets: dict[str, list[str]] | None = None
    if mode == "guided" and recommendation_context:
        guided_fallback_buckets = _build_guided_306090_from_recommendations(
            recommendation_context.get("reviewer", {}),
            recommendation_context.get("finance", {}),
            recommendation_context.get("operations", {}),
            recommendation_context.get("strategy", {}),
        )

    lines: list[str] = []
    for section in _SECTION_ORDER:
        value = _extract_section(parsed, section)
        section_lines: list[str] = [section]
        section_items = _flatten_value_to_lines(value) if value is not None else []
        if not section_items and section in _REQUIRED_SECTIONS and section != "30/60/90 Day Action Plan":
            section_items = [sharpen_defaults.get(section, "No data provided.")]
        elif not section_items:
            continue

        seen_lines: set[str] = set()
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

        if section == "Most Likely Root Causes (Ranked)":
            for item in _normalize_ranked_root_causes(cleaned_items):
                section_lines.append(item)
            section_lines.append("")
            lines.extend(section_lines)
            continue

        if section in ("What to Cut Now", "What to Invest In Now", "What Not to Do"):
            normalized = _normalize_operator_action_bullets(cleaned_items)
            if not normalized:
                normalized = [sharpen_defaults.get(section, "Define one concrete action with owner.")]
            for item in normalized[:6]:
                section_lines.append(f"- {item}")
            section_lines.append("")
            lines.extend(section_lines)
            continue

        if section == "30/60/90 Day Action Plan":
            section_lines.extend(
                _render_306090(
                    cleaned_items,
                    guided_buckets=guided_fallback_buckets if mode == "guided" else None,
                    forbid_generic_fallback=(mode == "guided"),
                )
            )
            lines.extend(section_lines)
            continue

        if section == "Weekly Metrics to Track":
            normalized = _normalize_metric_trigger_action(cleaned_items)
            if not normalized:
                normalized = ["Cash burn - Watch weekly; if variance worsens materially - Review spend mix and corrective actions"]
            for item in normalized:
                section_lines.append(f"- {item}")
            section_lines.append("")
            lines.extend(section_lines)
            continue

        normalized_generic = cleaned_items[:6]
        if section == "Executive Summary":
            normalized_generic = cleaned_items[:5]
        if section == "Rough Economics Snapshot":
            normalized_generic = cleaned_items[:8]
        if section == "Missing Critical Data":
            normalized_generic = [x.replace("Hypothesis:", "").strip() for x in normalized_generic]
        if not normalized_generic and section in _REQUIRED_SECTIONS:
            normalized_generic = [sharpen_defaults.get(section, "No data provided.")]
        for item in normalized_generic:
            section_lines.append(f"- {item}")
        section_lines.append("")
        lines.extend(section_lines)

    formatted = "\n".join(lines).strip() or text
    return _sanitize_founder_report_text(formatted)


def _fallback_founder_report(
    intake_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
    reviewer_output: dict,
    *,
    case_text: str = "",
) -> str:
    """Deterministic fallback report if OpenAI is unavailable."""
    econ = _build_economics_snapshot_from_case_text(case_text)
    review_summary = str(reviewer_output.get("summary", "")).strip()
    review_risks = _take("risks", reviewer_output, [])
    review_recs = _take("recommendations", reviewer_output, [])

    finance_findings = _take("findings", finance_output, [])
    ops_findings = _take("findings", operations_output, [])
    strategy_findings = _take("findings", strategy_output, [])
    ranked_causes = _normalize_ranked_root_causes(
        [
            "Marketing efficiency deterioration - Why ranked: direct pressure on contribution and payback - Evidence: rising CAC and weaker paid performance",
            "Retention / repeat purchase weakness - Why ranked: compounds CAC pressure and lowers LTV - Evidence: repeat purchase decline noted in case",
            "Inventory planning inefficiency - Why ranked: traps cash and creates stockout revenue leakage - Evidence: slow-moving stock + best-seller stockouts",
            "Pricing / discount discipline gaps - Why ranked: likely secondary lever on margin quality - Evidence: profitability pressure despite growth",
            "Operating cost structure drag - Why ranked: relevant but likely not primary root cause - Evidence: losses persist while top-line grows",
        ]
    )

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
        "Scale only levers with repeatable margin, retention, or payback improvement for 4+ weeks.",
        "Lock governance thresholds for discount approvals, spend shifts, and hiring decisions.",
    ]

    cut_now = [
        "Pause underperforming paid social campaigns/ad sets and reallocate only to proven creatives/segments.",
        "Reduce spend on low-LTV acquisition channels until cohort payback is validated by channel.",
        "Stop future buys of slow-moving inventory; clear or bundle aged stock to free cash.",
        "Pause net-new SKU complexity that increases forecasting error and stockout risk.",
    ]
    invest_now = [
        "Retention CRM / lifecycle: win-back, replenishment flows, and time-to-2nd-purchase improvements.",
        "Cohort + channel profitability reporting (CAC, payback, MER, contribution) updated weekly.",
        "Hero SKU in-stock reliability (forecasting, safety stock, supplier lead-time discipline).",
        "Bundle/regimen merchandising to raise AOV and gross profit per new customer.",
    ]
    not_to_do = [
        "Do not apply blanket cuts to customer success or fulfillment before cohort margin analysis.",
        "Do not double down on paid spend without channel-level payback discipline.",
        "Do not treat pricing as the first lever without validating retention and acquisition mix economics.",
    ]
    metrics = _normalize_metric_trigger_action([
        "Paid CAC payback (weeks) - If above threshold for 2 weeks - Cut spend 15-25% and reallocate",
        "Gross margin % - If below floor for 2 weeks - adjust price/mix and discount controls",
        "Repeat purchase rate - If below target range - launch retention offers and lifecycle fixes",
        "Stockout rate on top SKUs - If above threshold - rebalance buying and safety stock",
        "Inventory days - If rising beyond threshold - reduce replenishment and clear slow movers",
        "Weekly burn vs plan - If variance breaches threshold - trigger cost and spend controls",
    ])

    lines: list[str] = []
    lines.append("Executive Summary")
    lines.append(
        "- Fact: "
        + (
            review_summary
            or "Current evidence indicates pressure on cash discipline, margin quality, and execution sequencing."
        )
    )
    lines.append("- Hypothesis: Biggest issue is marketing efficiency deterioration; secondary issue is retention and repeat purchase weakness.")
    lines.append(
        "- Hypothesis: Some root causes remain unverified because core operating and unit-economic data are incomplete."
    )
    lines.append("")

    lines.append("Rough Economics Snapshot")
    if isinstance(econ.get("metrics"), dict) and econ["metrics"]:
        for k, v in econ["metrics"].items():
            lines.append(f"- Fact: {k.replace('_', ' ')} = {v}")
    else:
        lines.append("- Hypothesis: Insufficient numeric inputs for a high-confidence economics snapshot.")
    for a in econ.get("assumptions", [])[:3]:
        lines.append(f"- Hypothesis: {a}")
    for u in econ.get("uncertainties", [])[:3]:
        lines.append(f"- Hypothesis: {u}")
    lines.append("")

    lines.append("Most Likely Root Causes (Ranked)")
    for item in ranked_causes:
        lines.append(item)
    lines.append("")

    lines.append("Biggest Risks")
    for item in review_risks[:4]:
        lines.append(f"- Hypothesis: {item}")
    if review_recs:
        lines.append(f"- Hypothesis: Execution sprawl risk if too many recommendations run in parallel ({len(review_recs)} active ideas).")
    lines.append("")

    lines.append("What to Cut Now")
    for item in cut_now:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("What to Invest In Now")
    for item in invest_now:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("What Not to Do")
    for item in not_to_do:
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

    lines.append("Weekly Metrics to Track")
    for item in metrics:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("Missing Critical Data")
    for item in missing_data:
        lines.append(f"- {item}")

    return _sanitize_founder_report_text("\n".join(lines).strip())


def run_final_report_agent(
    intake_output: dict,
    finance_output: dict,
    operations_output: dict,
    strategy_output: dict,
    reviewer_output: dict,
    *,
    case_text: str = "",
    mode: str = "guided",
) -> str:
    """
    Build the concise founder-facing final report.

    Returns plain text with fixed sections for quick CEO review.
    """
    markdown_instructions = load_prompt("prompts/final_report_prompt.md").strip()
    economics_snapshot = _build_economics_snapshot_from_case_text(case_text)

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
        + "\n\n"
        + (f"Raw labeled case facts (verbatim user-provided or structured intake):\n{case_text.strip()}\n\n" if case_text.strip() else "")
        + _json_block("Deterministic rough economics snapshot (use when available)", economics_snapshot)
        + "\n\nQuality checklist:\n"
        + "- Separate facts from hypotheses using explicit prefixes.\n"
        + "- Use deterministic economics snapshot when available; avoid inventing precision.\n"
        + "- Include explicit biggest issue and secondary issue judgments.\n"
        + "- Include decisive sections: What to Cut Now, What to Invest In Now, What Not to Do.\n"
        + "- Include a ranked root-cause diagnosis (1-5) with why and evidence.\n"
        + "- Avoid repeated bullets across sections.\n"
        + "- 30/60/90 plan must render exactly with clean labels: 30 Days, 60 Days, 90 Days.\n"
        + "- Weekly metrics must be decision-oriented: Metric - Trigger - Action.\n"
        + "- Keep practical founder-level actions and concise language.\n"
        + "\nFocus on practical priorities and avoid repeating full raw details."
    )

    t0 = time.perf_counter()
    for attempt in range(2):
        try:
            call_start = time.perf_counter()
            raw_text = generate_agent_response(
                instructions=markdown_instructions,
                user_input=user_message,
            )
            print(
                f"[timing] founder_report_model_call attempt={attempt + 1} "
                f"elapsed_ms={int((time.perf_counter() - call_start) * 1000)}"
            )
        except Exception as exc:
            print(f"Final report OpenAI failed: {exc}")
            raw_text = ""
        if raw_text:
            formatted = _sanitize_founder_report_text(
                _format_model_report_text(
                    raw_text,
                    mode=mode,
                    recommendation_context={
                        "reviewer": reviewer_output,
                        "finance": finance_output,
                        "operations": operations_output,
                        "strategy": strategy_output,
                    },
                )
            )
            if not _has_forbidden_output_tokens(formatted) and not _looks_repetitive_or_dummy(formatted):
                print(f"[timing] founder_report_total elapsed_ms={int((time.perf_counter() - t0) * 1000)}")
                return formatted
        if attempt == 0:
            user_message += (
                "\n\nRETRY QUALITY GATE:\n"
                "- Remove any instructional/template phrasing.\n"
                "- Do not include words like placeholder, example, or requires validation.\n"
                "- Resolve tradeoffs decisively and avoid repeated generic bullets.\n"
            )

    print("Using fallback founder report after quality gate failure.")
    fallback = _fallback_founder_report(
        intake_output,
        finance_output,
        operations_output,
        strategy_output,
        reviewer_output,
        case_text=case_text,
    )
    print(f"[timing] founder_report_total elapsed_ms={int((time.perf_counter() - t0) * 1000)}")
    return _sanitize_founder_report_text(fallback)
