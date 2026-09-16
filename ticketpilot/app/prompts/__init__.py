"""Versioned prompt templates loaded from sibling ``*.md`` files (code_patterns §3).

Prompts never live inline in logic modules. Bump PROMPT_VERSIONS when a prompt changes so
downstream caches / baselines can pin to it.
"""

from pathlib import Path

PROMPT_VERSIONS = {
    "classify": "v1",
    "generate": "v1",
}

_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Read the prompt body for ``name`` (e.g. 'classify' -> classify.md)."""
    return (_DIR / f"{name}.md").read_text(encoding="utf-8")
