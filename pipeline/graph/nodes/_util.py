from __future__ import annotations

from pipeline.graph.state import PipelineState


def paper_json(state: PipelineState) -> str:
    return state["paper"].model_dump_json(indent=2)
