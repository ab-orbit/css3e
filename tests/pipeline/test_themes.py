"""Canonical theme registry.

infer_theme invents a fresh slug per run — three runs of the same paper
produced `sistemas-sensiveis-ao-contexto`, `sistemas-multi-agentes-contexto`
and `sistemas-multiagente-contexto`. The registry groups those drifting slugs
under one display theme so the gallery does not fragment.
"""

from __future__ import annotations

import pytest
import yaml

from pipeline.manifest.themes_yaml import (
    load_themes,
    register_tema,
    save_themes,
    theme_for_tema,
)
from pipeline.schemas.package import Theme

SAMPLE = [
    Theme(
        slug="css-context-sensitive-systems",
        name="CSS - Context Sensitive Systems",
        description="Sistemas que adaptam comportamento ao contexto.",
        temas=["sistemas-sensiveis-ao-contexto", "sistemas-multi-agentes-contexto"],
    )
]


@pytest.fixture
def registry(tmp_path):
    path = tmp_path / "themes.yaml"
    save_themes(SAMPLE, path)
    return path


class TestRoundTrip:
    def test_saved_registry_loads_back_equal(self, registry):
        assert load_themes(registry) == SAMPLE

    def test_missing_file_is_an_empty_registry(self, tmp_path):
        assert load_themes(tmp_path / "absent.yaml") == []

    def test_accents_survive_the_round_trip(self, tmp_path):
        path = tmp_path / "t.yaml"
        theme = Theme(slug="s", name="Sistemas Sensíveis", description="Ação e contexto.",
                      temas=["a"])
        save_themes([theme], path)
        assert load_themes(path)[0].name == "Sistemas Sensíveis"
        assert "Sensíveis" in path.read_text(encoding="utf-8")


class TestLookup:
    def test_finds_the_theme_owning_a_tema(self, registry):
        found = theme_for_tema("sistemas-multi-agentes-contexto", path=registry)
        assert found.slug == "css-context-sensitive-systems"

    def test_returns_none_for_an_unregistered_tema(self, registry):
        assert theme_for_tema("tema-novo-inesperado", path=registry) is None


class TestRegisterTema:
    def test_adds_a_tema_to_an_existing_theme(self, registry):
        register_tema("tema-novo", theme_slug="css-context-sensitive-systems", path=registry)
        theme = theme_for_tema("tema-novo", path=registry)
        assert theme.slug == "css-context-sensitive-systems"

    def test_registering_twice_does_not_duplicate(self, registry):
        register_tema("tema-novo", theme_slug="css-context-sensitive-systems", path=registry)
        register_tema("tema-novo", theme_slug="css-context-sensitive-systems", path=registry)
        theme = load_themes(registry)[0]
        assert theme.temas.count("tema-novo") == 1

    def test_unknown_tema_gets_its_own_theme_rather_than_vanishing(self, registry):
        """A run whose inferred tema matches no theme must still be reachable
        from a gallery; silently dropping it would orphan the article.
        """
        theme = register_tema("aprendizado-por-reforco", path=registry)

        assert theme.slug == "aprendizado-por-reforco"
        assert "aprendizado-por-reforco" in theme.temas
        assert theme.name == "Aprendizado Por Reforco"
        assert len(load_themes(registry)) == 2

    def test_existing_tema_is_returned_unchanged(self, registry):
        before = load_themes(registry)
        theme = register_tema("sistemas-sensiveis-ao-contexto", path=registry)

        assert theme.slug == "css-context-sensitive-systems"
        assert load_themes(registry) == before

    def test_registering_into_a_missing_theme_slug_is_an_error(self, registry):
        """Silently creating a theme from a typo'd slug would scatter articles
        across near-duplicate galleries — the exact failure this registry
        exists to prevent.
        """
        with pytest.raises(ValueError, match="no theme"):
            register_tema("x", theme_slug="slug-que-nao-existe", path=registry)


class TestFileShape:
    def test_yaml_is_human_editable(self, registry):
        """The registry is meant to be corrected by hand after a run adds a
        provisional theme, so it must stay readable."""
        raw = yaml.safe_load(registry.read_text(encoding="utf-8"))
        assert isinstance(raw, list)
        assert set(raw[0]) >= {"slug", "name", "temas"}
