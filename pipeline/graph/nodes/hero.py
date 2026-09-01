from __future__ import annotations

from pipeline.graph.nodes._util import paper_json
from pipeline.graph.state import PipelineState
from pipeline.llm.client import run_structured
from pipeline.schemas.components import HeroMeta


def gen_hero(state: PipelineState) -> dict:
    hero = run_structured(
        "hero", HeroMeta, variables={"paper_analysis_json": paper_json(state)}
    )
    return {"hero": hero}
