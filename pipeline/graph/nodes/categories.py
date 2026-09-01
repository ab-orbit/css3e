from __future__ import annotations

from pydantic import BaseModel

from pipeline.graph.nodes._util import paper_json
from pipeline.graph.state import PipelineState
from pipeline.llm.client import run_structured
from pipeline.schemas.components import CategoryCard


class _CategoryCards(BaseModel):
    cards: list[CategoryCard]


def gen_categories(state: PipelineState) -> dict:
    result = run_structured(
        "categories", _CategoryCards, variables={"paper_analysis_json": paper_json(state)}
    )
    return {"categories": result.cards}
