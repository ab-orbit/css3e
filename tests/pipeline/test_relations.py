"""LLM relation inference over GLiNER entities.

The contract: a relation survives only if the model cited a sentence that
appears verbatim in the source AND mentions both endpoints. That check is what
keeps the hybrid honest — GLiNER anchors the entities, and this stops the LLM
from asserting an edge the paper never states.
"""

from __future__ import annotations

import logging

import pytest

from pipeline.config import Settings
from pipeline.extraction import relations as mod
from pipeline.extraction.relations import RawRelation, RawRelations, infer_relations
from pipeline.schemas.entities import Entity, EntityGraph, Mention

TEXT = (
    "Sistemas multiagentes coordenam agentes autonomos. "
    "A consciencia contextual aprimora sistemas multiagentes em ambientes dinamicos. "
    "Os agentes autonomos usam aprendizado por reforco profundo."
)


def _entity(key, name, freq=3):
    return Entity(
        key=key, name=name, label="Concept", score=0.9,
        mentions=[Mention(start=0, end=len(name), text=name) for _ in range(freq)],
    )


@pytest.fixture
def graph():
    return EntityGraph(
        entities=[
            _entity("sistemas multiagentes", "Sistemas multiagentes"),
            _entity("consciencia contextual", "A consciencia contextual"),
            _entity("agentes autonomos", "agentes autonomos"),
        ],
        engine="gliner=test",
    )


@pytest.fixture
def settings():
    return Settings(RELATION_MAX_COUNT=10)


def _stub(monkeypatch, items):
    monkeypatch.setattr(
        mod, "run_structured", lambda *a, **k: RawRelations(relations=items)
    )


class TestGrounding:
    def test_relation_with_a_verbatim_quote_survives(self, monkeypatch, graph, settings):
        _stub(monkeypatch, [
            RawRelation(
                source_key="consciencia contextual",
                target_key="sistemas multiagentes",
                label="aprimora",
                quote="A consciencia contextual aprimora sistemas multiagentes em ambientes dinamicos.",
            )
        ])
        kept = infer_relations(TEXT, graph, settings=settings)

        assert len(kept) == 1
        assert kept[0].label == "aprimora"
        assert kept[0].quote_start >= 0
        assert TEXT[kept[0].quote_start : kept[0].quote_start + len(kept[0].quote)] == kept[0].quote

    def test_fabricated_quote_is_dropped(self, monkeypatch, graph, settings, caplog):
        """The whole point: an edge whose evidence does not exist in the paper
        must never reach the published page.
        """
        _stub(monkeypatch, [
            RawRelation(
                source_key="sistemas multiagentes",
                target_key="agentes autonomos",
                label="substitui",
                quote="Sistemas multiagentes substituem completamente agentes autonomos.",
            )
        ])
        with caplog.at_level(logging.WARNING):
            kept = infer_relations(TEXT, graph, settings=settings)

        assert kept == []
        assert "not found in the source" in caplog.text

    def test_quote_is_matched_ignoring_whitespace_runs(self, monkeypatch, graph, settings):
        """PDF text carries line breaks and double spaces; a model re-typing
        the sentence normalizes them. Rejecting on whitespace alone would
        throw away true relations.
        """
        text = "A consciencia contextual   aprimora\nsistemas multiagentes hoje."
        _stub(monkeypatch, [
            RawRelation(
                source_key="consciencia contextual",
                target_key="sistemas multiagentes",
                label="aprimora",
                quote="A consciencia contextual aprimora sistemas multiagentes hoje.",
            )
        ])
        assert len(infer_relations(text, graph, settings=settings)) == 1

    def test_quote_must_mention_both_entities(self, monkeypatch, graph, settings, caplog):
        """A real sentence that does not actually contain both endpoints is not
        evidence for an edge between them.
        """
        _stub(monkeypatch, [
            RawRelation(
                source_key="sistemas multiagentes",
                target_key="agentes autonomos",
                label="usa",
                quote="Os agentes autonomos usam aprendizado por reforco profundo.",
            )
        ])
        with caplog.at_level(logging.WARNING):
            kept = infer_relations(TEXT, graph, settings=settings)

        assert kept == []
        assert "does not mention" in caplog.text


class TestHygiene:
    def test_unknown_entity_key_is_dropped(self, monkeypatch, graph, settings):
        _stub(monkeypatch, [
            RawRelation(source_key="sistemas multiagentes", target_key="fantasma",
                        label="usa", quote=TEXT.split(". ")[0] + ".")
        ])
        assert infer_relations(TEXT, graph, settings=settings) == []

    def test_self_relation_is_dropped(self, monkeypatch, graph, settings):
        _stub(monkeypatch, [
            RawRelation(source_key="agentes autonomos", target_key="agentes autonomos",
                        label="usa", quote="Os agentes autonomos usam aprendizado por reforco profundo.")
        ])
        assert infer_relations(TEXT, graph, settings=settings) == []

    def test_duplicate_pairs_collapse_to_one(self, monkeypatch, graph, settings):
        quote = "A consciencia contextual aprimora sistemas multiagentes em ambientes dinamicos."
        _stub(monkeypatch, [
            RawRelation(source_key="consciencia contextual", target_key="sistemas multiagentes",
                        label="aprimora", quote=quote),
            RawRelation(source_key="consciencia contextual", target_key="sistemas multiagentes",
                        label="beneficia", quote=quote),
        ])
        assert len(infer_relations(TEXT, graph, settings=settings)) == 1

    def test_results_are_capped(self, monkeypatch, graph, settings):
        settings.relation_max_count = 1
        quote_a = "A consciencia contextual aprimora sistemas multiagentes em ambientes dinamicos."
        quote_b = "Sistemas multiagentes coordenam agentes autonomos."
        _stub(monkeypatch, [
            RawRelation(source_key="consciencia contextual", target_key="sistemas multiagentes",
                        label="aprimora", quote=quote_a),
            RawRelation(source_key="sistemas multiagentes", target_key="agentes autonomos",
                        label="coordena", quote=quote_b),
        ])
        assert len(infer_relations(TEXT, graph, settings=settings)) == 1


class TestDegradation:
    def test_empty_graph_skips_the_llm_call(self, monkeypatch, settings):
        called = []
        monkeypatch.setattr(mod, "run_structured", lambda *a, **k: called.append(1))
        assert infer_relations(TEXT, EntityGraph(), settings=settings) == []
        assert not called

    def test_single_entity_skips_the_llm_call(self, monkeypatch, settings):
        called = []
        monkeypatch.setattr(mod, "run_structured", lambda *a, **k: called.append(1))
        graph = EntityGraph(entities=[_entity("a", "A")])
        assert infer_relations(TEXT, graph, settings=settings) == []
        assert not called

    def test_llm_failure_yields_no_relations_not_an_exception(
        self, monkeypatch, graph, settings, caplog
    ):
        """Relations are the optional half; a page with entities and no edges
        is still worth publishing.
        """
        def _boom(*a, **k):
            raise RuntimeError("openrouter 502")

        monkeypatch.setattr(mod, "run_structured", _boom)
        with caplog.at_level(logging.WARNING):
            assert infer_relations(TEXT, graph, settings=settings) == []
        assert "Relation inference failed" in caplog.text
