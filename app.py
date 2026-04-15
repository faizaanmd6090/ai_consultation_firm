"""
AI management consulting simulator (Phase 1 mock logic, Phase 2 structure).

This script models a small multi-agent workflow similar to how a turnaround
engagement might be staffed (intake, finance, operations, strategy, review).
All five stages use OpenAI when configured (with mock fallbacks on failure).

Intake from the terminal uses mode-based questions (Quick / Guided / Detailed).
Answers are normalized into one case dictionary, shown back for confirmation,
then converted to a single narrative string for the existing intake agent.

Phase 2: every agent's return value is built through helpers in
schemas/agent_output.py so the dict keys stay consistent and easy to maintain.

Phase 3: each agent loads its Markdown instructions from prompts/ via
utils/prompt_loader.py on every run.

Phase 4–6: agents use OpenAI's Responses API (see services/openai_client.py).
Set OPENAI_API_KEY (e.g. in a .env file loaded below) and install requirements.txt.

Run from the project root:

    pip install -r requirements.txt
    python app.py
"""

from __future__ import annotations

import json
from typing import Any

from dotenv import load_dotenv

from agents.final_report_agent import run_final_report_agent
from agents.finance_agent import run_finance_agent
from agents.intake_agent import run_intake_agent
from agents.operations_agent import run_operations_agent
from agents.reviewer_agent import run_reviewer_agent
from agents.strategy_agent import run_strategy_agent
from utils.case_intake import (
    case_to_client_narrative,
    collect_case_by_mode,
    confirm_analysis,
    format_case_summary,
    normalize_case,
    prompt_mode_choice,
    validate_collected_case,
)


def run_turnaround_pipeline(client_problem: str) -> dict[str, Any]:
    """
    Execute the full consulting pipeline end-to-end.

    Returns a dict with keys: intake, finance, operations, strategy, review.
    Each value matches the shared shape from schemas.agent_output (six common
    fields everywhere; review also has priority_order).
    """
    # Intake: frame the problem and align the team on facts, urgency, and data gaps.
    intake = run_intake_agent(client_problem)

    # Parallel workstreams (still run sequentially here for simplicity).
    finance = run_finance_agent(intake)
    operations = run_operations_agent(intake)
    strategy = run_strategy_agent(intake)

    # Review: integrate all workstreams and set an execution order.
    review = run_reviewer_agent(intake, finance, operations, strategy)

    return {
        "intake": intake,
        "finance": finance,
        "operations": operations,
        "strategy": strategy,
        "review": review,
    }


def _print_stage(title: str, payload: dict[str, Any]) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")
    print(json.dumps(payload, indent=2))


def _print_founder_report(report_text: str) -> None:
    print(f"\n{'=' * 72}\nFOUNDER REPORT - DECISION SUMMARY\n{'=' * 72}")
    print(report_text.strip())


def _should_show_detailed_outputs() -> bool:
    print("\nShow detailed agent outputs? (y/N): ", end="", flush=True)
    answer = input().strip().lower()
    return answer in {"y", "yes"}


if __name__ == "__main__":
    # Load project-root .env into os.environ so OPENAI_API_KEY is available to the intake agent.
    load_dotenv()

    # --- Terminal welcome and mode-based intake ---
    print("\n" + "=" * 72)
    print("Welcome to the AI management consulting simulator.")
    print("You will answer a few questions; we will summarize them before running the analysis.")
    print("=" * 72)

    mode = prompt_mode_choice()
    raw_case = collect_case_by_mode(mode)
    case = normalize_case(raw_case)

    print("\n" + format_case_summary(case))
    if not confirm_analysis():
        print("\nOkay - analysis cancelled. Run again when you are ready.")
        raise SystemExit(0)

    client_problem = case_to_client_narrative(case)
    is_valid, reason = validate_collected_case(case)
    if not is_valid:
        print(f"\nCannot run analysis yet: {reason}")
        print("Tip: add revenue, cash/runway, or margin-related detail in your answers.")
        raise SystemExit(0)

    results = run_turnaround_pipeline(client_problem)
    founder_report = run_final_report_agent(
        results["intake"],
        results["finance"],
        results["operations"],
        results["strategy"],
        results["review"],
    )
    _print_founder_report(founder_report)

    if _should_show_detailed_outputs():
        _print_stage("INTAKE - case framing and problem structure", results["intake"])
        _print_stage(
            "FINANCE - P&L, cash, and capital allocation view", results["finance"]
        )
        _print_stage(
            "OPERATIONS - cost-to-serve and delivery levers", results["operations"]
        )
        _print_stage(
            "STRATEGY - market, pricing, and portfolio choices", results["strategy"]
        )
        _print_stage(
            "REVIEW - integrated view and execution priority order", results["review"]
        )
