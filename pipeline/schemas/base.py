"""Base model for every schema the LLM fills in via tool-calling.

Some OpenRouter providers serialise a nested tool-call argument as a JSON
*string* instead of an object or array — a list of sections arrives as
'[\n  {"no": "01", ...}\n]'. Pydantic then fails the whole node, which on this
pipeline means losing a twenty-minute run to a provider quirk rather than to a
real modelling error. Parsing the string back before validation costs nothing
and keeps the run alive; anything that is not JSON, or a field that genuinely
expects text, is handed through untouched so real errors still surface.
"""

from __future__ import annotations

import json
import types
import typing
from typing import Any

from pydantic import BaseModel, model_validator


def _expects_text(annotation: Any) -> bool:
    """True when the field can legitimately hold a raw string."""
    if annotation is str:
        return True
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        return any(_expects_text(arg) for arg in typing.get_args(annotation))
    if origin is typing.Literal:
        return True
    return False


class CoercingModel(BaseModel):
    """Accepts JSON-stringified values for structured fields."""

    @model_validator(mode="before")
    @classmethod
    def _parse_stringified_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        patched: dict[str, Any] | None = None
        for name, field in cls.model_fields.items():
            key = name if name in data else field.alias
            if key is None or key not in data:
                continue
            value = data[key]
            if not isinstance(value, str) or _expects_text(field.annotation):
                continue
            text = value.strip()
            if not text.startswith(("{", "[")):
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue  # Not JSON: let pydantic report the real error.
            if patched is None:
                patched = dict(data)
            patched[key] = parsed

        return patched if patched is not None else data
