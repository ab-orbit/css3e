"""Renders an ArticlePackage into the three page strings (index/blog/workshop)
using the Jinja2 templates under pipeline/render/templates/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pipeline.config import Settings
from pipeline.render.graph_layout import layout_graph
from pipeline.render.jinja_env import get_env
from pipeline.render.jsonld import build_jsonld, render_jsonld_script
from pipeline.schemas.package import ArticlePackage

# Accent palette for category cards (--accent-N). Extend if a paper proposes
# more than 6 categories; hue-rotate rather than hand-picking past this.
DEFAULT_ACCENT_COLORS = ["#2E7D5B", "#8A5A00", "#E8172D", "#2B5F86", "#6B3FA0", "#B4233D"]


@dataclass
class RenderContext:
    asset_prefix: str  # "" for root files, "../../../" for articles/<tema>/<slug>/*.html
    pdf_relative_href: str
    og_image_url: str
    site_base_url: str
    publisher_name: str
    brand_label: str
    # Back-link to the theme gallery. An article page links only its own
    # content plus this one way back out. Defaulted so the render tests and any
    # standalone render still work without a theme registry.
    theme_href: str = ""
    theme_name: str = ""


def _mindmap_json(pkg: ArticlePackage) -> tuple[str, str]:
    data = pkg.mindmap.root.model_dump(exclude_none=True)
    palette = {p.kind: {"fill": p.fill, "text": p.text} for p in pkg.mindmap.palette}
    return json.dumps(data, ensure_ascii=False), json.dumps(palette, ensure_ascii=False)


def render_article_package(
    pkg: ArticlePackage,
    seo_by_kind: dict[str, "SeoMeta"],  # noqa: F821 - forward ref, avoids circular import at module load
    ctx: RenderContext,
    settings: Settings,
) -> dict[str, str]:
    env = get_env()
    mindmap_data_json, mindmap_palette_json = _mindmap_json(pkg)

    authors = [a.name for a in pkg.paper.authors]
    accent_colors = DEFAULT_ACCENT_COLORS[: max(len(pkg.categories), 1)] or DEFAULT_ACCENT_COLORS

    base_vars = {
        "pkg": pkg,
        "asset_prefix": ctx.asset_prefix,
        "pdf_relative_href": ctx.pdf_relative_href,
        "og_image_url": ctx.og_image_url,
        "site_base_url": ctx.site_base_url,
        "publisher_name": ctx.publisher_name,
        "brand_label": ctx.brand_label,
        "authors": authors,
        "published_date": pkg.paper.date_published,
        "modified_date": pkg.paper.date_published,
        "about": pkg.paper.key_concepts,
        "paper": pkg.paper,
        "accent_colors": accent_colors,
        "mindmap": pkg.mindmap,
        "mindmap_data_json": mindmap_data_json,
        "mindmap_palette_json": mindmap_palette_json,
        "categories": pkg.categories,
        "downloads": pkg.downloads,
        "hero": pkg.hero,
        "theme_href": ctx.theme_href,
        "theme_name": ctx.theme_name,
        # Coordinates are computed here, not in the browser: the page ships
        # static SVG and loads no graph library.
        "entity_graph": layout_graph(pkg.entity_graph),
        "entity_engine": pkg.entity_graph.engine,
    }

    out: dict[str, str] = {}

    # Only the article page carries the JSON-LD: duplicating the same @id
    # across three URLs would make the graph ambiguous about which page is the
    # canonical ScholarlyArticle.
    article_page_path = f"articles/{pkg.tema}/{pkg.slug}/index.html"
    jsonld_script = render_jsonld_script(
        build_jsonld(
            pkg,
            pkg.entity_graph,
            site_base_url=ctx.site_base_url,
            page_path=article_page_path,
        )
    )

    article_tpl = env.get_template("article.html.j2")
    out["index.html"] = article_tpl.render(
        **base_vars,
        seo=seo_by_kind["article"],
        essay=pkg.essay_condensed,
        jsonld_script=jsonld_script,
    )

    blog_tpl = env.get_template("blog.html.j2")
    out["blog.html"] = blog_tpl.render(
        **base_vars,
        seo=seo_by_kind["blog"],
    )

    workshop_tpl = env.get_template("workshop.html.j2")
    out["workshop.html"] = workshop_tpl.render(
        **base_vars,
        seo=seo_by_kind["workshop"],
        workshop=pkg.workshop,
    )

    return out
