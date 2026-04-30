"""
Terminal-based mode intake for the consulting simulator.

Collects answers in Quick, Guided, or Detailed mode and normalizes them into
one common case dictionary. The app then turns that dict into a single
narrative string for run_intake_agent (no agent changes required).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from utils.input_validation import (
    normalize_headcount,
    normalize_profit_or_loss_type,
    normalize_revenue_period,
    validate_business_model_intake,
    validate_cash_reserves_required,
    validate_company_name_intake,
    validate_headcount,
    validate_industry_intake,
    validate_main_goal_intake,
    validate_main_problem_intake,
    validate_marketing_spend_required,
    validate_profit_or_loss_amount,
    validate_profit_or_loss_type,
    validate_revenue_amount,
    validate_revenue_period_required,
    validate_spend_category_intake,
)

# When stdin is not a TTY (e.g. piped input), stdout may be fully block-buffered.
# Line-buffering helps each question appear before the next `input()` reads a line.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (OSError, ValueError):
        pass

# Every case uses these string keys so downstream code can rely on one shape.
_CANONICAL_KEYS: tuple[str, ...] = (
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


def empty_case() -> dict[str, str]:
    """Return a fresh case dict with all canonical keys set to empty strings."""
    return {key: "" for key in _CANONICAL_KEYS}


def _ask(prompt: str, *, allow_empty: bool = False) -> str:
    """Read one line from the user; re-prompt if empty when not allowed."""
    while True:
        text = prompt if prompt.endswith("\n") else prompt + "\n"
        print(text, end="", flush=True)
        answer = input().strip()
        if answer or allow_empty:
            return answer
        print("Please enter a value (or type 'n/a' if truly unknown).\n", flush=True)


def ask_until_valid(
    prompt: str,
    *,
    allow_empty: bool = False,
    validate: Callable[[str], str | None],
    normalize: Callable[[str], str] | None = None,
) -> str:
    """
    Print `prompt`, read one line, validate, and re-ask on failure with a short hint.
    If `normalize` is set, the returned value is normalize(answer) after a successful validate.
    """
    while True:
        line = prompt if prompt.endswith("\n") else prompt + "\n"
        print(line, end="", flush=True)
        answer = input().strip()
        if allow_empty and not answer:
            return ""
        if not allow_empty and not answer:
            print("Please enter a value (or type 'n/a' if unknown).\n", flush=True)
            continue
        err = validate(answer)
        if err:
            print(f"{err}\n", flush=True)
            continue
        if normalize is not None:
            return normalize(answer)
        return answer


def prompt_mode_choice() -> str:
    """
    Show intake mode menu. Empty input defaults to Guided (recommended).
    Returns 'quick', 'guided', or 'detailed'.
    """
    print("\nHow would you like to describe your company?")
    print("  1. Quick   - fastest, essentials only")
    print("  2. Guided  - recommended: step-by-step consultant-style questions")
    print("  3. Detailed - fuller intake if you have more numbers and context")
    print("\nPress Enter for Guided (2), or type 1, 2, or 3: ", end="", flush=True)

    raw = input().strip().lower()
    if raw in ("", "2", "guided"):
        return "guided"
    if raw in ("1", "quick"):
        return "quick"
    if raw in ("3", "detailed"):
        return "detailed"
    print("Invalid choice. Using Guided (2).\n")
    return "guided"


def collect_quick_case() -> dict[str, str]:
    """Minimal questions for a fast path."""
    case = empty_case()
    print("\n--- Quick intake ---\n")

    case["business_model"] = ask_until_valid(
        "What does your company do, and how does it make money?\n"
        "Example: B2B SaaS selling HR software to small businesses on subscription.\n\n> ",
        validate=validate_business_model_intake,
    )
    case["revenue_amount"] = ask_until_valid(
        "What is your revenue? Include a number or scale (currency, k/M, ARR, etc.).\n"
        "Example: $2M ARR, 500k per year, or roughly 1.5 million annually.\n\n> ",
        validate=validate_revenue_amount,
    )
    case["profit_or_loss_type"] = ask_until_valid(
        "Are you making a profit, a loss, or roughly break-even?\n"
        "You can answer with words like profitable, losing money, or break-even.\n\n> ",
        validate=validate_profit_or_loss_type,
        normalize=normalize_profit_or_loss_type,
    )
    case["profit_or_loss_amount"] = ask_until_valid(
        "Roughly how much profit or loss per month or year (whichever you use)?\n"
        "Example: $50k loss per month, 10% margin, or n/a if you are unsure.\n\n> ",
        validate=validate_profit_or_loss_amount,
    )
    case["headcount"] = ask_until_valid(
        "How many employees (headcount or FTE)?\n"
        "Example: 12, 50, or about 30.\n\n> ",
        validate=validate_headcount,
        normalize=normalize_headcount,
    )
    case["main_problem"] = ask_until_valid(
        "What is the biggest problem right now?\n"
        "Short phrases are OK, e.g. high churn, rising CAC, shrinking margins, low runway.\n\n> ",
        validate=validate_main_problem_intake,
    )
    case["main_goal"] = ask_until_valid(
        "What is your main goal for the next few months?\n"
        "Example: extend runway, improve margins, grow revenue 20%.\n\n> ",
        validate=validate_main_goal_intake,
    )

    extra = _ask("Anything else we should know? (optional, press Enter to skip): ", allow_empty=True)
    if extra:
        case["extra_context"] = extra
    return case


def collect_guided_case() -> dict[str, str]:
    """Step-by-step intake; Guided is the default/recommended mode."""
    case = empty_case()
    print("\n--- Guided intake ---\n")

    case["business_model"] = ask_until_valid(
        "What does your company do, and how does it make money?\n"
        "Example: wholesale coffee to independent cafés, mostly on contract.\n\n> ",
        validate=validate_business_model_intake,
    )
    case["revenue_amount"] = ask_until_valid(
        "What is your revenue (rough amount + currency or scale)?\n"
        "Example: 750k USD per year, $3M ARR, or about 2 million.\n\n> ",
        validate=validate_revenue_amount,
    )
    case["revenue_period"] = ask_until_valid(
        "Is that revenue figure weekly, monthly, quarterly, or annual?\n"
        "You can say things like monthly, per year, or quarterly.\n\n> ",
        validate=validate_revenue_period_required,
        normalize=normalize_revenue_period,
    )
    case["profit_or_loss_type"] = ask_until_valid(
        "Are you profitable, losing money, or about break-even?\n"
        "Answers like profitable, loss, or losing money are all fine.\n\n> ",
        validate=validate_profit_or_loss_type,
        normalize=normalize_profit_or_loss_type,
    )
    case["profit_or_loss_amount"] = ask_until_valid(
        "Roughly how much profit or loss for that same kind of period?\n"
        "Example: 20k profit per month, 15% margin, or n/a if unsure.\n\n> ",
        validate=validate_profit_or_loss_amount,
    )
    case["headcount"] = ask_until_valid(
        "How many employees?\n"
        "Example: 8, 42 FTE, around 100.\n\n> ",
        validate=validate_headcount,
        normalize=normalize_headcount,
    )
    spend = ask_until_valid(
        "What is your biggest spend category right now?\n"
        "Examples: payroll, ads, COGS, rent, software.\n\n> ",
        validate=validate_spend_category_intake,
    )
    case["marketing_spend"] = ask_until_valid(
        "Are you spending heavily on marketing? Give a rough amount, % of revenue, or a word like no, minimal, or unknown.\n"
        "Example: 20% of revenue, $5k per month, minimal.\n\n> ",
        validate=validate_marketing_spend_required,
    )
    case["cash_reserves"] = ask_until_valid(
        "What are your cash reserves or runway concerns?\n"
        "Example: 8 weeks of runway, $200k in the bank, tight on cash.\n\n> ",
        validate=validate_cash_reserves_required,
    )
    case["main_problem"] = ask_until_valid(
        "What is the biggest problem right now?\n"
        "Short phrases are OK, e.g. high churn, rising ad costs, cash runway is short.\n\n> ",
        validate=validate_main_problem_intake,
    )
    case["main_goal"] = ask_until_valid(
        "What is your goal for the next 3 to 6 months?\n"
        "Example: stabilize cash, raise a round, cut CAC, launch in a new region.\n\n> ",
        validate=validate_main_goal_intake,
    )

    parts: list[str] = []
    if spend:
        parts.append(f"Biggest spend category: {spend}")
    extra = _ask("Any extra context? (optional, press Enter to skip): ", allow_empty=True)
    if extra:
        parts.append(extra)
    case["extra_context"] = "\n".join(parts).strip()
    return case


def collect_detailed_case() -> dict[str, str]:
    """Fuller business intake including churn, pricing, and competition."""
    case = empty_case()
    print("\n--- Detailed intake ---\n")

    case["company_name"] = ask_until_valid(
        "What is the company name?\n"
        "Use the real name or a simple placeholder you prefer.\n\n> ",
        validate=validate_company_name_intake,
    )
    case["industry"] = ask_until_valid(
        "What industry are you in?\n"
        "Example: B2B software, specialty retail, logistics for food.\n\n> ",
        validate=validate_industry_intake,
    )
    case["business_model"] = ask_until_valid(
        "Describe the business model: what you sell, to whom, and how you get paid.\n"
        "Example: subscription analytics for mid-market retailers.\n\n> ",
        validate=validate_business_model_intake,
    )
    case["revenue_amount"] = ask_until_valid(
        "What is your revenue (amount + scale)?\n"
        "Example: $12M annually, 400k monthly, 2M ARR.\n\n> ",
        validate=validate_revenue_amount,
    )
    case["revenue_period"] = ask_until_valid(
        "What period is that revenue for? Choose weekly, monthly, quarterly, or annual.\n"
        "Synonyms like yearly or per month are OK.\n\n> ",
        validate=validate_revenue_period_required,
        normalize=normalize_revenue_period,
    )
    case["profit_or_loss_type"] = ask_until_valid(
        "Are you at a profit, loss, or break-even?\n"
        "You may answer with profitable, losing money, or break-even.\n\n> ",
        validate=validate_profit_or_loss_type,
        normalize=normalize_profit_or_loss_type,
    )
    case["profit_or_loss_amount"] = ask_until_valid(
        "Rough profit or loss amount for the period you use.\n"
        "Example: $2M EBITDA, 5% net margin, or n/a if uncertain.\n\n> ",
        validate=validate_profit_or_loss_amount,
    )
    case["headcount"] = ask_until_valid(
        "Headcount or FTE?\n"
        "Example: 25, about 200 employees.\n\n> ",
        validate=validate_headcount,
        normalize=normalize_headcount,
    )
    case["marketing_spend"] = ask_until_valid(
        "Marketing spend (amount, % of revenue, or words like unknown / minimal).\n"
        "Example: 12% of revenue, $30k per month, none.\n\n> ",
        validate=validate_marketing_spend_required,
    )
    case["cash_reserves"] = ask_until_valid(
        "Cash reserves or runway (weeks/months, or rough bank balance).\n"
        "Example: 4 months runway, ~$500k cash.\n\n> ",
        validate=validate_cash_reserves_required,
    )

    retention = _ask("Retention or churn issues? (describe, or 'none known'): ", allow_empty=True)
    pricing = _ask("Pricing or discounting issues? ", allow_empty=True)
    competitors = _ask("Competitor pressure? ", allow_empty=True)
    case["main_problem"] = ask_until_valid(
        "What is the biggest problem right now?\n"
        "Short phrases are OK, e.g. shrinking margins, key customers leaving, debt covenant pressure.\n\n> ",
        validate=validate_main_problem_intake,
    )
    case["main_goal"] = ask_until_valid(
        "What is your primary goal?\n"
        "Example: refinance debt, improve gross margin, double enterprise sales.\n\n> ",
        validate=validate_main_goal_intake,
    )

    extra = _ask("Extra context (optional): ", allow_empty=True)
    detail_lines = []
    if retention:
        detail_lines.append(f"Retention/churn: {retention}")
    if pricing:
        detail_lines.append(f"Pricing/discounting: {pricing}")
    if competitors:
        detail_lines.append(f"Competition: {competitors}")
    if extra:
        detail_lines.append(extra)
    case["extra_context"] = "\n".join(detail_lines).strip()
    return case


def collect_case_by_mode(mode: str) -> dict[str, str]:
    """Dispatch to the right collector."""
    if mode == "quick":
        return collect_quick_case()
    if mode == "detailed":
        return collect_detailed_case()
    return collect_guided_case()


def normalize_case(case: dict[str, Any]) -> dict[str, str]:
    """Ensure all canonical keys exist and values are stripped strings."""
    out = empty_case()
    for key in _CANONICAL_KEYS:
        val = case.get(key, "")
        out[key] = str(val).strip() if val is not None else ""
    return out


def format_case_summary(case: dict[str, str]) -> str:
    """Human-readable summary for confirmation before running the pipeline."""
    lines: list[str] = ["Case summary (what we will send to the analysis pipeline)", "-" * 48]
    labels = {
        "company_name": "Company name",
        "industry": "Industry",
        "business_model": "What the company does",
        "revenue_amount": "Revenue",
        "revenue_period": "Revenue period",
        "profit_or_loss_type": "Profit / loss",
        "profit_or_loss_amount": "Profit / loss amount",
        "gross_margin": "Gross margin",
        "headcount": "Headcount",
        "marketing_spend": "Marketing spend",
        "marketing_spend_period": "Marketing spend period",
        "cash_reserves": "Cash / runway",
        "runway": "Runway",
        "main_problem": "Main problem",
        "main_goal": "Main goal",
        "extra_context": "Extra context",
    }
    for key in _CANONICAL_KEYS:
        val = case.get(key, "").strip()
        if val:
            lines.append(f"  - {labels[key]}: {val}")
    if len(lines) == 2:
        lines.append("  (No answers captured — please restart and fill in the prompts.)")
    lines.append("-" * 48)
    return "\n".join(lines)


def case_to_client_narrative(case: dict[str, str]) -> str:
    """
    Build one narrative string for run_intake_agent from the structured case.

    Labeled sections help the model even when the user chose Quick mode.
    """
    c = normalize_case(case)
    blocks: list[str] = []

    if c["company_name"]:
        blocks.append(f"Company name: {c['company_name']}")
    if c["industry"]:
        blocks.append(f"Industry: {c['industry']}")
    if c["business_model"]:
        blocks.append(f"What the company does: {c['business_model']}")

    rev = c["revenue_amount"]
    if rev:
        if c["revenue_period"]:
            blocks.append(f"Revenue ({c['revenue_period']}): {rev}")
        else:
            blocks.append(f"Revenue: {rev}")

    pl_type = c["profit_or_loss_type"]
    pl_amt = c["profit_or_loss_amount"]
    if pl_type or pl_amt:
        blocks.append(
            f"Profitability: {pl_type or 'unspecified'} - amount: {pl_amt or 'unspecified'}"
        )

    if c.get("gross_margin"):
        blocks.append(f"Gross margin: {c['gross_margin']}")

    if c["headcount"]:
        blocks.append(f"Headcount: {c['headcount']}")
    if c["marketing_spend"]:
        if c.get("marketing_spend_period"):
            blocks.append(
                f"Marketing spend ({c['marketing_spend_period']}): {c['marketing_spend']}"
            )
        else:
            blocks.append(f"Marketing spend: {c['marketing_spend']}")
    if c["cash_reserves"]:
        blocks.append(f"Cash / runway: {c['cash_reserves']}")
    if c.get("runway"):
        blocks.append(f"Runway: {c['runway']}")
    if c["main_problem"]:
        blocks.append(f"Biggest problem right now: {c['main_problem']}")
    if c["main_goal"]:
        blocks.append(f"Main goal: {c['main_goal']}")
    if c["extra_context"]:
        blocks.append(f"Additional context:\n{c['extra_context']}")

    return "\n\n".join(blocks).strip()


def confirm_analysis() -> bool:
    """Ask user to confirm before running OpenAI / agents."""
    while True:
        print("Proceed with analysis? (y/n): ", end="", flush=True)
        ans = input().strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'.\n")


_BUSINESS_KEYWORDS = frozenset(
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
    }
)


def validate_collected_case(case: dict[str, str]) -> tuple[bool, str]:
    """
    Backward-compatible gate: delegates to input_validation.validate_intake_case.
    Mode is inferred from filled fields when not passed via app (see infer_intake_mode).
    """
    from utils.input_validation import infer_intake_mode, validate_intake_case

    c = normalize_case(case)
    mode = infer_intake_mode(c)
    ok, errors = validate_intake_case(c, mode)
    if ok:
        return True, ""
    return False, "; ".join(errors)
