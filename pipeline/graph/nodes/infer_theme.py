from __future__ import annotations

import re

from pipeline.graph.state import PipelineState
from pipeline.llm.client import make_chat_model


def infer_theme(state: PipelineState) -> dict:
    """Only runs if --tema wasn't passed on the CLI."""
    if state.get("tema"):
        return {}

    model = make_chat_model(fast=True)
    prompt_template = _load()
    prompt = prompt_template.format(
        title=state["paper"].title,
        abstract=state["paper"].abstract,
        key_concepts=", ".join(state["paper"].key_concepts),
    )
    raw = model.invoke(prompt).content
    slug = re.sub(r"[^a-z0-9-]+", "-", str(raw).strip().lower()).strip("-")
    return {"tema": slug or "geral"}


def _load() -> str:
    from pipeline.llm.client import load_prompt

    return load_prompt("infer_theme")
