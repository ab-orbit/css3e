"""Entities and relations extracted from the paper text.

Every entity carries the character offsets it was found at, so any claim on the
published page can be traced back to the exact span of source text that
supports it. That provenance is the reason this pipeline uses span-based
models (GLiNER/GLiREL) instead of asking an LLM for a list of concepts.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Mention(BaseModel):
    """One occurrence of an entity in the source text."""

    start: int = Field(description="Character offset into the full extracted text")
    end: int
    text: str = Field(description="The exact surface form as it appears at [start:end]")

    @property
    def length(self) -> int:
        return self.end - self.start


class Entity(BaseModel):
    """A deduplicated entity, with every place it was mentioned."""

    key: str = Field(description="Normalized form used for deduplication, e.g. 'ca-mas'")
    name: str = Field(description="Display form — the most frequent surface variant")
    label: str = Field(description="Entity type, e.g. Method, Task, Concept, System")
    score: float = Field(ge=0.0, le=1.0, description="Mean model confidence across mentions")
    mentions: list[Mention] = Field(default_factory=list)

    @property
    def frequency(self) -> int:
        return len(self.mentions)

    @property
    def relevance(self) -> float:
        """Ranking signal: something said often AND confidently outranks
        something said once with high confidence, or often with low.
        """
        return self.frequency * self.score


class Relation(BaseModel):
    """A directed relation between two entities, grounded in one passage."""

    source_key: str
    target_key: str
    label: str = Field(description="Relation type, e.g. 'is part of', 'uses', 'evaluates'")
    score: float = Field(ge=0.0, le=1.0)
    quote: str = Field(
        default="",
        description="Passage the relation was read from — what makes it auditable",
    )
    quote_start: int = Field(default=-1, description="Offset of `quote`, -1 if unknown")


class EntityGraph(BaseModel):
    """Fan-in shape: what gen_entities contributes to the ArticlePackage."""

    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    engine: str = Field(default="", description="Model versions used, for reproducibility")

    @property
    def is_empty(self) -> bool:
        return not self.entities

    def entity_by_key(self, key: str) -> Entity | None:
        return next((e for e in self.entities if e.key == key), None)

    def top_entities(self, limit: int) -> list[Entity]:
        return sorted(self.entities, key=lambda e: e.relevance, reverse=True)[:limit]

    def connected_relations(self) -> list[Relation]:
        """Relations whose both endpoints survived entity filtering.

        Pruning entities can orphan a relation; rendering a dangling edge would
        put an unlabelled node on the page.
        """
        keys = {e.key for e in self.entities}
        return [r for r in self.relations if r.source_key in keys and r.target_key in keys]
