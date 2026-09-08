from __future__ import annotations

from pipeline.schemas.base import CoercingModel

from pipeline.graph.nodes._util import paper_json
from pipeline.graph.state import PipelineState
from pipeline.llm.client import run_structured
from pipeline.schemas.components import TableSpec


class _Tables(CoercingModel):
    tables: list[TableSpec]


def gen_tables(state: PipelineState) -> dict:
    result = run_structured(
        "tables", _Tables, variables={"paper_analysis_json": paper_json(state)}
    )
    return {"tables": result.tables}
