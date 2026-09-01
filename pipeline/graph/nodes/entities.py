from __future__ import annotations

import logging

from pipeline.config import get_settings
from pipeline.extraction.entities import EntityExtractionError, extract_entities
from pipeline.extraction.relations import infer_relations
from pipeline.graph.state import PipelineState
from pipeline.schemas.entities import EntityGraph

logger = logging.getLogger(__name__)


def gen_entities(state: PipelineState) -> dict:
    """Extract entities with GLiNER, then relations with the pipeline's LLM.

    Reads paper_text rather than the PaperAnalysis: entity offsets must address
    the text that was actually extracted, so that every entity on the published
    page points at a real span of the source.

    Fail-soft in two stages, like the media branch. No torch, no model, or an
    unmounted volume means no entities and the build continues. Entities
    without relations is also a valid outcome — the relation half degrades on
    its own inside infer_relations.
    """
    settings = get_settings()

    if not settings.entity_extraction:
        return {"entity_graph": EntityGraph()}

    try:
        graph = extract_entities(state["paper_text"], settings=settings)
    except EntityExtractionError as exc:
        logger.warning("Skipping entity extraction: %s", exc)
        return {"entity_graph": EntityGraph()}

    if graph.is_empty:
        return {"entity_graph": graph}

    graph.relations = infer_relations(state["paper_text"], graph, settings=settings)
    if graph.relations:
        graph.engine += ", relations=llm"

    logger.info(
        "Extracted %s entities and %s relations",
        len(graph.entities),
        len(graph.relations),
    )
    return {"entity_graph": graph}
