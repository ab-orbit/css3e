from __future__ import annotations

from pipeline.graph.nodes._util import paper_json
from pipeline.graph.state import PipelineState
from pipeline.llm.client import run_structured
from pipeline.schemas.components import EssayVariant


def gen_essay_condensed(state: PipelineState) -> dict:
    essay = run_structured(
        "essay",
        EssayVariant,
        variables={"paper_analysis_json": paper_json(state), "variant": "condensed"},
    )
    return {"essay_condensed": essay}


def gen_essay_full(state: PipelineState) -> dict:
    essay = run_structured(
        "essay",
        EssayVariant,
        variables={"paper_analysis_json": paper_json(state), "variant": "full"},
    )
    return {"essay_full": essay}
