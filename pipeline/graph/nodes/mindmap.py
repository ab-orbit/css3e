from __future__ import annotations

from pipeline.graph.nodes._util import paper_json
from pipeline.graph.state import PipelineState
from pipeline.llm.client import run_structured
from pipeline.schemas.components import MindMapSpec


def gen_mindmap(state: PipelineState) -> dict:
    mindmap = run_structured(
        "mindmap", MindMapSpec, variables={"paper_analysis_json": paper_json(state)}
    )
    return {"mindmap": mindmap}
