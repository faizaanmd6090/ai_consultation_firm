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
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from dotenv import load_dotenv

from agents.final_report_agent import run_final_report_agent
from agents.finance_agent import run_finance_agent, run_finance_clarification
from agents.intake_agent import run_intake_agent
from agents.operations_agent import run_operations_agent, run_operations_clarification
from agents.reviewer_agent import (
    build_clarification_answer,
    run_reviewer_final_with_clarifications,
    run_reviewer_pass1,
)
from agents.strategy_agent import run_strategy_agent, run_strategy_clarification
from utils.case_intake import (
    case_to_client_narrative,
    collect_case_by_mode,
    confirm_analysis,
    format_case_summary,
    normalize_case,
    prompt_mode_choice,
)
from utils.input_validation import validate_intake_case


def _print_intake_validation_help() -> None:
    """Short examples after field-level validation failure."""
    print("\nExamples of valid answers:")
    print("  - Revenue: $1.2M ARR, 500k per year, 2 million (rough), or n/a with strong detail elsewhere")
    print("  - Revenue period: monthly, quarterly, annual (yearly is fine)")
    print("  - Profit / loss: profit, loss, break-even, profitable, losing money")
    print("  - Headcount: 12, 50 FTE, about 30 employees")
    print()


def run_turnaround_pipeline(client_problem: str) -> dict[str, Any]:
    """
    Execute the full consulting pipeline end-to-end.

    Returns a dict with keys: intake, finance, operations, strategy, review.
    Each value matches the shared shape from schemas.agent_output (six common
    fields everywhere; review also has priority_order).
    """
    pipeline_start = time.perf_counter()

    # Intake: frame the problem and align the team on facts, urgency, and data gaps.
    t = time.perf_counter()
    intake = run_intake_agent(client_problem)
    print(f"[timing] stage=intake elapsed_ms={int((time.perf_counter() - t) * 1000)}")

    # Parallel specialist workstreams.
    specialists_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=3) as executor:
        finance_future = executor.submit(run_finance_agent, intake)
        operations_future = executor.submit(run_operations_agent, intake)
        strategy_future = executor.submit(run_strategy_agent, intake)
        finance = finance_future.result()
        operations = operations_future.result()
        strategy = strategy_future.result()
    print(f"[timing] stage=specialists_parallel elapsed_ms={int((time.perf_counter() - specialists_start) * 1000)}")

    # Reviewer pass 1: decide whether one bounded follow-up round is needed.
    t = time.perf_counter()
    review_clarification_plan = run_reviewer_pass1(intake, finance, operations, strategy)
    print(f"[timing] stage=reviewer_pass1 elapsed_ms={int((time.perf_counter() - t) * 1000)}")

    # Controlled single clarification round (0 or 1 rounds only, <=3 questions).
    clarifications_start = time.perf_counter()
    review_clarification_answers: list[dict[str, Any]] = []
    if review_clarification_plan.get("needs_follow_up"):
        for item in review_clarification_plan.get("clarification_questions", [])[:3]:
            if not isinstance(item, dict):
                continue
            target = str(item.get("target_agent", "")).strip().lower()
            question = str(item.get("question", "")).strip()
            if not question:
                continue
            q_start = time.perf_counter()
            if target == "finance":
                lines = run_finance_clarification(intake, finance, question)
            elif target == "operations":
                lines = run_operations_clarification(intake, operations, question)
            elif target == "strategy":
                lines = run_strategy_clarification(intake, strategy, question)
            else:
                continue
            print(
                f"[timing] stage=clarification target={target} "
                f"elapsed_ms={int((time.perf_counter() - q_start) * 1000)}"
            )
            review_clarification_answers.append(build_clarification_answer(target, lines[:4]))
    print(f"[timing] stage=clarifications_total elapsed_ms={int((time.perf_counter() - clarifications_start) * 1000)}")

    # Reviewer pass 2: final integrated synthesis with explicit tradeoff resolution.
    t = time.perf_counter()
    review = run_reviewer_final_with_clarifications(
        intake,
        finance,
        operations,
        strategy,
        clarification_answers=review_clarification_answers,
    )
    print(f"[timing] stage=reviewer_pass2 elapsed_ms={int((time.perf_counter() - t) * 1000)}")
    print(f"[timing] stage=pipeline_total elapsed_ms={int((time.perf_counter() - pipeline_start) * 1000)}")

    return {
        "intake": intake,
        "finance": finance,
        "operations": operations,
        "strategy": strategy,
        "review_clarification_plan": review_clarification_plan,
        "review_clarification_answers": review_clarification_answers,
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

    ok, intake_errors = validate_intake_case(case, mode)
    if not ok:
        print(
            "\nSome inputs do not look valid yet. "
            "Please correct the fields below before running analysis."
        )
        for err in intake_errors:
            print(f"  - {err}")
        _print_intake_validation_help()
        raise SystemExit(0)

    client_problem = case_to_client_narrative(case)

    results = run_turnaround_pipeline(client_problem)
    founder_report = run_final_report_agent(
        results["intake"],
        results["finance"],
        results["operations"],
        results["strategy"],
        results["review"],
        case_text=client_problem,
        mode=mode,
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
