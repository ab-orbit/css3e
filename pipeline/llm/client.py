"""ChatOpenAI pointed at OpenRouter's OpenAI-compatible endpoint.

Model ids follow OpenRouter's `provider/model-name` convention
(e.g. "anthropic/claude-sonnet-4.5", "openai/gpt-4o-mini").
Structured output uses tool-calling (`.with_structured_output(Schema)`),
not raw JSON-mode parsing, since it's reliably supported across the
model families this project is likely to use.
"""

from __future__ import annotations

from typing import TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from pipeline.config import Settings, get_settings
from pipeline.llm.prompt_store import PROMPTS_DIR, load_prompt, render_prompt, save_prompt

__all__ = ["PROMPTS_DIR", "load_prompt", "save_prompt", "make_chat_model", "render_prompt", "run_structured"]

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

T = TypeVar("T", bound=BaseModel)


def make_chat_model(settings: Settings | None = None, *, fast: bool = False) -> ChatOpenAI:
    settings = settings or get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    model = settings.openrouter_model_fast if fast else settings.openrouter_model
    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url=OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": settings.site_base_url,
            "X-Title": "CSS3E article-to-site pipeline",
        },
        temperature=0.3,
    )


# Re-exported: prompt IO lives in prompt_store so the media layer can read a
# prompt without importing LangChain.


def run_structured(
    prompt_name: str,
    schema: type[T],
    *,
    variables: dict[str, str] | None = None,
    fast: bool = False,
    settings: Settings | None = None,
) -> T:
    """Fill a prompt template's {placeholder}s from `variables`, send it to the
    configured OpenRouter model, and return a validated instance of `schema`
    via tool-calling structured output.
    """
    template = load_prompt(prompt_name)
    prompt = render_prompt(template, variables or {}, prompt_name=prompt_name)
    # method="function_calling" is explicit on purpose. Left to its default,
    # langchain-openai negotiates OpenAI's native structured-outputs path
    # (response_format + strict json_schema), which OpenRouter does not enforce
    # uniformly across providers: the model answers with prose Markdown and the
    # strict parser dies with "Invalid JSON: expected value at line 1 column 1".
    # Tool-calling is supported by every model family this project targets.
    model = make_chat_model(settings, fast=fast).with_structured_output(
        schema, method="function_calling"
    )
    result = model.invoke(prompt)
    if not isinstance(result, schema):
        raise RuntimeError(
            f"Prompt {prompt_name!r} returned {type(result).__name__}, expected "
            f"{schema.__name__}. The model likely ignored the tool call."
        )
    return result
