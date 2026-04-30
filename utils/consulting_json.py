"""
Shared JSON parsing for OpenAI-powered consulting agents (Phase 5+).

Each specialist is instructed to return one JSON object with the standard fields.
The reviewer adds priority_order. These helpers turn model text into the dict
shape used by schemas.agent_output.
"""

from __future__ import annotations

import json
from typing import Any

from schemas.agent_output import reviewer_report, standard_report

JSON_SHAPE_INSTRUCTION = """
You must respond with only a JSON object with keys:
summary (string), findings (array of strings), risks (array of strings),
recommendations (array of strings), assumptions (array of strings).
Do not include markdown fences or commentary outside the JSON.
"""

REVIEWER_JSON_SHAPE_INSTRUCTION = """
You must respond with only a JSON object with keys:
summary (string), findings (array of strings), risks (array of strings),
recommendations (array of strings), assumptions (array of strings),
priority_order (array of strings, ranked most important first).
Do not include markdown fences or commentary outside the JSON.
"""

_STANDARD_KEYS = frozenset(
    {"summary", "findings", "risks", "recommendations", "assumptions"}
)
_REVIEWER_KEYS = frozenset(
    {
        "summary",
        "findings",
        "risks",
        "recommendations",
        "assumptions",
        "priority_order",
    }
)


def coerce_str_list(value: Any) -> list[str]:
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


def unwrap_object(
    data: dict[str, Any],
    required_subset: frozenset[str] | None = None,
) -> dict[str, Any]:
    """If the model nests everything under one key, unwrap one level."""
    core_keys = required_subset or _STANDARD_KEYS
    if core_keys <= data.keys():
        return data
    if len(data) == 1:
        inner = next(iter(data.values()))
        if isinstance(inner, dict):
            return unwrap_object(inner, required_subset)
    return data


def parse_model_json(raw: str) -> dict[str, Any]:
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
    return unwrap_object(parsed, _STANDARD_KEYS)


def parse_reviewer_model_json(raw: str) -> dict[str, Any]:
    """Parse reviewer JSON including priority_order."""
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
    return unwrap_object(parsed, _REVIEWER_KEYS)


def standard_report_from_parsed(obj: dict[str, Any], agent_name: str) -> dict[str, Any]:
    """Map a parsed JSON object into the shared six-field report."""
    summary = obj.get("summary", "")
    if not isinstance(summary, str):
        summary = str(summary) if summary is not None else ""

    return standard_report(
        agent_name=agent_name,
        summary=summary.strip(),
        findings=coerce_str_list(obj.get("findings")),
        risks=coerce_str_list(obj.get("risks")),
        recommendations=coerce_str_list(obj.get("recommendations")),
        assumptions=coerce_str_list(obj.get("assumptions")),
    )


def reviewer_report_from_parsed(
    obj: dict[str, Any], agent_name: str = "reviewer"
) -> dict[str, Any]:
    """Map a parsed reviewer JSON object into standard fields plus priority_order."""
    summary = obj.get("summary", "")
    if not isinstance(summary, str):
        summary = str(summary) if summary is not None else ""

    return reviewer_report(
        agent_name=agent_name,
        summary=summary.strip(),
        findings=coerce_str_list(obj.get("findings")),
        risks=coerce_str_list(obj.get("risks")),
        recommendations=coerce_str_list(obj.get("recommendations")),
        assumptions=coerce_str_list(obj.get("assumptions")),
        priority_order=coerce_str_list(obj.get("priority_order")),
    )
