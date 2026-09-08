"""Reading and writing the prompt files under pipeline/llm/prompts/.

Split out of `client` so the media layer can read a prompt without importing
LangChain, and so the authoring console has one place to persist an edited
prompt. A saved prompt is an ordinary file change: it shows up as a diff in
git, which is what makes "save as default" reviewable rather than magic.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Load a prompt .md file from pipeline/llm/prompts/<name>.md."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"No prompt file at {path}")
    return path.read_text(encoding="utf-8")


def save_prompt(name: str, text: str) -> Path:
    """Overwrite a prompt file and drop the cached copy.

    The cache is what makes every later read see the new text; without the
    invalidation a saved prompt would only take effect on the next restart,
    which is exactly the kind of surprise an authoring tool must not have.
    """
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"No prompt file at {path}")
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    load_prompt.cache_clear()
    return path


def render_prompt(
    template: str, variables: dict[str, str], *, prompt_name: str = "<inline>"
) -> str:
    """Substitute {name} placeholders, leaving every other brace untouched.

    NOT str.format: the prompts are Portuguese prose that uses braces as
    ordinary notation (e.g. "uma lista de atributos {label, texto}"), and
    str.format reads those as placeholders and dies with a KeyError. Only the
    names explicitly passed in `variables` are ever substituted.

    Raises KeyError if a declared variable has no placeholder in the template —
    that is a silently-dropped input, which would send a subtly wrong prompt to
    the model rather than fail.
    """
    missing = [name for name in variables if "{" + name + "}" not in template]
    if missing:
        raise KeyError(
            f"Prompt {prompt_name!r} has no placeholder for: {sorted(missing)}. "
            f"Either add {{{missing[0]}}} to the template or stop passing it."
        )
    for name, value in variables.items():
        template = template.replace("{" + name + "}", value)
    return template
