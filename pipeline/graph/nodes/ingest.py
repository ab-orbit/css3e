from __future__ import annotations

from pipeline.config import get_settings
from pipeline.extraction.pdf import extract_text
from pipeline.graph.state import PipelineState


def ingest_pdf(state: PipelineState) -> dict:
    settings = get_settings()
    text = extract_text(state["pdf_path"], settings)
    return {"paper_text": text}
