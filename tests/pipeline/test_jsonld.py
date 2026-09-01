"""schema.org JSON-LD emitted per article.

Consumers are search engines and LLM answer engines, both of which fail
silently on a malformed graph — so the shape is asserted here rather than
eyeballed.
"""

from __future__ import annotations

import json

import pytest

from pipeline.render.jsonld import build_jsonld, render_jsonld_script
from pipeline.schemas.entities import Entity, EntityGraph, Mention, Relation
from tests.pipeline.fixtures.sample_package import make_sample_package

SITE = "https://example.test/"


def _entity(key, name, label="Concept", freq=3, score=0.9):
    return Entity(
        key=key, name=name, label=label, score=score,
        mentions=[Mention(start=i * 50, end=i * 50 + len(name), text=name) for i in range(freq)],
    )


@pytest.fixture
def graph():
    return EntityGraph(
        entities=[
            _entity("context aware systems", "Context-Aware Systems", freq=9),
            _entity("multi agent systems", "Multi-Agent Systems", freq=7),
            _entity("gliner", "GLiNER", label="Software", freq=2),
        ],
        relations=[
            Relation(
                source_key="context aware systems",
                target_key="multi agent systems",
                label="integrates with",
                score=0.82,
                quote="A integração de CAS em MAS torna-se essencial.",
                quote_start=1200,
            )
        ],
        engine="gliner=urchade/gliner_multi-v2.1",
    )


@pytest.fixture
def doc(graph):
    pkg = make_sample_package()
    return build_jsonld(pkg, graph, site_base_url=SITE, page_path="articles/t/s/index.html")


class TestScholarlyArticle:
    def _article(self, doc):
        return next(n for n in doc["@graph"] if n["@type"] == "ScholarlyArticle")

    def test_context_is_schema_org(self, doc):
        assert doc["@context"] == "https://schema.org"

    def test_article_carries_identity_and_url(self, doc):
        article = self._article(doc)
        assert article["name"]
        assert article["url"].startswith(SITE)
        assert article["@id"].startswith(SITE)

    def test_authors_are_person_nodes(self, doc):
        authors = self._article(doc)["author"]
        assert authors and all(a["@type"] == "Person" for a in authors)
        assert all(a["name"] for a in authors)

    def test_doi_becomes_an_identifier(self, doc):
        article = self._article(doc)
        assert "identifier" in article

    def test_about_holds_the_top_entities_as_defined_terms(self, doc):
        about = self._article(doc)["about"]
        assert all(t["@type"] == "DefinedTerm" for t in about)
        # Ranked by relevance, so the most-mentioned concept leads.
        assert about[0]["name"] == "Context-Aware Systems"

    def test_every_entity_appears_somewhere(self, doc):
        article = self._article(doc)
        named = {t["name"] for t in article.get("about", [])} | {
            t["name"] for t in article.get("mentions", [])
        }
        assert named == {"Context-Aware Systems", "Multi-Agent Systems", "GLiNER"}

    def test_overflow_beyond_the_primary_cap_lands_in_mentions(self):
        """`about` claims the article is PRIMARILY about a term, so it is
        capped; everything past the cap must still be published as `mentions`.
        """
        from pipeline.render.jsonld import PRIMARY_TOPIC_COUNT

        many = EntityGraph(
            entities=[
                _entity(f"e{i}", f"Entidade {i}", freq=PRIMARY_TOPIC_COUNT + 5 - i)
                for i in range(PRIMARY_TOPIC_COUNT + 4)
            ]
        )
        doc = build_jsonld(make_sample_package(), many, site_base_url=SITE, page_path="p.html")
        article = next(n for n in doc["@graph"] if n["@type"] == "ScholarlyArticle")

        assert len(article["about"]) == PRIMARY_TOPIC_COUNT
        assert len(article["mentions"]) == 4

    def test_an_entity_is_never_in_both_about_and_mentions(self):
        """Duplicating a term across both properties makes the graph
        self-contradictory about what the article is primarily about.
        """
        from pipeline.render.jsonld import PRIMARY_TOPIC_COUNT

        many = EntityGraph(
            entities=[
                _entity(f"e{i}", f"Entidade {i}", freq=20 - i)
                for i in range(PRIMARY_TOPIC_COUNT + 4)
            ]
        )
        doc = build_jsonld(make_sample_package(), many, site_base_url=SITE, page_path="p.html")
        article = next(n for n in doc["@graph"] if n["@type"] == "ScholarlyArticle")

        assert not (
            {t["name"] for t in article["about"]} & {t["name"] for t in article["mentions"]}
        )


class TestRelations:
    def test_relations_travel_outside_schema_org_properties(self, doc):
        """schema.org has no general triple mechanism, so relations ride in a
        namespaced key. Search engines ignore it; LLM readers can use it.
        """
        assert "css3e:relations" in doc
        assert doc["css3e:relations"][0]["label"] == "integrates with"

    def test_a_relation_carries_the_passage_that_supports_it(self, doc):
        relation = doc["css3e:relations"][0]
        assert relation["quote"]
        assert relation["source"] == "Context-Aware Systems"
        assert relation["target"] == "Multi-Agent Systems"

    def test_orphaned_relations_are_dropped(self):
        graph = EntityGraph(
            entities=[_entity("a", "A")],
            relations=[Relation(source_key="a", target_key="ghost", label="uses", score=0.9)],
        )
        doc = build_jsonld(make_sample_package(), graph, site_base_url=SITE, page_path="p.html")
        assert doc["css3e:relations"] == []


class TestEmptyGraph:
    def test_article_is_still_valid_without_entities(self):
        """Extraction is fail-soft, so the JSON-LD must survive an empty graph
        rather than emitting an article with empty required properties.
        """
        doc = build_jsonld(
            make_sample_package(), EntityGraph(), site_base_url=SITE, page_path="p.html"
        )
        article = next(n for n in doc["@graph"] if n["@type"] == "ScholarlyArticle")
        assert article["name"]
        assert "about" not in article or article["about"] == []


class TestScriptRendering:
    def test_output_is_parseable_json(self, doc):
        html = render_jsonld_script(doc)
        payload = html.split(">", 1)[1].rsplit("<", 1)[0]
        assert json.loads(payload)

    def test_script_tag_is_correctly_typed(self, doc):
        assert render_jsonld_script(doc).startswith('<script type="application/ld+json">')

    def test_closing_tag_in_content_cannot_break_out_of_the_script(self):
        """An entity name containing </script> would otherwise terminate the
        block early and inject markup into the page.
        """
        graph = EntityGraph(entities=[_entity("x", "</script><img src=x onerror=alert(1)>")])
        doc = build_jsonld(make_sample_package(), graph, site_base_url=SITE, page_path="p.html")
        html = render_jsonld_script(doc)
        assert "</script><img" not in html
        assert html.count("</script>") == 1

    def test_unicode_survives_intact(self, doc):
        graph = EntityGraph(entities=[_entity("acao", "Ação e Coordenação")])
        rendered = render_jsonld_script(
            build_jsonld(make_sample_package(), graph, site_base_url=SITE, page_path="p.html")
        )
        assert "Ação e Coordenação" in rendered


class TestInPage:
    """The block has to reach the page as markup, not as escaped text."""

    def _page(self):
        from pipeline.config import Settings as S
        from pipeline.render.build import RenderContext, render_article_package

        pkg = make_sample_package()
        ctx = RenderContext(
            asset_prefix="../../../", pdf_relative_href="p.pdf",
            og_image_url="https://example.test/og.png", site_base_url=SITE,
            publisher_name="Pub", brand_label="B",
        )
        seo = {s.page_kind: s for s in pkg.seo_pages}
        return render_article_package(pkg, seo, ctx, S())["index.html"]

    def test_script_tag_is_real_markup(self):
        """Jinja2 autoescaping turned the whole block into &lt;script&gt;...,
        publishing the graph as visible text that no consumer can read.
        """
        html = self._page()

        assert "&lt;script type=&#34;application/ld+json&#34;&gt;" not in html
        assert '<script type="application/ld+json">' in html

    def test_the_page_graph_parses_and_carries_the_article(self):
        import re

        html = self._page()
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S
        )
        graphs = [json.loads(b.replace("<\\/", "</")) for b in blocks]

        assert any("@graph" in g for g in graphs), "no @graph block reached the page"
