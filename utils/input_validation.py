"""
Structured validation for terminal intake before the consulting pipeline runs.

Field-level rules, lightweight gibberish heuristics, and coherence checks.
"""

from __future__ import annotations

import re
from typing import Final

# Duplicated from case_intake to avoid circular imports; keep in sync with business context.
_BUSINESS_LEXICON: Final[frozenset[str]] = frozenset(
    {
        "revenue",
        "cost",
        "costs",
        "margin",
        "margins",
        "retention",
        "customer",
        "customers",
        "loss",
        "losses",
        "pricing",
        "cash",
        "growth",
        "profit",
        "profits",
        "ebitda",
        "churn",
        "discount",
        "turnaround",
        "runway",
        "burn",
        "marketing",
        "sales",
        "employee",
        "headcount",
        "saas",
        "b2b",
        "subscription",
        "arr",
        "mrr",
        "inventory",
        "cogs",
        "payroll",
        "cac",
        "ltv",
        "acquisition",
        "online",
        "digital",
        "software",
        "platform",
        "product",
        "products",
        "service",
        "services",
        "wholesale",
        "brand",
        "clients",
        "users",
        "teams",
        "businesses",
    }
)

# Single-word answers that are too vague for "what the company does."
_VAGUE_BUSINESS_MODEL_ONE_WORD: Final[frozenset[str]] = frozenset(
    {
        "saas",
        "b2b",
        "b2c",
        "d2c",
        "shop",
        "store",
        "app",
        "startup",
        "retail",
        "ecommerce",
        "agency",
        "consulting",
    }
)

# Extra tokens for short problem phrases (matched as whole words).
_SIGNAL_TOKENS: Final[frozenset[str]] = frozenset({"cac", "ltv", "roi", "cpa"})

# Weak revenue placeholders: allowed only if coherence passes (strong problem + model + lexicon).
_WEAK_REVENUE: Final[re.Pattern[str]] = re.compile(
    r"^(n/a|na|unknown|not\s*sure|tbd|unsure|n\s*/\s*a|none)\s*$",
    re.IGNORECASE,
)


def is_likely_gibberish(text: str) -> bool:
    """Heuristic gibberish detection (no ML): repetition, low vowel ratio, few distinct letters."""
    if not text or not text.strip():
        return False
    s_clean = "".join(text.split()).lower()
    if len(s_clean) < 3:
        return False
    # Single repeated character (e.g. aaaaaa)
    if len(set(s_clean)) == 1 and len(s_clean) > 2:
        return True
    # Same two-letter pattern repeated (e.g. asasas)
    if len(s_clean) >= 6 and len(s_clean) % 2 == 0:
        pair = s_clean[:2]
        if pair * (len(s_clean) // 2) == s_clean:
            return True
    letters = [c for c in s_clean if c.isalpha()]
    if len(letters) >= 8:
        vowels = sum(1 for c in letters if c in "aeiou")
        if vowels / len(letters) < 0.12:
            return True
    # Long alpha chunk with very few distinct letters (keyboard mash)
    if len(letters) > 15 and len(set(letters)) < 5:
        return True
    return False


def _word_tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower()) if len(w) >= 2]


def is_meaningful_business_text(text: str, *, min_words: int = 2) -> bool:
    """Not gibberish; enough real words; at least one business-lexicon hit."""
    raw = text.strip()
    if not raw:
        return False
    if is_likely_gibberish(raw):
        return False
    words = _word_tokens(raw)
    if len(words) < min_words:
        return False
    blob = " ".join(words)
    if not any(kw in blob for kw in _BUSINESS_LEXICON):
        return False
    return True


def _has_business_signal(text: str) -> bool:
    """True if text mentions a lexicon term or common short signal (cac, roi)."""
    raw = text.strip().lower()
    if not raw:
        return False
    words = _word_tokens(raw)
    blob = " ".join(words)
    if any(kw in blob for kw in _BUSINESS_LEXICON):
        return True
    return any(t in raw.split() for t in _SIGNAL_TOKENS)


def _has_amount_signal(text: str) -> bool:
    """Digit, currency, scale, or spelled-out amount language (shared revenue / P&L amount rules)."""
    t = text.strip()
    if not t:
        return False
    if _WEAK_REVENUE.match(t):
        return True
    if re.search(r"\d", t):
        return True
    if re.search(r"[\$£€]", t):
        return True
    if re.search(r"\b(arr|mrr|revenue)\b", t, re.IGNORECASE):
        return True
    if re.search(r"\b\d*[.]?\d*\s*[kmb]\b", t, re.IGNORECASE):
        return True
    if re.search(
        r"\b(million|thousand|billion|hundred\s+thousand|half\s+million)\b",
        t,
        re.IGNORECASE,
    ):
        return True
    return False


def validate_business_model_intake(text: str) -> str | None:
    """
    Reject vague one-word answers; require meaningful business text with a concrete signal.
    """
    raw = text.strip()
    if not raw:
        return "Please describe what the company does and how it makes money."
    if is_likely_gibberish(raw):
        return "Please describe what the company does and how it makes money."
    words = _word_tokens(raw)
    if len(words) < 2:
        w0 = words[0].lower() if words else ""
        if len(words) == 1 and (
            w0 in _VAGUE_BUSINESS_MODEL_ONE_WORD or len(w0) <= 4
        ):
            return (
                "Please describe what the company does and how it makes money. "
                "Example: B2B SaaS selling HR software to small businesses on subscription."
            )
        if len(words) == 1:
            return (
                "Please add a bit more — what do you sell, and who pays you? "
                "Example: wholesale coffee to cafés."
            )
    if not is_meaningful_business_text(raw, min_words=2):
        return (
            "Say what you sell, to whom, and how you get paid (one short phrase is fine)."
        )
    return None


def validate_main_problem_intake(text: str) -> str | None:
    """Allow short phrases like 'high churn, low retention' when they carry business signal."""
    raw = text.strip()
    if not raw:
        return "Describe a real business issue (e.g. high churn, shrinking margins, runway is 4 weeks)."
    if is_likely_gibberish(raw):
        return (
            "Main problem should be a real business issue. "
            "Examples: high churn, shrinking margins, or cash runway is 4 weeks."
        )
    words = _word_tokens(raw)
    if _has_business_signal(raw):
        if len(words) >= 2:
            return None
        # Single strong token: "churn" alone is weak; need two words or length
        if len(raw) >= 12:
            return None
    if len(raw) >= 20 and len(words) >= 2:
        return None
    if len(raw) >= 15 and len(words) >= 2 and _has_business_signal(raw):
        return None
    return (
        "Main problem should be a real business issue, "
        "for example: high churn, shrinking margins, or cash runway is 4 weeks."
    )


def validate_main_goal_intake(text: str) -> str | None:
    raw = text.strip()
    if not raw:
        return "State a concrete goal (e.g. reach profitability, 6 months runway, grow ARR)."
    if is_likely_gibberish(raw):
        return "Use a real goal phrase (growth, margin, runway, revenue)."
    words = _word_tokens(raw)
    if _has_business_signal(raw) and len(words) >= 1:
        return None
    if len(raw) >= 12 and len(words) >= 2:
        return None
    if is_meaningful_business_text(raw, min_words=2):
        return None
    return (
        "State a concrete business goal (e.g. extend runway, improve margins, grow sales)."
    )


def validate_profit_or_loss_amount(text: str) -> str | None:
    """Rough figure: number or amount-like language; allow weak placeholders like n/a."""
    t = text.strip()
    if not t:
        return "Give a rough amount (e.g. $50k per month) or type n/a if unknown."
    if is_likely_gibberish(t):
        return (
            "Profit or loss amount should include a number or scale, e.g. $10k per month or 15% margin."
        )
    if _has_amount_signal(t):
        return None
    return (
        "Profit or loss amount should include a number or scale, "
        "for example: $50k per month, 500k yearly, or minimal."
    )


def normalize_revenue_period(text: str) -> str:
    """
    Map accepted wording to weekly | monthly | quarterly | annual.
    Call only after validate_revenue_period passes.
    """
    raw = text.strip().lower()
    s = re.sub(r"[^a-z0-9\s/]", " ", raw)
    s = " ".join(s.split())
    if re.search(r"\b(annual|yearly|per\s*year|each\s*year|a\s*year)\b", s) or s in (
        "year",
        "annual",
        "yearly",
    ):
        return "annual"
    if re.search(r"\b(quarterly|each\s*quarter|per\s*quarter|q[1-4])\b", s) or s in (
        "quarter",
        "quarterly",
    ):
        return "quarterly"
    if re.search(r"\b(monthly|each\s*month|per\s*month|a\s*month)\b", s) or s in (
        "month",
        "monthly",
    ):
        return "monthly"
    if re.search(r"\b(weekly|each\s*week|per\s*week|a\s*week)\b", s) or s in (
        "week",
        "weekly",
    ):
        return "weekly"
    return text.strip()


def normalize_profit_or_loss_type(text: str) -> str:
    """
    Canonical values: profit | loss | break-even.
    Call only after validate_profit_or_loss_type passes.
    """
    t = text.strip().lower()
    if re.search(r"break[\s\-]?even|breakeven", t):
        return "break-even"
    if "loss" in t or "losing" in t or re.search(r"\blose\b", t):
        return "loss"
    if "profit" in t or "profitable" in t:
        return "profit"
    return text.strip()


def validate_company_name_intake(text: str) -> str | None:
    t = text.strip()
    if not t:
        return "Enter a company name."
    if is_likely_gibberish(t):
        return "Use a real company name or a simple placeholder name."
    return None


def validate_industry_intake(text: str) -> str | None:
    t = text.strip()
    if not t:
        return "Enter an industry (e.g. software, retail, logistics)."
    if is_likely_gibberish(t):
        return "Use a real industry label."
    return None


def validate_spend_category_intake(text: str) -> str | None:
    """Guided mode: non-empty line item for biggest spend area."""
    t = text.strip()
    if not t:
        return "Name one spend area (e.g. payroll, COGS, ads, rent)."
    if is_likely_gibberish(t):
        return "Use a real category name, not random characters."
    return None


def validate_revenue_amount(text: str) -> str | None:
    """
    Pass if empty is invalid here (caller requires revenue in all modes).
    Pass weak placeholders (n/a, unknown) for coherence to tighten elsewhere.
    Otherwise require a digit or loose amount language ($, k/m/b, million, ARR/MRR, etc.).
    """
    t = text.strip()
    if not t:
        return "Revenue should include a number, for example: $1M ARR or 500k yearly."
    if _has_amount_signal(t):
        return None
    return (
        "Revenue should include a number, for example: $1M ARR or 500k yearly. "
        "You can type n/a only if you add strong detail elsewhere."
    )


def is_weak_revenue_amount(text: str) -> bool:
    t = text.strip()
    return bool(t and _WEAK_REVENUE.match(t))


def validate_revenue_period_required(text: str) -> str | None:
    """Guided/detailed: period is required."""
    if not text.strip():
        return "Revenue period must be weekly, monthly, quarterly, or annual."
    return validate_revenue_period(text)


def validate_revenue_period(text: str) -> str | None:
    """If non-empty, must normalize to weekly | monthly | quarterly | annual."""
    raw = text.strip().lower()
    if not raw:
        return None
    s = re.sub(r"[^a-z0-9\s/]", " ", raw)
    s = " ".join(s.split())
    if _period_matches(s):
        return None
    return "Revenue period must be weekly, monthly, quarterly, or annual."


def _period_matches(s: str) -> bool:
    if re.search(r"\b(annual|yearly|per\s*year|each\s*year|a\s*year)\b", s):
        return True
    if re.search(r"\b(quarterly|each\s*quarter|per\s*quarter|q[1-4])\b", s):
        return True
    if re.search(r"\b(monthly|each\s*month|per\s*month|a\s*month)\b", s):
        return True
    if re.search(r"\b(weekly|each\s*week|per\s*week|a\s*week)\b", s):
        return True
    # Short answers: "month", "year" alone
    if s in ("month", "monthly"):
        return True
    if s in ("week", "weekly"):
        return True
    if s in ("quarter", "quarterly"):
        return True
    if s in ("year", "annual", "yearly"):
        return True
    return False


def validate_profit_or_loss_type(text: str) -> str | None:
    """Map to profit | loss | break-even from common phrasing."""
    if not text.strip():
        return "State whether you are profit, loss, or break-even (or profitable / losing)."
    t = text.strip().lower()
    if re.search(r"break[\s\-]?even|breakeven", t):
        return None
    if "profit" in t or "profitable" in t:
        return None
    if "loss" in t or "losing" in t or re.search(r"\blose\b", t):
        return None
    return "Use profit, loss, or break-even (synonyms: profitable, losing money)."


def validate_headcount(text: str) -> str | None:
    """Require a positive integer (allow '42 employees')."""
    if not text.strip():
        return "Headcount must be a number (e.g. 12, 50, about 30)."
    digits = re.sub(r",", "", text)
    m = re.search(r"\d+", digits)
    if not m:
        return "Please enter a numeric headcount, for example: 12, 50, or about 30."
    n = int(m.group())
    if n < 1:
        return "Headcount must be a positive number."
    return None


def normalize_headcount(text: str) -> str:
    """Store canonical digits-only headcount after validation."""
    m = re.search(r"\d+", text.replace(",", ""))
    return m.group(0) if m else text.strip()


def validate_marketing_spend_required(text: str) -> str | None:
    """Guided/detailed: marketing line must not be empty."""
    if not text.strip():
        return (
            "Describe marketing spend: an amount, % of revenue, or words like no, minimal, unknown."
        )
    return validate_marketing_spend(text)


def validate_cash_reserves_required(text: str) -> str | None:
    if not text.strip():
        return "Describe cash reserves or runway (weeks/months of runway or rough balance)."
    return validate_cash_reserves(text)


def validate_marketing_spend(text: str) -> str | None:
    """Flexible: digit, %, or common qualitative words."""
    t = text.strip()
    if not t:
        return None
    if re.search(r"\d", t) or "%" in t:
        return None
    qual = re.compile(
        r"\b(no|none|minimal|low|unknown|n/a|na|not\s*sure|little|zero)\b",
        re.IGNORECASE,
    )
    if qual.search(t):
        return None
    if is_likely_gibberish(t):
        return "Marketing spend: give a rough amount, %, or words like no / minimal / unknown."
    return None


def validate_cash_reserves(text: str) -> str | None:
    """Fail only on obvious gibberish."""
    t = text.strip()
    if not t:
        return None
    if is_likely_gibberish(t):
        return "Cash/runway: describe weeks/months of runway or a rough balance (not random characters)."
    return None


def infer_intake_mode(case: dict[str, str]) -> str:
    """
    Infer quick vs guided vs detailed from which fields are typically filled.
    Used when validate_collected_case is called without an explicit mode.
    """
    if (case.get("company_name") or "").strip() or (case.get("industry") or "").strip():
        return "detailed"
    if (case.get("marketing_spend") or "").strip() or (case.get("cash_reserves") or "").strip():
        return "guided"
    return "quick"


def validate_intake_case(case: dict[str, str], mode: str) -> tuple[bool, list[str]]:
    """
    Validate structured case after confirmation. Returns (ok, list of human-readable errors).

    mode: 'quick' | 'guided' | 'detailed' — controls which optional fields are required.
    """
    errors: list[str] = []

    def add(field: str, msg: str) -> None:
        errors.append(f"{field}: {msg}")

    mp = case.get("main_problem", "").strip()
    mg = case.get("main_goal", "").strip()
    bm = case.get("business_model", "").strip()

    err_mp = validate_main_problem_intake(mp)
    if err_mp:
        add("main_problem", err_mp)

    err_mg = validate_main_goal_intake(mg)
    if err_mg:
        add("main_goal", err_mg)

    err_bm = validate_business_model_intake(bm)
    if err_bm:
        add("business_model", err_bm)

    # Revenue
    rev_err = validate_revenue_amount(case.get("revenue_amount", ""))
    if rev_err:
        add("revenue_amount", rev_err)

    # Period: required non-empty for guided/detailed (user is asked); optional for quick
    rp = case.get("revenue_period", "").strip()
    if mode in ("guided", "detailed"):
        if not rp:
            add("revenue_period", "State whether revenue is weekly, monthly, quarterly, or annual.")
        else:
            rperr = validate_revenue_period(rp)
            if rperr:
                add("revenue_period", rperr)
    elif rp:
        rperr = validate_revenue_period(rp)
        if rperr:
            add("revenue_period", rperr)

    pl_type_err = validate_profit_or_loss_type(case.get("profit_or_loss_type", ""))
    if pl_type_err:
        add("profit_or_loss_type", pl_type_err)

    pla_err = validate_profit_or_loss_amount(case.get("profit_or_loss_amount", ""))
    if pla_err:
        add("profit_or_loss_amount", pla_err)

    hc_err = validate_headcount(case.get("headcount", ""))
    if hc_err:
        add("headcount", hc_err)

    # Guided / detailed: marketing & cash
    if mode in ("guided", "detailed"):
        ms = case.get("marketing_spend", "").strip()
        if not ms:
            add("marketing_spend", "Describe marketing spend (amount, %, or e.g. no / minimal).")
        else:
            merr = validate_marketing_spend(ms)
            if merr:
                add("marketing_spend", merr)
        cr = case.get("cash_reserves", "").strip()
        if not cr:
            add("cash_reserves", "Describe cash reserves or runway (weeks/months or rough balance).")
        else:
            cerr = validate_cash_reserves(cr)
            if cerr:
                add("cash_reserves", cerr)

    if mode == "detailed":
        cn = case.get("company_name", "").strip()
        ind = case.get("industry", "").strip()
        if not cn:
            add("company_name", "Enter a company name.")
        elif is_likely_gibberish(cn):
            add("company_name", "Use a real name or placeholder, not random characters.")
        if not ind:
            add("industry", "Enter an industry.")
        elif is_likely_gibberish(ind):
            add("industry", "Use a real industry label.")

    # Coherence: weak revenue requires stronger problem + model
    if is_weak_revenue_amount(case.get("revenue_amount", "")):
        strong_mp = len(mp) >= 40 and is_meaningful_business_text(mp, min_words=4)
        strong_bm = len(bm) >= 25 and is_meaningful_business_text(bm, min_words=3)
        if not (strong_mp and strong_bm):
            add(
                "revenue_amount",
                "If revenue is unknown, expand main problem and business model with specific business detail.",
            )

    # Overall business signal in combined narrative slice
    combined = " ".join(
        [
            case.get("business_model", ""),
            case.get("main_problem", ""),
            case.get("main_goal", ""),
            case.get("extra_context", ""),
        ]
    ).lower()
    words = [w for w in combined.split() if w.strip()]
    if len(words) < 12:
        if not any(
            err.startswith("main_problem:") or err.startswith("main_goal:")
            for err in errors
        ):
            add(
                "overall",
                "Overall case text is thin — add specifics (numbers, timeframe, customers, or costs).",
            )
    elif not any(kw in combined for kw in _BUSINESS_LEXICON):
        add(
            "overall",
            "Add clearer business context (e.g. revenue, costs, margins, customers, cash, or marketing).",
        )

    # Too many critical failures: optional extra line (already covered by field errors)
    critical = {
        "main_problem",
        "business_model",
        "revenue_amount",
        "main_goal",
    }
    failed = {e.split(":", 1)[0].strip() for e in errors}
    if len(failed & critical) >= 3:
        if not any(e.startswith("overall:") for e in errors):
            add(
                "overall",
                "Several core fields need real answers before analysis can run.",
            )

    return (len(errors) == 0, errors)
