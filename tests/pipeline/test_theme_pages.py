"""Theme tg generation."""

from __future__ import annotations

import pytest

from pipeline.config import Settings
from pipeline.manifest.theme_pages import build_theme_page, entries_for_theme
from pipeline.schemas.package import ManifestEntry, Theme

THEME = Theme(
    slug="css-context-sensitive-systems",
    name="CSS - Context Sensitive Systems",
    description="Sistemas que adaptam comportamento ao contexto.",
    temas=["tema-a", "tema-b"],
)


def _entry(slug, tema="tema-a", status="published", **kw):
    return ManifestEntry(
        slug=slug, tema=tema, title=f"Title {slug}", pdf_source="x.pdf",
        authors=["Autor Um"], date_published="2026-01-01",
        pages={"article": f"articles/{tema}/{slug}/index.html"},
        briefing=kw.pop("briefing", f"Briefing de {slug}."), status=status, **kw,
    )


class TestSelection:
    def test_collects_entries_from_every_tema_of_the_theme(self):
        entries = entries_for_theme(
            THEME, [_entry("a", "tema-a"), _entry("b", "tema-b"), _entry("c", "tema-fora")]
        )
        assert {e.slug for e in entries} == {"a", "b"}

    def test_drafts_are_excluded(self):
        entries = entries_for_theme(THEME, [_entry("a"), _entry("rascunho", status="draft")])
        assert {e.slug for e in entries} == {"a"}

    def test_copies_of_root_pages_are_included(self):
        """A copy is still a real published page a reader can open."""
        entries = entries_for_theme(THEME, [_entry("copia", status="copy-of-root")])
        assert [e.slug for e in entries] == ["copia"]

    def test_newest_first(self):
        velho = _entry("velho")
        novo = _entry("novo")
        novo.date_published = "2026-12-31"

        assert [e.slug for e in entries_for_theme(THEME, [velho, novo])] == ["novo", "velho"]


class TestLinks:
    def test_card_links_at_the_page_the_entry_actually_has(self):
        """Some entries publish only a workshop page. Linking a card at
        index.html regardless produces a 404 for those.
        """
        only_workshop = ManifestEntry(
            slug="dinamica", tema="tema-a", title="Dinâmica", pdf_source="x.pdf",
            authors=["A"], date_published="2026-01-01",
            pages={"workshop": "articles/tema-a/dinamica/workshop.html"},
            briefing="b", status="published",
        )
        html = build_theme_page(THEME, [only_workshop], settings=Settings())

        assert "../tema-a/dinamica/workshop.html" in html
        assert "../tema-a/dinamica/index.html" not in html

    def test_prefers_the_article_page_when_several_exist(self):
        full = _entry("completo")
        full.pages = {
            "article": "articles/tema-a/completo/index.html",
            "blog": "articles/tema-a/completo/blog.html",
            "workshop": "articles/tema-a/completo/workshop.html",
        }
        html = build_theme_page(THEME, [full], settings=Settings())
        # Anchor inside the cards section: the console's JS carries a card
        # template string that would otherwise match first.
        cards = html.split('data-view="cards"', 1)[1].split('data-view="list"', 1)[0]
        card = cards.split('class="tg-card-hit" href="', 1)[1]

        assert card.startswith("../tema-a/completo/index.html")


class TestHrefsComeFromTheManifest:
    def test_uses_the_recorded_path_not_a_reconstructed_one(self):
        """An entry's page may live in a directory that is not <tema>/<slug>.
        `three-categories-of-cas-workshop` publishes into the
        `three-categories-of-cas` folder it shares, so rebuilding the href from
        tema+slug produced a 404.
        """
        shared = ManifestEntry(
            slug="tres-categorias-workshop", tema="tema-a", title="Dinâmica",
            pdf_source="x.pdf", authors=["A"], date_published="2026-01-01",
            pages={"workshop": "articles/tema-a/tres-categorias/workshop.html"},
            briefing="b", status="published",
        )
        html = build_theme_page(THEME, [shared], settings=Settings())

        assert "../tema-a/tres-categorias/workshop.html" in html
        assert "tres-categorias-workshop/" not in html

    def test_paths_are_made_relative_to_the_gallery(self):
        entry = _entry("a")
        entry.pages = {"article": "articles/tema-a/a/index.html"}
        html = build_theme_page(THEME, [entry], settings=Settings())

        assert "../tema-a/a/index.html" in html
        assert 'href="articles/' not in html


class TestRendering:
    @pytest.fixture
    def html(self):
        return build_theme_page(
            THEME,
            [_entry("a"), _entry("b", "tema-b", has_audio=True, has_slides=True)],
            settings=Settings(SITE_BASE_URL="https://example.test/"),
        )

    def test_shows_the_theme_name_and_description(self, html):
        assert "CSS - Context Sensitive Systems" in html
        assert "Sistemas que adaptam comportamento ao contexto." in html

    def test_every_article_has_a_card_with_its_briefing(self, html):
        assert "Briefing de a." in html
        assert "Briefing de b." in html

    def test_links_point_at_the_article_pages(self, html):
        assert "../tema-a/a/index.html" in html
        assert "../tema-b/b/index.html" in html

    def test_media_badges_reflect_the_manifest(self, html):
        """Only the entry with media gets badges — and it gets them in BOTH
        views, so the count is per view, not per page.
        """
        cards = html.split('data-view="cards"', 1)[1].split('data-view="list"', 1)[0]

        assert cards.count('class="tg-badge tg-badge-audio"') == 1
        assert cards.count('class="tg-badge tg-badge-deck"') == 1

    def test_both_views_are_present_with_cards_as_default(self, html):
        assert 'data-view="cards"' in html
        assert 'data-view="list"' in html
        assert 'data-active-view="cards"' in html

    def test_briefing_appears_in_the_list_view_too(self, html):
        """The user asked for a briefing in BOTH views, so the list cannot
        degrade into bare titles."""
        list_section = html.split('data-view="list"', 1)[1]
        assert "Briefing de a." in list_section

    def test_page_is_a_complete_document(self, html):
        assert html.strip().startswith("<!doctype html>")
        assert "</html>" in html

    def test_canonical_is_absolute(self, html):
        assert 'rel="canonical"' in html
        assert "https://example.test/articles/css-context-sensitive-systems/" in html

    def test_empty_theme_still_renders(self):
        html = build_theme_page(THEME, [], settings=Settings())
        assert "CSS - Context Sensitive Systems" in html
