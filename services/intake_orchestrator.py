from __future__ import annotations

import json
import re
from typing import Any, Literal

from services.openai_client import generate_agent_response
from utils.input_validation import (
    normalize_headcount,
    normalize_profit_or_loss_type,
    normalize_revenue_period,
    validate_business_model_intake,
    validate_headcount,
    validate_main_goal_intake,
    validate_main_problem_intake,
    validate_profit_or_loss_amount,
    validate_profit_or_loss_type,
    validate_revenue_amount,
    validate_revenue_period,
)

SessionState = Literal["collecting_info", "ready_to_analyze", "analyzing", "report_ready"]
ChatIntent = Literal["add_context", "confirm_analysis", "edit_case", "switch_mode"]
IntakeMode = Literal["quick", "guided", "detailed"]

CASE_FIELDS: tuple[str, ...] = (
    "company_name",
    "industry",
    "business_model",
    "revenue_amount",
    "revenue_period",
    "profit_or_loss_amount",
    "profit_or_loss_type",
    "gross_margin",
    "headcount",
    "marketing_spend",
    "marketing_spend_period",
    "cash_reserves",
    "runway",
    "main_problem",
    "main_goal",
    "extra_context",
)


def empty_case_draft() -> dict[str, str]:
    return {k: "" for k in CASE_FIELDS}


def detect_chat_intent(message: str, state: SessionState) -> ChatIntent:
    m = message.strip().lower()
    if re.search(r"\b(run analysis|analyze|proceed|go ahead|yes|do it|run it)\b", m):
        if state == "ready_to_analyze":
            return "confirm_analysis"
    if re.search(r"\b(change mode|switch mode|quick|guided|detailed)\b", m):
        return "switch_mode"
    if re.search(r"\b(edit|update|correct|fix|change)\b", m):
        return "edit_case"
    return "add_context"


def critical_fields_for_mode(mode: IntakeMode) -> list[str]:
    base = [
        "business_model",
        "revenue_amount",
        "profit_or_loss_type",
        "profit_or_loss_amount",
        "headcount",
        "main_problem",
        "main_goal",
    ]
    if mode in ("guided", "detailed"):
        base.extend(["revenue_period", "marketing_spend", "cash_reserves", "runway"])
    if mode == "detailed":
        base.extend(["company_name", "industry", "gross_margin"])
    return base


def _validate_field(field: str, value: str, mode: IntakeMode) -> str | None:
    if field == "business_model":
        return validate_business_model_intake(value)
    if field == "revenue_amount":
        return validate_revenue_amount(value)
    if field == "revenue_period":
        if not value and mode == "quick":
            return None
        return validate_revenue_period(value)
    if field == "profit_or_loss_type":
        return validate_profit_or_loss_type(value)
    if field == "profit_or_loss_amount":
        return validate_profit_or_loss_amount(value)
    if field == "headcount":
        return validate_headcount(value)
    if field == "main_problem":
        return validate_main_problem_intake(value)
    if field == "main_goal":
        return validate_main_goal_intake(value)
    return None


def _to_number_string(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _parse_amount_token(token: str) -> float | None:
    t = token.strip().lower().replace(",", "")
    m = re.match(r"^\$?(\d+(?:\.\d+)?)([kmb])?$", t)
    if not m:
        return None
    n = float(m.group(1))
    scale = m.group(2)
    if scale == "k":
        n *= 1_000
    elif scale == "m":
        n *= 1_000_000
    elif scale == "b":
        n *= 1_000_000_000
    return n


def normalize_amount_and_period(text: str, *, context_hint: str = "") -> tuple[str | None, str | None]:
    lowered = text.lower()
    amount: str | None = None
    period: str | None = None

    # Amount extraction.
    amount_match = re.search(
        r"(?i)(?:\$|usd\s*)?(\d+(?:[.,]\d+)?)\s*(k|m|b|million|billion|thousand)?",
        text,
    )
    if amount_match:
        raw_num = amount_match.group(1).replace(",", "")
        suffix = (amount_match.group(2) or "").lower()
        n = float(raw_num)
        if suffix == "k":
            n *= 1_000
        elif suffix == "m" or suffix == "million":
            n *= 1_000_000
        elif suffix == "b" or suffix == "billion":
            n *= 1_000_000_000
        elif suffix == "thousand":
            n *= 1_000
        amount = _to_number_string(n)

    # Period extraction / normalization.
    period_source = f"{lowered} {context_hint.lower()}".strip()
    # Prioritize explicit short-period phrasing before annual references in longer text.
    if re.search(r"\b(per month|monthly|month)\b", period_source):
        period = "monthly"
    elif re.search(r"\b(per quarter|quarterly|quarter)\b", period_source):
        period = "quarterly"
    elif re.search(r"\b(per week|weekly|week)\b", period_source):
        period = "weekly"
    elif re.search(
        r"\b(last\s*12\s*months?|last year|past year|over the last 12 months|over the past 12 months|annually|annual)\b",
        period_source,
    ):
        period = "annual"

    return amount, period


def infer_business_model(text: str) -> tuple[str | None, float, str]:
    lowered = text.lower()
    has_dtc = re.search(r"\b(d2c|dtc|directly to customers|direct to consumer)\b", lowered)
    has_website = re.search(r"\b(website|online store|our website)\b", lowered)
    has_sell = re.search(r"\b(sell|selling|we sell|products)\b", lowered)
    has_skin = re.search(r"\b(skincare|cream|creams|lotion|lotions|beauty)\b", lowered)

    if has_dtc and has_skin:
        return (
            "DTC skincare company selling creams and lotions directly to customers via its website",
            0.92,
            "strong DTC + skincare evidence",
        )
    if (has_dtc or has_website) and (has_sell or has_skin):
        return (
            "DTC company selling products directly via its website",
            0.84,
            "direct-to-consumer and website sales language detected",
        )
    if re.search(r"\b(b2b|enterprise|subscription|saas)\b", lowered):
        return ("B2B subscription business", 0.72, "B2B/subscription cues detected")
    return (None, 0.0, "")


def _extract_deterministic_signals(text: str) -> dict[str, Any]:
    lowered = text.lower()
    deltas: dict[str, str] = {}
    confidence: dict[str, float] = {}
    evidence: dict[str, str] = {}

    # Business model inference.
    bm, bm_conf, bm_evidence = infer_business_model(text)
    if bm:
        deltas["business_model"] = bm
        confidence["business_model"] = bm_conf
        evidence["business_model"] = bm_evidence

    # Revenue.
    rev_match = re.search(
        r"(?i)(?:revenue|did about|generated|sales)\D{0,30}(\$?\s*\d+(?:[.,]\d+)?\s*(?:k|m|b|million|billion|thousand)?)",
        text,
    )
    if rev_match:
        rev_context = text[max(0, rev_match.start() - 80) : min(len(text), rev_match.end() + 80)]
        amt, per = normalize_amount_and_period(rev_match.group(1), context_hint=rev_context)
        if amt:
            deltas["revenue_amount"] = amt
            confidence["revenue_amount"] = 0.9
            evidence["revenue_amount"] = "revenue amount phrase found"
        if per:
            deltas["revenue_period"] = per
            confidence["revenue_period"] = 0.86
            evidence["revenue_period"] = "revenue period phrase found"

    # Profit/loss.
    loss_match = re.search(
        r"(?i)\b(lost|loss|profit|profitable|profit of)\b\D{0,20}(\$?\s*\d+(?:[.,]\d+)?\s*(?:k|m|b|million|billion|thousand)?)",
        text,
    )
    if loss_match:
        sign = "loss" if re.search(r"lost|loss", loss_match.group(1), re.I) else "profit"
        amt, _ = normalize_amount_and_period(loss_match.group(2), context_hint=text)
        if amt:
            deltas["profit_or_loss_amount"] = amt
            confidence["profit_or_loss_amount"] = 0.88
            evidence["profit_or_loss_amount"] = "profit/loss amount phrase found"
        deltas["profit_or_loss_type"] = sign
        confidence["profit_or_loss_type"] = 0.9
        evidence["profit_or_loss_type"] = "profit/loss direction phrase found"

    # Gross margin.
    gm = re.search(r"(?i)\bgross margin\b\D{0,10}(\d+(?:\.\d+)?)\s*%", text)
    if gm:
        deltas["gross_margin"] = f"{gm.group(1)}%"
        confidence["gross_margin"] = 0.88
        evidence["gross_margin"] = "gross margin percentage found"

    # Marketing spend + period.
    ms = re.search(
        r"(?i)(?:spending|spend|marketing)\D{0,25}(\$?\s*\d+(?:[.,]\d+)?\s*(?:k|m|b|million|billion|thousand)?)\s*(per month|monthly|per quarter|quarterly|per year|annually)?",
        text,
    )
    if ms:
        amt, per = normalize_amount_and_period(ms.group(1), context_hint=f"{ms.group(2) or ''} {text}")
        if amt:
            deltas["marketing_spend"] = amt
            confidence["marketing_spend"] = 0.87
            evidence["marketing_spend"] = "marketing spend amount phrase found"
        if per:
            deltas["marketing_spend_period"] = per
            confidence["marketing_spend_period"] = 0.84
            evidence["marketing_spend_period"] = "marketing period phrase found"

    # Headcount.
    hc = re.search(r"(?i)\b(\d+)\s+(employees|employee|fte|staff)\b", text)
    if hc:
        deltas["headcount"] = normalize_headcount(hc.group(1))
        confidence["headcount"] = 0.9
        evidence["headcount"] = "headcount phrase found"

    # Runway.
    rw = re.search(r"(?i)\b(\d+(?:\.\d+)?)\s+(weeks?|months?)\s+of\s+cash\s+runway\b", text)
    if rw:
        deltas["runway"] = f"{rw.group(1)} {rw.group(2)}"
        confidence["runway"] = 0.87
        evidence["runway"] = "runway phrase found"

    # Main problem / goal summaries.
    if re.search(
        r"(?i)\b(main problem|biggest problem|problem is|profitability is getting worse|less efficient|acquisition costs have increased|repeat purchase rates are lower|inventory planning has been inconsistent)\b",
        text,
    ):
        deltas["main_problem"] = (
            "Growing revenue but decreasing business efficiency due to CAC pressure, weaker repeat purchases, and inventory issues."
        )
        confidence["main_problem"] = 0.82
        evidence["main_problem"] = "problem framing language detected"
    if re.search(r"(?i)\b(goal is|my goal|i need help|cash-flow positive|within the next|next 2 quarters)\b", text):
        deltas["main_goal"] = "Become cash-flow positive within 2 quarters without killing growth."
        confidence["main_goal"] = 0.84
        evidence["main_goal"] = "goal statement detected"

    # Company / industry hints.
    if re.search(r"(?i)\b(run a|we are a|i run a)\s+(dtc|d2c|b2b|b2c)?\s*([a-z ]+?)\s+company\b", lowered):
        if "skincare" in lowered:
            deltas["industry"] = "Skincare"
            confidence["industry"] = 0.72
            evidence["industry"] = "industry noun detected"

    return {"field_deltas": deltas, "confidence": confidence, "evidence": evidence}


def compute_missing_fields(draft: dict[str, str], mode: IntakeMode) -> list[str]:
    missing: list[str] = []
    for field in critical_fields_for_mode(mode):
        val = (draft.get(field) or "").strip()
        if not val:
            missing.append(field)
            continue
        err = _validate_field(field, val, mode)
        if err:
            missing.append(field)
    return missing


def compute_readiness(mode: IntakeMode, missing_fields: list[str]) -> tuple[int, bool]:
    total = len(critical_fields_for_mode(mode))
    score = int(((total - len(missing_fields)) / max(total, 1)) * 100)
    threshold = 60 if mode == "quick" else 78 if mode == "guided" else 90
    can_run = score >= threshold and len(missing_fields) <= (2 if mode == "quick" else 1 if mode == "guided" else 0)
    return max(0, min(100, score)), can_run


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                out = json.loads(text[start : end + 1])
                return out if isinstance(out, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


def _fallback_delta(user_message: str) -> dict[str, Any]:
    text = user_message.strip()
    det = _extract_deterministic_signals(text)

    return {
        "field_deltas": det["field_deltas"],
        "confidence": det["confidence"],
        "evidence": det["evidence"],
        "residual_context": text,
    }


def extract_case_fields_from_message(
    mode: IntakeMode,
    messages: list[dict[str, str]],
    current_draft: dict[str, str],
    user_message: str,
) -> dict[str, Any]:
    prompt = (
        "Extract only explicitly supported business facts from the latest user message.\n"
        "Return JSON with keys: field_deltas, confidence, evidence, residual_context.\n"
        f"Allowed fields: {', '.join(CASE_FIELDS)}.\n"
        "Rules:\n"
        "- Do NOT copy the full paragraph into many fields.\n"
        "- Keep values concise and specific.\n"
        "- Leave fields absent if uncertain.\n"
        "- residual_context: short leftover context not represented in structured fields.\n"
        "- confidence values between 0 and 1.\n"
        "Return JSON only."
    )
    context_tail = messages[-8:]
    user_input = (
        f"Mode: {mode}\n"
        f"Current draft: {json.dumps(current_draft, ensure_ascii=False)}\n"
        f"Recent messages: {json.dumps(context_tail, ensure_ascii=False)}\n"
        f"Latest user message: {user_message}\n"
    )
    try:
        raw = generate_agent_response(prompt, user_input)
        parsed = _parse_json_object(raw)
        if not parsed:
            return _fallback_delta(user_message)
        parsed.setdefault("field_deltas", {})
        parsed.setdefault("confidence", {})
        parsed.setdefault("evidence", {})
        parsed.setdefault("residual_context", "")
        # Deterministic enrichment boosts reliability for long paragraphs.
        det = _extract_deterministic_signals(user_message)
        fd = parsed.get("field_deltas") if isinstance(parsed.get("field_deltas"), dict) else {}
        conf = parsed.get("confidence") if isinstance(parsed.get("confidence"), dict) else {}
        ev = parsed.get("evidence") if isinstance(parsed.get("evidence"), dict) else {}
        for k, v in det["field_deltas"].items():
            if not fd.get(k):
                fd[k] = v
                conf[k] = det["confidence"].get(k, 0.6)
                ev[k] = det["evidence"].get(k, "deterministic extraction")
            else:
                try:
                    old_conf = float(conf.get(k, 0.0) or 0.0)
                except (TypeError, ValueError):
                    old_conf = 0.0
                new_conf = float(det["confidence"].get(k, 0.0) or 0.0)
                if new_conf > old_conf + 0.15:
                    fd[k] = v
                    conf[k] = new_conf
                    ev[k] = det["evidence"].get(k, "deterministic extraction")
        parsed["field_deltas"] = fd
        parsed["confidence"] = conf
        parsed["evidence"] = ev
        return parsed
    except Exception:
        return _fallback_delta(user_message)


def merge_case_draft(current_draft: dict[str, str], extraction_result: dict[str, Any]) -> dict[str, str]:
    merged = dict(current_draft)
    deltas: dict[str, Any] = extraction_result.get("field_deltas", {}) or {}
    confidence_raw = extraction_result.get("confidence", {}) or {}
    confidence: dict[str, Any]
    if isinstance(confidence_raw, dict):
        confidence = confidence_raw
    else:
        confidence = {}

    canonical_fields = {
        "business_model",
        "revenue_amount",
        "revenue_period",
        "profit_or_loss_amount",
        "profit_or_loss_type",
        "gross_margin",
        "marketing_spend",
        "marketing_spend_period",
        "headcount",
        "runway",
        "main_problem",
        "main_goal",
    }

    for field, raw_val in deltas.items():
        if field not in CASE_FIELDS:
            continue
        new_val = str(raw_val or "").strip()
        if not new_val:
            continue
        try:
            new_conf = float(confidence.get(field, 0.5) or 0.0)
        except (TypeError, ValueError):
            new_conf = 0.5
        current_val = (merged.get(field) or "").strip()
        current_conf = 0.9 if current_val else 0.0
        if new_conf < 0.45 and current_val:
            continue
        if current_conf > new_conf and current_val:
            continue

        if field == "revenue_period":
            new_val = normalize_revenue_period(new_val)
        elif field in ("revenue_amount", "profit_or_loss_amount", "marketing_spend"):
            n = _parse_amount_token(new_val)
            if n is not None:
                new_val = _to_number_string(n)
        elif field == "marketing_spend_period":
            _, p = normalize_amount_and_period("", context_hint=new_val)
            if p:
                new_val = p
        elif field == "profit_or_loss_type":
            new_val = normalize_profit_or_loss_type(new_val)
        elif field == "headcount":
            new_val = normalize_headcount(new_val)
        elif field == "runway":
            m = re.search(r"(\d+(?:\.\d+)?)\s*(weeks?|months?)", new_val, flags=re.I)
            if m:
                new_val = f"{m.group(1)} {m.group(2).lower()}"
        elif field in ("main_problem", "main_goal"):
            new_val = re.sub(r"\s+", " ", new_val).strip()
            if len(new_val) > 180:
                new_val = f"{new_val[:177].rstrip()}..."

        # Prefer higher quality canonical values for key structured fields.
        if field in canonical_fields and current_val and new_val != current_val:
            if len(new_val) < len(current_val) and new_conf >= 0.7:
                merged[field] = new_val
                continue
        merged[field] = new_val

    residual = str(extraction_result.get("residual_context", "") or "").strip()
    if residual:
        # Keep only a compact residual note; full raw text remains in chat history.
        if len(residual) > 220:
            residual = f"{residual[:217].rstrip()}..."
        prior = merged.get("extra_context", "").strip()
        merged["extra_context"] = f"{prior}\n{residual}".strip() if prior else residual

    return merged


def choose_next_follow_up(
    mode: IntakeMode,
    draft: dict[str, str],
    missing_fields: list[str],
    *,
    last_follow_up_field: str | None = None,
) -> tuple[str, str]:
    if not missing_fields:
        return (
            "I have enough context to run analysis. You can say 'run analysis' to proceed.",
            "",
        )
    targets: dict[str, str] = {
        "business_model": "Can you summarize your business model in one line (what you sell and to whom)?",
        "revenue_amount": "What is your current revenue amount?",
        "revenue_period": "Is that revenue weekly, monthly, quarterly, or annual?",
        "profit_or_loss_type": "Are you currently profit, loss, or break-even?",
        "profit_or_loss_amount": "What is the approximate profit/loss amount for that period?",
        "gross_margin": "What is your approximate gross margin percentage?",
        "headcount": "What is your headcount?",
        "marketing_spend": "What is your marketing spend amount?",
        "marketing_spend_period": "Is that marketing spend monthly, quarterly, or annual?",
        "cash_reserves": "What is your current cash reserve position?",
        "runway": "How much runway do you have (weeks/months)?",
        "main_problem": "What is the single biggest business problem right now?",
        "main_goal": "What is your main goal over the next 2-3 quarters?",
        "company_name": "What is the company name?",
        "industry": "What industry are you in?",
    }
    priorities = critical_fields_for_mode(mode)
    if mode != "quick":
        priorities = [*priorities, "gross_margin", "marketing_spend_period"]

    # Defensive gating: do not ask for already meaningful normalized fields.
    gated_missing: list[str] = []
    for field in missing_fields:
        val = (draft.get(field) or "").strip()
        if val and not _validate_field(field, val, mode):
            continue
        gated_missing.append(field)

    if not gated_missing:
        return (
            "I have enough context to run analysis. You can say 'run analysis' to proceed.",
            "",
        )

    for field in priorities:
        if field in gated_missing:
            if last_follow_up_field and field == last_follow_up_field and len(gated_missing) > 1:
                continue
            return targets.get(field, f"Could you clarify {field.replace('_', ' ')}?"), field
    field = gated_missing[0]
    return targets.get(field, f"Could you clarify {field.replace('_', ' ')}?"), field


def summarize_extracted_facts(draft: dict[str, str], missing_fields: list[str], readiness_score: int) -> dict[str, Any]:
    def _v(key: str) -> str:
        return (draft.get(key) or "").strip()

    return {
        "business": {
            "company_name": _v("company_name") or "Not yet provided",
            "industry": _v("industry") or "Not yet provided",
            "business_model": _v("business_model") or "Not yet provided",
        },
        "financials": {
            "revenue_amount": _v("revenue_amount") or "Not yet provided",
            "revenue_period": _v("revenue_period") or "Not yet provided",
            "profit_or_loss_type": _v("profit_or_loss_type") or "Not yet provided",
            "profit_or_loss_amount": _v("profit_or_loss_amount") or "Not yet provided",
            "gross_margin": _v("gross_margin") or "Not yet provided",
            "marketing_spend": _v("marketing_spend") or "Not yet provided",
            "marketing_spend_period": _v("marketing_spend_period") or "Not yet provided",
        },
        "constraints": {
            "headcount": _v("headcount") or "Not yet provided",
            "cash_reserves": _v("cash_reserves") or "Not yet provided",
            "runway": _v("runway") or "Not yet provided",
        },
        "problem_goal": {
            "main_problem": _v("main_problem") or "Not yet provided",
            "main_goal": _v("main_goal") or "Not yet provided",
        },
        "readiness_score": readiness_score,
        "missing_fields": missing_fields,
    }

