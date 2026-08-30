"""Extraction logic, with the models faked.

The value under test is what the pipeline owns: offset remapping across
windows, deduplication of the same entity seen twice through overlap, label
and surface-form resolution, and fail-soft behaviour. The models themselves
are exercised by the end-to-end run, not here — loading 2GB of weights in a
unit test would make the suite unusable.
"""

from __future__ import annotations

import logging

import pytest

from pipeline.config import Settings
from pipeline.extraction import entities as mod
from pipeline.extraction.entities import (
    EntityExtractionError,
    _normalize_key,
    extract_entities,
    resolve_device,
)


@pytest.fixture
def settings():
    return Settings(
        ENTITY_EXTRACTION=True,
        ENTITY_CHUNK_CHARS=120,
        ENTITY_CHUNK_OVERLAP=30,
        ENTITY_MAX_COUNT=10,
        RELATION_MAX_COUNT=10,
    )


class FakeGliner:
    """Returns whatever spans the test plants, at window-local offsets."""

    def __init__(self, plant):
        self._plant = plant
        self.windows_seen: list[str] = []

    def predict_entities(self, text, labels, threshold=0.5):
        self.windows_seen.append(text)
        found = []
        for surface, label, score in self._plant:
            index = text.find(surface)
            if index != -1:
                found.append(
                    {"text": surface, "label": label, "score": score,
                     "start": index, "end": index + len(surface)}
                )
        return found


def _install(monkeypatch, plant, *, glirel_exc=EntityExtractionError("no glirel")):
    fake = FakeGliner(plant)
    monkeypatch.setattr(mod, "_load_gliner", lambda *a, **k: fake)

    def _boom(*a, **k):
        raise glirel_exc

    monkeypatch.setattr(mod, "_load_glirel", _boom)
    return fake


class TestNormalizeKey:
    @pytest.mark.parametrize(
        "surface",
        ["Multi-Agent Systems", "multi agent systems", "Multi-Agent  Systems", "MULTI_AGENT_SYSTEMS"],
    )
    def test_surface_variants_share_one_key(self, surface):
        assert _normalize_key(surface) == "multi agent systems"

    def test_punctuation_is_dropped_and_hyphens_become_spaces(self):
        """The hyphen folds to a space by design — that is what makes
        "Multi-Agent Systems" and "multi agent systems" one key.
        """
        assert _normalize_key("CA-MAS,") == "ca mas"
        assert _normalize_key("(GLiNER).") == "gliner"

    def test_acronym_stays_distinct_from_its_expansion(self):
        """Merging them needs coreference, which these models do not do —
        guessing would silently fuse unrelated entities.
        """
        assert _normalize_key("MAS") != _normalize_key("Multi-Agent Systems")


class TestExtractEntities:
    def test_empty_text_short_circuits(self, settings):
        assert extract_entities("   ", settings=settings).is_empty

    def test_offsets_point_at_the_real_span_in_the_full_text(self, monkeypatch, settings):
        """The whole reason for span models: a reported offset must locate the
        entity in the ORIGINAL text, not in the window it was found in.
        """
        text = ("preenchimento " * 40) + "Context-Aware Systems" + (" cauda" * 40)
        _install(monkeypatch, [("Context-Aware Systems", "Concept", 0.9)])

        graph = extract_entities(text, settings=settings)

        entity = graph.entity_by_key("context aware systems")
        assert entity is not None
        for mention in entity.mentions:
            assert text[mention.start : mention.end] == "Context-Aware Systems"

    def test_same_occurrence_seen_through_overlap_counts_once(self, monkeypatch, settings):
        """Windows overlap by design, so a single occurrence is often predicted
        twice. Counting it twice would inflate its ranking.
        """
        text = "a" * 100 + " Multi-Agent Systems " + "b" * 200
        _install(monkeypatch, [("Multi-Agent Systems", "Concept", 0.9)])

        graph = extract_entities(text, settings=settings)

        entity = graph.entity_by_key("multi agent systems")
        starts = [m.start for m in entity.mentions]
        assert len(starts) == len(set(starts))
        assert entity.frequency == 1

    def test_display_name_is_the_most_frequent_surface_form(self, monkeypatch, settings):
        text = "CAS aqui. " * 5 + "Context-Aware Systems uma vez."
        _install(monkeypatch, [("CAS", "Concept", 0.8)])

        graph = extract_entities(text, settings=settings)
        assert graph.entity_by_key("cas").name == "CAS"

    def test_label_is_decided_by_summed_confidence(self, monkeypatch, settings):
        text = "GLiNER " * 10
        _install(monkeypatch, [("GLiNER", "Software", 0.95)])

        graph = extract_entities(text, settings=settings)
        assert graph.entity_by_key("gliner").label == "Software"

    def test_results_are_capped_and_ranked_by_relevance(self, monkeypatch, settings):
        settings.entity_max_count = 2
        text = " ".join(["alpha"] * 9 + ["beta"] * 5 + ["gamma"] * 1)
        _install(
            monkeypatch,
            [("alpha", "Concept", 0.9), ("beta", "Concept", 0.9), ("gamma", "Concept", 0.9)],
        )

        graph = extract_entities(text, settings=settings)

        assert len(graph.entities) == 2
        assert [e.key for e in graph.entities] == ["alpha", "beta"]

    def test_a_failing_window_does_not_lose_the_others(self, monkeypatch, settings, caplog):
        """One bad window must not discard a whole paper's extraction."""
        text = "Sistema Alfa. " * 30

        class Flaky(FakeGliner):
            calls = 0

            def predict_entities(self, text, labels, threshold=0.5):
                Flaky.calls += 1
                if Flaky.calls == 1:
                    raise RuntimeError("CUDA blew up")
                return super().predict_entities(text, labels, threshold)

        flaky = Flaky([("Sistema Alfa", "System", 0.9)])
        monkeypatch.setattr(mod, "_load_gliner", lambda *a, **k: flaky)
        monkeypatch.setattr(mod, "_load_glirel", lambda *a, **k: (_ for _ in ()).throw(
            EntityExtractionError("skip")))

        with caplog.at_level(logging.WARNING):
            graph = extract_entities(text, settings=settings)

        assert not graph.is_empty
        assert "GLiNER failed" in caplog.text

    def test_returns_entities_only(self, monkeypatch, settings):
        """Relations are no longer this module's job. GLiREL was measured on
        this corpus and could not resolve direction (both orderings of a pair
        tied at window level), so relations moved to pipeline.extraction.
        relations, where an LLM infers them and every one must cite a verified
        sentence.
        """
        _install(monkeypatch, [("Alfa", "Concept", 0.9)])

        graph = extract_entities("Alfa " * 20, settings=settings)

        assert not graph.is_empty
        assert graph.relations == []
        assert "glirel" not in graph.engine

    def test_engine_records_the_model_used(self, monkeypatch, settings):
        """Reproducibility: the page should be able to say what produced it."""
        _install(monkeypatch, [("Alfa", "Concept", 0.9)])
        graph = extract_entities("Alfa " * 10, settings=settings)
        assert settings.gliner_model in graph.engine


class TestResolveDevice:
    def test_explicit_device_is_honoured(self):
        assert resolve_device("cpu") == "cpu"

    def test_falls_back_to_cpu_without_torch(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def _no_torch(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("no torch")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _no_torch)
        assert resolve_device("auto") == "cpu"
