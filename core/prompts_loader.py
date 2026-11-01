"""Loads prompt templates from core/prompts/*.md and fills the {{placeholders}}.

Prompts live in files (core/prompts/README.md) so each step's prompt can be read, diffed
and swapped on its own. Placeholders look like {{name}}; we use plain text replacement,
so curly braces in the JSON examples inside prompts are safe.
"""

from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"


def render_prompt(name: str, **values: str) -> str:
    text = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text
