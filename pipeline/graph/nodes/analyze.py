from __future__ import annotations

from pipeline.graph.state import PipelineState
from pipeline.llm.client import run_structured
from pipeline.schemas.paper import PaperAnalysis


def analyze_paper(state: PipelineState) -> dict:
    """The one expensive, shared extraction pass. Every downstream node reads
    ONLY the resulting PaperAnalysis, never paper_text again.
    """
    source_pdf_url = str(state["pdf_path"])
    paper = run_structured(
        "analyze_paper",
        PaperAnalysis,
        variables={"paper_text": state["paper_text"], "source_pdf_url": source_pdf_url},
    )
    return {"paper": paper}
