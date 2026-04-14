"""
Intake agent (engagement manager / problem framing).

Phase 4 (revised): loads prompts/intake_prompt.md, sends it plus the client problem
to OpenAI via the Responses API, and maps the reply into the shared six-field shape
from schemas.agent_output.

If the API call fails (missing key, network, rate limit, etc.), returns a
deterministic mock intake so the rest of the pipeline still runs.

Other agents remain mocks for now.
"""

from __future__ import annotations

import json
from typing import Any

from schemas.agent_output import standard_report
from services.openai_client import generate_intake_response
from utils.prompt_loader import load_prompt

_JSON_SHAPE_INSTRUCTION = """
You must respond with only a JSON object with keys:
summary (string), findings (array of strings), risks (array of strings),
recommendations (array of strings), assumptions (array of strings).
Do not include markdown fences or commentary outside the JSON.
"""


def _coerce_str_list(value: Any) -> list[str]:
    """Turn model output into a clean list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif item is not None and not isinstance(item, (dict, list)):
                s = str(item).strip()
                if s:
                    out.append(s)
            elif isinstance(item, dict):
                s = json.dumps(item, ensure_ascii=False)
                if s:
                    out.append(s)
        return out
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _unwrap_object(data: dict[str, Any]) -> dict[str, Any]:
    """If the model nests everything under one key, unwrap one level."""
    core_keys = {"summary", "findings", "risks", "recommendations", "assumptions"}
    if core_keys <= data.keys():
        return data
    if len(data) == 1:
        inner = next(iter(data.values()))
        if isinstance(inner, dict):
            return _unwrap_object(inner)
    return data


def _parse_model_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise TypeError("Model JSON root must be an object")
    return _unwrap_object(parsed)


def _fallback_from_raw(raw: str) -> dict[str, Any]:
    """If JSON parsing fails, still return a valid standard_report."""
    snippet = (raw or "").strip()[:500]
    return standard_report(
        agent_name="intake",
        summary=snippet or "Empty model response.",
        findings=[
            "Intake could not parse the model reply as JSON; see summary for the raw fragment."
        ],
        risks=[],
        recommendations=[],
        assumptions=[],
    )


def _mock_intake_report(client_problem: str) -> dict[str, Any]:
    """
    Deterministic fallback when the OpenAI call fails (offline, quota, bad key, etc.).
    Mirrors the original Phase 1 mock behavior.
    """
    text = (client_problem or "").strip()
    lowered = text.lower()

    mentions_cash = "cash" in lowered
    mentions_margin = "margin" in lowered
    mentions_retention = "retention" in lowered or "customer" in lowered
    mentions_discount = "discount" in lowered

    summary = (
        "The client presents a turnaround situation: meaningful revenue scale coexists "
        "with sustained losses, eroding margins, and liquidity pressure. "
        "Commercial symptoms (pricing/discounting and retention) suggest both "
        "P&L and go-to-market issues that need coordinated finance, operations, "
        "and strategy workstreams."
    )
    if text:
        summary += " The narrative below anchors the case on the client's own words."
    summary += " (Mock intake: OpenAI call unavailable.)"

    findings = [
        "Revenue exists at scale, but profit conversion is weak—multi-year losses point to structural drivers, not a one-off shock.",
        "Rising costs and shrinking margins indicate either unit economics pressure, mix shift toward lower-margin revenue, or both.",
        "Cash constraints increase execution risk: turnaround actions must be sequenced with a clear liquidity guardrail.",
    ]
    if mentions_cash:
        findings.append(
            "Explicit cash runway concerns imply near-term decisions on payables, capex, and working capital need early attention."
        )
    if mentions_margin:
        findings.append(
            "Margin compression should be decomposed into price, variable cost, and fixed cost buckets to prioritize levers."
        )
    if mentions_retention or mentions_discount:
        findings.append(
            "Falling retention and aggressive discounting often signal weak pricing architecture and/or service delivery gaps."
        )

    risks = [
        "Without a single source of truth on cash and covenant headroom, the team may recommend actions the business cannot fund.",
        "If leadership treats this as purely a cost-cutting exercise, revenue quality can deteriorate further during the fix.",
        "Data gaps on customer-level profitability can mis-prioritize segments and worsen losses while appearing 'busy'.",
    ]

    recommendations = [
        "Issue a 2-week data request list: monthly P&L bridge, cash forecast, AR/AP aging, customer cohort retention, and discount policy.",
        "Stand up a weekly turnaround cadence: liquidity first, then margin levers, then growth reinvestment—no parallel unfunded initiatives.",
        "Define a baseline 'must-win' quarter: stop-loss rules on discounting and a short list of highest-value customer segments.",
    ]

    assumptions = [
        "Management can produce management accounts and a 13-week cash view within the next few business days.",
        "No material undisclosed litigation or regulatory freeze is blocking operational change.",
        "Revenue is not collapsing imminently; the primary near-term failure mode is liquidity and margin discipline.",
    ]

    return standard_report(
        agent_name="intake",
        summary=summary,
        findings=findings,
        risks=risks,
        recommendations=recommendations,
        assumptions=assumptions,
    )


def run_intake_agent(client_problem: str) -> dict:
    """
    Call OpenAI with the intake prompt + client problem; return standard_report.

    On API errors, returns _mock_intake_report so the pipeline keeps running.
    """
    markdown_instructions = load_prompt("prompts/intake_prompt.md")
    system_instruction = (
        markdown_instructions.strip()
        + "\n\n"
        + _JSON_SHAPE_INSTRUCTION.strip()
    ).strip()

    user_message = (
        "Client problem:\n"
        + (client_problem or "").strip()
        + "\n\n"
        "Produce the JSON object described in your instructions."
    )

    try:
        raw_text = generate_intake_response(
            instructions=system_instruction,
            user_input=user_message,
        )
    except Exception as exc:
        print(f"OpenAI intake failed: {exc}")
        print("Using fallback mock intake output.")
        return _mock_intake_report(client_problem)

    if not raw_text:
        return _fallback_from_raw("")

    try:
        obj = _parse_model_json(raw_text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return _fallback_from_raw(raw_text)

    summary = obj.get("summary", "")
    if not isinstance(summary, str):
        summary = str(summary) if summary is not None else ""

    return standard_report(
        agent_name="intake",
        summary=summary.strip(),
        findings=_coerce_str_list(obj.get("findings")),
        risks=_coerce_str_list(obj.get("risks")),
        recommendations=_coerce_str_list(obj.get("recommendations")),
        assumptions=_coerce_str_list(obj.get("assumptions")),
    )
