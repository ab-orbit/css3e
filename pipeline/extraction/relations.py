"""Relations between GLiNER entities, inferred by the pipeline's LLM.

This is the second half of a hybrid: GLiNER anchors the entities with exact
character offsets, and the LLM decides which of them the paper actually
relates, and in which direction.

The split exists because GLiREL, measured on this corpus, could not do the
second job. At window level its top score was 0.031 with both directions of a
pair tied; at sentence level (0.363, ten times better) the semantically correct
direction still lost to its inverse by 0.05. It detects that two entities are
related without telling you which way the relation runs.

What keeps the LLM half honest is grounding: every relation must cite a
sentence, that sentence must appear in the source text, and it must mention
both endpoints. Anything else is dropped with a warning. The model can be
wrong about a relation, but it cannot invent evidence for one.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from pydantic import BaseModel, Field

from pipeline.config import Settings
from pipeline.llm.client import run_structured
from pipeline.schemas.entities import EntityGraph, Relation

logger = logging.getLogger(__name__)

# How much of the paper the model sees. Relations worth publishing are stated
# in the argument, not buried in the reference list.
CONTEXT_CHARS = 40_000


class RawRelation(BaseModel):
    """One relation as the model proposes it, before grounding."""

    source_key: str = Field(description="`key` of the entity that exerts the relation")
    target_key: str = Field(description="`key` of the entity that receives it")
    label: str = Field(description="Short verbal label in Portuguese")
    quote: str = Field(description="Sentence copied verbatim from the source")


class RawRelations(BaseModel):
    relations: list[RawRelation] = Field(default_factory=list)


def _normalize_whitespace(text: str) -> str:
    """Collapse whitespace runs so a re-typed quote can still match.

    PDF text is full of line breaks and double spaces; a model quoting a
    sentence normalizes them. Rejecting on whitespace alone would discard true
    relations for a formatting difference.
    """
    return re.sub(r"\s+", " ", text).strip()


def _fold(text: str) -> str:
    """Casefold and strip accents, for the "does the quote mention it" check.

    Only used for that containment test — never for locating the quote, whose
    offset must point at the real characters.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def infer_relations(
    text: str, graph: EntityGraph, *, settings: Settings
) -> list[Relation]:
    """Ask the LLM which of `graph`'s entities the paper relates, then verify.

    Never raises: relations are the optional half of the graph, and a page with
    entities and no edges is still worth publishing.
    """
    if len(graph.entities) < 2:
        # Nothing to relate — skip the call rather than pay for a guaranteed
        # empty answer.
        return []

    entity_list = "\n".join(
        f"- {e.key} — {e.name} — {e.label} — {e.frequency} menções"
        for e in graph.entities
    )

    try:
        proposed = run_structured(
            "relations",
            RawRelations,
            variables={
                "entity_list": entity_list,
                "paper_text": text[:CONTEXT_CHARS],
                "max_relations": str(settings.relation_max_count),
            },
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001 - optional half, degrade quietly
        logger.warning("Relation inference failed, publishing entities only: %s", exc)
        return []

    return _ground(proposed.relations, text, graph, settings)


def _ground(
    proposed: list[RawRelation],
    text: str,
    graph: EntityGraph,
    settings: Settings,
) -> list[Relation]:
    """Keep only relations whose evidence checks out against the source."""
    known = {e.key: e for e in graph.entities}
    haystack = _normalize_whitespace(text)
    folded_haystack = _fold(haystack)

    kept: list[Relation] = []
    seen_pairs: set[frozenset[str]] = set()

    for item in proposed:
        if item.source_key not in known or item.target_key not in known:
            logger.warning(
                "Dropping relation with unknown entity: %s -> %s",
                item.source_key,
                item.target_key,
            )
            continue

        if item.source_key == item.target_key:
            continue

        # One edge per pair: the same two entities asserted twice with
        # different labels would draw two arrows between the same nodes.
        pair = frozenset({item.source_key, item.target_key})
        if pair in seen_pairs:
            continue

        quote = _normalize_whitespace(item.quote)
        if not quote:
            continue

        position = folded_haystack.find(_fold(quote))
        if position == -1:
            logger.warning(
                "Dropping relation %s --%s--> %s: quote not found in the source",
                item.source_key,
                item.label,
                item.target_key,
            )
            continue

        folded_quote = _fold(quote)
        source_name = _fold(known[item.source_key].name)
        target_name = _fold(known[item.target_key].name)
        if not _mentions(folded_quote, source_name) or not _mentions(
            folded_quote, target_name
        ):
            logger.warning(
                "Dropping relation %s --%s--> %s: quote does not mention both entities",
                item.source_key,
                item.label,
                item.target_key,
            )
            continue

        seen_pairs.add(pair)
        kept.append(
            Relation(
                source_key=item.source_key,
                target_key=item.target_key,
                label=item.label,
                # The LLM gives no calibrated probability. Reporting a fake one
                # would be worse than reporting the verified fact: grounded.
                score=1.0,
                quote=quote[: settings.relation_quote_chars],
                quote_start=_locate(text, quote),
            )
        )
        if len(kept) >= settings.relation_max_count:
            break

    return kept


def _mentions(folded_quote: str, folded_name: str) -> bool:
    """Whether the quote refers to an entity.

    Falls back to the longest word of a multi-word name: GLiNER's display form
    may carry a leading article ("A consciencia contextual") that the sentence
    in the paper does not repeat verbatim at that position.
    """
    if folded_name in folded_quote:
        return True
    words = [w for w in folded_name.split() if len(w) > 3]
    return bool(words) and all(w in folded_quote for w in words)


def _locate(text: str, normalized_quote: str) -> int:
    """Offset of the quote in the ORIGINAL text, or -1.

    The normalized form is used for matching, but the offset has to address the
    real characters, so a direct hit is tried first and a whitespace-tolerant
    regex second.
    """
    direct = text.find(normalized_quote)
    if direct != -1:
        return direct

    pattern = r"\s+".join(re.escape(word) for word in normalized_quote.split())
    match = re.search(pattern, text)
    return match.start() if match else -1
