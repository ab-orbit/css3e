from __future__ import annotations

from pipeline.schemas.base import CoercingModel

from pipeline.graph.nodes._util import paper_json
from pipeline.graph.state import PipelineState
from pipeline.llm.client import run_structured
from pipeline.schemas.components import CategoryCard


class _CategoryCards(CoercingModel):
    cards: list[CategoryCard]


def gen_categories(state: PipelineState) -> dict:
    result = run_structured(
        "categories", _CategoryCards, variables={"paper_analysis_json": paper_json(state)}
    )
    return {"categories": result.cards}
