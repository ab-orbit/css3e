from __future__ import annotations

import logging

from pipeline.config import ARTICLES_DIR, get_settings
from pipeline.graph.state import PipelineState
from pipeline.media.notebooklm_client import NotebookLMError, generate_slide_deck

logger = logging.getLogger(__name__)


def generate_slides(state: PipelineState) -> dict:
    """Generates the deck in NotebookLM and downloads it as both PPTX and PDF,
    stored alongside the page. Nothing leaves the repo: the PDF is what the
    page embeds (browsers cannot render a .pptx inline) and the PPTX is the
    editable download, so the deck needs no Google Drive credentials, no
    upload/convert step, and no manual "anyone with the link" sharing.

    slides_preview_url/edit_url stay available as an optional override for an
    article whose deck really does live in Google Slides — set them with
    `pipeline set-slides` and deck_embed.html.j2 will prefer them. Left None
    here, the page falls back to the self-hosted PDF.

    Never fails the whole build: missing credentials or a NotebookLM outage
    just means no deck.
    """
    settings = get_settings()
    tema = state.get("tema") or "geral"
    slides_dir = ARTICLES_DIR / tema / state["slug"] / "slides"

    try:
        generate_slide_deck(
            state["pdf_path"],
            title=state["slug"],
            pptx_dest=slides_dir / "deck.pptx",
            pdf_dest=slides_dir / "deck.pdf",
            settings=settings,
        )
    except NotebookLMError as exc:
        logger.warning("Skipping slide generation: %s", exc)
        return {"slides_pptx_path": None, "slides_pdf_path": None}

    return {"slides_pptx_path": "slides/deck.pptx", "slides_pdf_path": "slides/deck.pdf"}
