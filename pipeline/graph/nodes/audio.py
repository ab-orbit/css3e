from __future__ import annotations

import logging

from pipeline.config import ARTICLES_DIR, get_settings
from pipeline.graph.state import PipelineState
from pipeline.media.notebooklm_client import NotebookLMError, generate_audio_overview

logger = logging.getLogger(__name__)


def generate_audio(state: PipelineState) -> dict:
    """Runs in the media branch, in parallel with the LLM fan-out — only
    needs the PDF + title, not any of the fine-grained content nodes.
    Never fails the whole build: missing credentials just means no audio.
    """
    settings = get_settings()
    tema = state.get("tema") or "geral"
    dest = ARTICLES_DIR / tema / state["slug"] / "audio" / f"{state['slug']}.m4a"
    try:
        generate_audio_overview(
            state["pdf_path"],
            title=state["slug"],
            dest_path=dest,
            settings=settings,
        )
    except NotebookLMError as exc:
        logger.warning("Skipping audio generation: %s", exc)
        return {"audio_path": None, "audio_title": None, "audio_subtitle": None}

    return {
        "audio_path": f"audio/{state['slug']}.m4a",
        "audio_title": f"Comentário em áudio: {state['slug']}",
        "audio_subtitle": "Faixa 01 · gerada via NotebookLM Audio Overview",
    }
