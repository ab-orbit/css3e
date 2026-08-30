from __future__ import annotations

from pipeline.config import SHARED_OG_IMAGE, get_settings, published_pdf_name
from pipeline.graph.state import PipelineState
from pipeline.manifest.themes_yaml import register_tema
from pipeline.render.build import RenderContext, render_article_package


def render_html(state: PipelineState) -> dict:
    settings = get_settings()
    pkg = state["package"]
    # Registering here (not only at publish) means the back-link points at a
    # gallery that will exist: publish regenerates every registered theme.
    theme = register_tema(state["tema"])

    ctx = RenderContext(
        asset_prefix="../../../",
        # Relative to the page itself: publish copies the PDF into this same
        # folder. Prefixing "../../../" to state["pdf_path"] produced a broken
        # href, since that path is absolute and outside the repo.
        pdf_relative_href=published_pdf_name(state["slug"]),
        og_image_url=f"{settings.site_base_url}{SHARED_OG_IMAGE}",
        site_base_url=settings.site_base_url,
        publisher_name=settings.default_publisher_name,
        theme_href=f"../../{theme.slug}/index.html",
        theme_name=theme.name,
        brand_label=pkg.paper.title[:40],
    )

    seo_by_kind = {seo.page_kind: seo for seo in pkg.seo_pages}
    pages = render_article_package(pkg, seo_by_kind, ctx, settings)
    return {"rendered_pages": pages}
