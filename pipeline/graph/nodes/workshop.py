from __future__ import annotations

from pipeline.graph.nodes._util import paper_json
from pipeline.graph.state import PipelineState
from pipeline.llm.client import run_structured
from pipeline.schemas.components import WorkshopSpec


def gen_workshop(state: PipelineState) -> dict:
    workshop = run_structured(
        "workshop", WorkshopSpec, variables={"paper_analysis_json": paper_json(state)}
    )
    return {"workshop": workshop}
