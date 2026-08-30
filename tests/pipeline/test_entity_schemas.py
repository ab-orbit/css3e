"""Entity/relation model behaviour."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pipeline.schemas.entities import Entity, EntityGraph, Mention, Relation


def _entity(key, *, label="Concept", score=0.9, mentions=1):
    return Entity(
        key=key,
        name=key.upper(),
        label=label,
        score=score,
        mentions=[Mention(start=i * 10, end=i * 10 + 5, text=key[:5]) for i in range(mentions)],
    )


def test_relevance_ranks_frequent_and_confident_above_rare():
    frequent = _entity("mas", score=0.8, mentions=10)
    rare = _entity("xyz", score=0.99, mentions=1)
    assert frequent.relevance > rare.relevance


def test_top_entities_orders_by_relevance():
    graph = EntityGraph(
        entities=[_entity("a", mentions=1), _entity("b", mentions=9), _entity("c", mentions=5)]
    )
    assert [e.key for e in graph.top_entities(2)] == ["b", "c"]


def test_connected_relations_drops_orphaned_edges():
    """Pruning entities can orphan a relation; drawing a dangling edge would
    put an unlabelled node on the published page.
    """
    graph = EntityGraph(
        entities=[_entity("cas"), _entity("mas")],
        relations=[
            Relation(source_key="cas", target_key="mas", label="integrates with", score=0.8),
            Relation(source_key="cas", target_key="pruned", label="uses", score=0.7),
        ],
    )
    kept = graph.connected_relations()
    assert len(kept) == 1
    assert kept[0].target_key == "mas"


def test_score_must_be_a_probability():
    with pytest.raises(ValidationError):
        Entity(key="x", name="X", label="Concept", score=1.5)


def test_empty_graph_is_reported_as_empty():
    assert EntityGraph().is_empty
    assert not EntityGraph(entities=[_entity("a")]).is_empty


def test_mention_length():
    assert Mention(start=10, end=25, text="x" * 15).length == 15
