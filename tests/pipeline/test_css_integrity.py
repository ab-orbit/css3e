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
