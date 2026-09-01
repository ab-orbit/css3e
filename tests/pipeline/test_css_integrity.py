"""Guards against CSS that fails silently.

An undefined custom property invalidates the entire declaration it appears in,
with no error anywhere: `padding: 46px var(--gut)` where --gut is defined
nowhere computed to padding:0, gluing the blog cover's text to its border.
Nothing in the pipeline noticed, because a browser drops the rule quietly.
"""

from __future__ import annotations

import re

import pytest

from pipeline.config import REPO_ROOT, SHARED_STYLESHEET, Settings
from pipeline.render.build import RenderContext, render_article_package
from tests.pipeline.fixtures.sample_package import make_sample_package


def _rendered_pages() -> dict[str, str]:
    pkg = make_sample_package()
    ctx = RenderContext(
        asset_prefix="../../../",
        pdf_relative_href="sample-paper.pdf",
        og_image_url="https://example.test/og.png",
        site_base_url="https://example.test/",
        publisher_name="Test Publisher",
        brand_label="Sample",
    )
    seo_by_kind = {seo.page_kind: seo for seo in pkg.seo_pages}
    return render_article_package(pkg, seo_by_kind, ctx, Settings())


SHARED_CSS = REPO_ROOT / SHARED_STYLESHEET


def _strip_css_comments(css: str) -> str:
    """Drop /* ... */ blocks. A comment naming a variable (like the one
    documenting the --gut bug) is not a usage of it.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


@pytest.mark.parametrize("page", ["index.html", "blog.html", "workshop.html"])
def test_every_css_variable_used_is_defined(page):
    """Every var(--x) a page references must be declared either inline or in the
    shared stylesheet the page links. --gut was in neither.
    """
    html = _strip_css_comments(_rendered_pages()[page])
    shared = SHARED_CSS.read_text(encoding="utf-8")

    used = set(re.findall(r"var\(\s*(--[\w-]+)", html))
    declared = set(re.findall(r"(--[\w-]+)\s*:", html + shared))

    undefined = sorted(used - declared)
    assert not undefined, (
        f"{page} references CSS variables that are never declared: {undefined}. "
        "An undefined var() invalidates its whole declaration silently."
    )


def test_blog_cover_band_has_real_padding():
    """The statement block must be inset from its border on both axes."""
    html = _rendered_pages()["blog.html"]

    rule = re.search(r"\.post-cover \.band\{([^}]*)\}", html)
    assert rule, "the .post-cover .band rule disappeared"

    padding = re.search(r"padding:([^;]+)", rule.group(1))
    assert padding, "the band has no padding"
    value = padding.group(1)
    assert "var(" not in value or "--gut" not in value
    assert len(value.split()) >= 2, f"expected vertical and horizontal padding, got {value!r}"


def test_blog_cover_statement_is_justified():
    html = _rendered_pages()["blog.html"]
    rule = re.search(r"\.post-cover \.band b\{([^}]*)\}", html)

    assert rule, "no rule styling the statement itself"
    assert "text-align:justify" in rule.group(1)
    assert "hyphens:auto" in rule.group(1), (
        "justification without hyphenation opens rivers of whitespace"
    )


def _theme_page() -> str:
    from pipeline.manifest.theme_pages import build_theme_page
    from pipeline.schemas.package import ManifestEntry, Theme

    theme = Theme(slug="t", name="Tema", description="d", temas=["tema-a"])
    entry = ManifestEntry(
        slug="a", tema="tema-a", title="T", pdf_source="x.pdf", authors=["A"],
        date_published="2026-01-01", pages={"article": "articles/tema-a/a/index.html"},
        briefing="B", status="published",
    )
    return build_theme_page(theme, [entry], settings=Settings())


def _class_selectors(css: str) -> set[str]:
    """Class names a stylesheet defines a `display` for.

    Only display matters here: that is the property whose collision silently
    restructures a layout.
    """
    found = set()
    for match in re.finditer(r"\.([\w-]+)\s*(?:,[^{]*)?\{([^}]*)\}", _strip_css_comments(css)):
        if "display:" in match.group(2):
            found.add(match.group(1))
    return found


def test_gallery_classes_do_not_collide_with_the_shared_stylesheet():
    """`.gallery` was already defined in resources/cases/style.css as a
    five-column grid. Reusing the name turned the theme page's container into
    that grid, laying the toolbar, the cards and the list side by side in
    189px columns. Nothing failed — it just rendered wrong.
    """
    gallery_css = (
        REPO_ROOT
        / "pipeline/render/templates/partials/theme_gallery.css.j2"
    ).read_text(encoding="utf-8")

    mine = _class_selectors(gallery_css)
    shared = _class_selectors(SHARED_CSS.read_text(encoding="utf-8"))

    collisions = sorted(mine & shared)
    assert not collisions, (
        f"these classes set `display` in both the gallery CSS and the shared "
        f"stylesheet: {collisions}. The shared rule wins or loses depending on "
        f"order, and the layout breaks silently."
    )


def test_hidden_views_are_actually_hidden():
    """`[hidden]` is a user-agent rule with lower specificity than a class, so
    `.tg-list{display:flex}` rendered both views on top of each other.
    """
    html = _theme_page()

    assert ".tg-grid[hidden]" in html
    assert ".tg-list[hidden]" in html
    assert "display:none" in html.split(".tg-list[hidden]", 1)[1][:40]
