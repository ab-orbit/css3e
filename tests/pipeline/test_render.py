from pipeline.config import Settings
from pipeline.render.build import RenderContext, render_article_package
from tests.pipeline.fixtures.sample_package import make_sample_package


def _ctx() -> RenderContext:
    return RenderContext(
        asset_prefix="../../../",
        pdf_relative_href="../../../tests/pipeline/fixtures/sample.pdf",
        og_image_url="https://example.test/three-categories.png",
        site_base_url="https://example.test/",
        publisher_name="Test Publisher",
        brand_label="Sample Paper Title",
    )


def test_render_produces_three_pages():
    pkg = make_sample_package()
    seo_by_kind = {seo.page_kind: seo for seo in pkg.seo_pages}
    pages = render_article_package(pkg, seo_by_kind, _ctx(), Settings())

    assert set(pages) == {"index.html", "blog.html", "workshop.html"}
    for html in pages.values():
        assert html.strip().startswith("<!doctype html>")
        assert "<html lang=\"pt-BR\">" in html


def test_index_page_contains_hero_categories_and_mindmap_data():
    pkg = make_sample_package()
    seo_by_kind = {seo.page_kind: seo for seo in pkg.seo_pages}
    pages = render_article_package(pkg, seo_by_kind, _ctx(), Settings())
    index_html = pages["index.html"]

    assert "Sample Paper Title" in index_html
    assert "CAT-A" in index_html and "CAT-B" in index_html
    assert '"t": "Sample Paper Title"' in index_html or '"t":"Sample Paper Title"' in index_html.replace(" ", "")
    assert "var PALETTE" in index_html
    assert "resources/cases/style.css" in index_html


def test_blog_page_contains_essay_sections():
    pkg = make_sample_package()
    seo_by_kind = {seo.page_kind: seo for seo in pkg.seo_pages}
    pages = render_article_package(pkg, seo_by_kind, _ctx(), Settings())
    blog_html = pages["blog.html"]

    assert "First section" in blog_html
    assert "A pull quote." in blog_html


def test_workshop_page_contains_both_tracks():
    pkg = make_sample_package()
    seo_by_kind = {seo.page_kind: seo for seo in pkg.seo_pages}
    pages = render_article_package(pkg, seo_by_kind, _ctx(), Settings())
    workshop_html = pages["workshop.html"]

    assert "Visão do participante" in workshop_html
    assert "Visão do facilitador" in workshop_html
    assert "Reflita sobre X." in workshop_html
    assert "Apresente o tema." in workshop_html


def test_seo_head_has_valid_jsonld():
    import json
    import re

    pkg = make_sample_package()
    seo_by_kind = {seo.page_kind: seo for seo in pkg.seo_pages}
    pages = render_article_package(pkg, seo_by_kind, _ctx(), Settings())

    for html in pages.values():
        match = re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.S)
        assert match, "missing JSON-LD block"
        data = json.loads(match.group(1))
        assert data["@context"] == "https://schema.org"
        assert data["headline"]


def _render_index(**overrides) -> str:
    """Render index.html from the sample package with the deck fields overridden."""
    pkg = make_sample_package()
    for field, value in overrides.items():
        setattr(pkg, field, value)
    seo_by_kind = {seo.page_kind: seo for seo in pkg.seo_pages}
    return render_article_package(pkg, seo_by_kind, _ctx(), Settings())["index.html"]


def test_deck_embeds_self_hosted_pdf_by_default():
    """With no Google Slides URL, the deck section embeds the article's own
    deck.pdf — the whole point of dropping the Drive dependency.
    """
    html = _render_index(
        slides_pdf_path="slides/deck.pdf",
        slides_pptx_path="slides/deck.pptx",
        slides_preview_url=None,
        slides_edit_url=None,
    )

    assert 'src="slides/deck.pdf#view=FitH"' in html
    assert "Deck em PDF · hospedado neste site" in html
    assert 'href="slides/deck.pptx" download' in html
    assert "docs.google.com" not in html
    assert "Slides pendentes" not in html


def test_deck_prefers_google_slides_when_url_is_set():
    """The manual `pipeline set-slides` override still wins over the local PDF."""
    html = _render_index(
        slides_pdf_path="slides/deck.pdf",
        slides_pptx_path="slides/deck.pptx",
        slides_preview_url="https://docs.google.com/presentation/d/abc/preview",
        slides_edit_url="https://docs.google.com/presentation/d/abc/edit",
    )

    assert 'src="https://docs.google.com/presentation/d/abc/preview"' in html
    assert "Google Slides · prévia incorporada" in html
    assert "slides/deck.pdf#view=FitH" not in html


def test_deck_shows_pending_notice_without_any_deck():
    html = _render_index(
        slides_pdf_path=None,
        slides_pptx_path=None,
        slides_preview_url=None,
        slides_edit_url=None,
    )

    assert "Slides pendentes" in html
    assert "<iframe" not in html.split('id="slides"')[1].split("</section>")[0]
