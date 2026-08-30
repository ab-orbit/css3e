from __future__ import annotations

import logging

from pydantic import BaseModel

from pipeline.config import published_pdf_name
from pipeline.graph.nodes._util import paper_json
from pipeline.graph.state import PipelineState
from pipeline.llm.client import run_structured
from pipeline.schemas.components import DownloadItem


logger = logging.getLogger(__name__)


class _Downloads(BaseModel):
    items: list[DownloadItem]


def gen_downloads(state: PipelineState) -> dict:
    """Build the downloads grid, restricted to this article's own files.

    Every href is validated against the set handed to the prompt. The model
    previously invented a site-wide "Simuladores" link because the prompt asked
    for one; nothing but an explicit check keeps a generated href inside the
    article's own folder.
    """
    audio_href = state.get("audio_path") or ""
    slides_href = state.get("slides_pdf_path") or state.get("slides_pptx_path") or ""
    allowed = {
        published_pdf_name(state["slug"]),
        "blog.html",
        audio_href,
        slides_href,
    } - {""}

    result = run_structured(
        "downloads",
        _Downloads,
        variables={
            "has_audio": str(bool(audio_href)),
            "has_slides": str(bool(slides_href)),
            "pdf_relative_href": published_pdf_name(state["slug"]),
            "blog_relative_href": "blog.html",
            "audio_relative_href": audio_href,
            "slides_relative_href": slides_href,
            "paper_analysis_json": paper_json(state),
        },
    )

    kept = []
    for item in result.items:
        if item.href in allowed:
            kept.append(item)
        else:
            logger.warning(
                "Dropping download %r: href %r is not one of this article's files",
                item.title,
                item.href,
            )
    return {"downloads": kept}
