"""
Load Markdown prompt files from the project (Phase 3).

These files describe how each agent should behave when you later connect an LLM.
Right now agents only read the text into a variable; mock outputs stay unchanged.
"""

from __future__ import annotations

from pathlib import Path


# Project root = parent of the `utils/` folder (works when you run `python app.py` from repo root).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_prompt(relative_path: str) -> str:
    """
    Read a UTF-8 text file under the project root.

    Args:
        relative_path: Path relative to project root, e.g. "prompts/intake_prompt.md".

    Returns:
        File contents as a string (may be empty if the file is empty).
    """
    path = _PROJECT_ROOT / relative_path
    return path.read_text(encoding="utf-8")
