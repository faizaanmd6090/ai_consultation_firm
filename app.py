"""
AI management consulting simulator (Phase 1 mock logic, Phase 2 structure).

This script models a small multi-agent workflow similar to how a turnaround
engagement might be staffed (intake, finance, operations, strategy, review).
All five stages use OpenAI when configured (with mock fallbacks on failure).

When you run this file, you type your business problem in the terminal; the
pipeline runs on that text (multiline is supported—finish with an empty line).

Phase 2: every agent's return value is built through helpers in
schemas/agent_output.py so the dict keys stay consistent and easy to maintain.

Phase 3: each agent loads its Markdown instructions from prompts/ via
utils/prompt_loader.py on every run.

Phase 4–6: agents use OpenAI's Responses API (see services/openai_client.py).
Phase 6 adds OpenAI-backed operations and reviewer agents.
Set OPENAI_API_KEY (e.g. in a .env file loaded below) and install requirements.txt.

Example problem you could paste when prompted:
    Revenue is flat, costs are up, and we are burning cash. Retention is weak.

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

_VAGUE_INPUTS = {
    "hi",
    "hello",
    "heyy",
    "hey",
    "help",
    "test",
    "ok",
}

_BUSINESS_KEYWORDS = {
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
}


def read_client_problem() -> str:
    """
    Prompt for the client's situation in the terminal.

    Reads one or more lines until the user enters a blank line, then joins
    them with newlines. If nothing was typed, asks again.
    """
    while True:
        print("Describe your company situation:")
        print("(Type your problem. Press Enter on an empty line when you are done.)")
        lines: list[str] = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        text = "\n".join(lines).strip()
        if text:
            return text
        print("Please enter at least a short description.\n")


def validate_client_problem(text: str) -> tuple[bool, str]:
    """
    Basic guardrail before running the multi-agent analysis.

    Returns (is_valid, reason_if_invalid).
    """
    cleaned = text.strip().lower()
    words = [w.strip(".,!?;:()[]{}\"'") for w in cleaned.split() if w.strip()]

    if not words:
        return False, "No input detected."
    if cleaned in _VAGUE_INPUTS:
        return False, "Input is too vague."
    if len(words) < 8:
        return False, "Please provide a bit more detail (at least 8 words)."
    if not any(keyword in cleaned for keyword in _BUSINESS_KEYWORDS):
        return False, "Please include business context (for example revenue, costs, margins, customers, or cash)."
    return True, ""


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
    answer = input("\nShow detailed agent outputs? (y/N): ").strip().lower()
    return answer in {"y", "yes"}


if __name__ == "__main__":
    # Load project-root .env into os.environ so OPENAI_API_KEY is available to the intake agent.
    load_dotenv()

    client_problem = read_client_problem()
    is_valid, reason = validate_client_problem(client_problem)
    if not is_valid:
        print("Please describe a real company situation before running the consulting analysis.")
        print(f"Reason: {reason}")
        print(
            "Example input: Our company has had 3 years of losses despite strong revenue. "
            "Costs are rising, margins are shrinking, and customer retention is falling. "
            "We need a turnaround plan."
        )
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
