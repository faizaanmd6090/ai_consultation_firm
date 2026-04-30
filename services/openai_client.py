"""
Thin wrapper around the OpenAI Responses API (Phase 4+).

- Reads OPENAI_API_KEY from the environment (set via .env + load_dotenv in app.py or your shell).
- Uses client.responses.create (not Chat Completions), per OpenAI's Responses API.
- Shared by intake, finance, operations, strategy, reviewer, and any future agents; no tools or chains.
- Exceptions bubble to agents so they can log and use mock fallbacks.

Docs: https://platform.openai.com/docs/guides/migrate-to-responses
"""

from __future__ import annotations

import os
import time
from typing import Any

from openai import OpenAI

# Single model for all OpenAI-powered agents; change here if you switch models.
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TIMEOUT_S = float(os.environ.get("OPENAI_TIMEOUT_S", "90"))


def _require_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to a .env file in the project root "
            "or export it in your terminal before running python app.py."
        )
    return key


def generate_agent_response(instructions: str, user_input: str) -> str:
    """
    Send instructions + user input to the model; return aggregated text (often JSON).

    Tries JSON object mode first; if the SDK rejects it, retries with default text format.
    """
    client = OpenAI(api_key=_require_api_key())

    base_kwargs: dict[str, Any] = {
        "model": OPENAI_MODEL,
        "instructions": instructions,
        "input": user_input,
        "timeout": OPENAI_TIMEOUT_S,
    }

    call_start = time.perf_counter()
    try:
        response = client.responses.create(
            **base_kwargs,
            text={"format": {"type": "json_object"}},
        )
        print(
            f"[timing] openai_call mode=json_object model={OPENAI_MODEL} "
            f"elapsed_ms={int((time.perf_counter() - call_start) * 1000)}"
        )
    except Exception as exc:
        print(f"[warn] openai_json_object_mode_failed: {exc}")
        retry_start = time.perf_counter()
        response = client.responses.create(**base_kwargs)
        print(
            f"[timing] openai_call mode=text_fallback model={OPENAI_MODEL} "
            f"elapsed_ms={int((time.perf_counter() - retry_start) * 1000)}"
        )

    return (response.output_text or "").strip()


def generate_intake_response(instructions: str, user_input: str) -> str:
    """Backward-compatible alias used by intake_agent."""
    return generate_agent_response(instructions, user_input)
