"""Fan-in aggregate (ArticlePackage) and the manifest row / sitemap row shapes
that pipeline/manifest/* uses to regenerate sitemap.xml and llms.txt.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from pipeline.schemas.components import (
    CategoryCard,
    DownloadItem,
    EssayVariant,
    HeroMeta,
    MindMapSpec,
    SeoMeta,
    TableSpec,
    WorkshopSpec,
)
from pipeline.schemas.entities import EntityGraph
from pipeline.schemas.paper import PaperAnalysis


class ArticlePackage(BaseModel):
    """Everything needed to render index.html / blog.html / workshop.html for
    one article. Serialized to articles/<tema>/<slug>/package.json so the
    HTML can be re-rendered from a template change without re-running the LLM.
    """

    slug: str
    tema: str
    paper: PaperAnalysis
    hero: HeroMeta
    categories: list[CategoryCard]
    mindmap: MindMapSpec
    tables: list[TableSpec]
    essay_condensed: EssayVariant
    essay_full: EssayVariant
    workshop: WorkshopSpec
    seo_pages: list[SeoMeta] = Field(description="One per page_kind rendered for this article")
    downloads: list[DownloadItem]
    # Entities/relations extracted from the source text. Empty when
    # extraction is disabled or unavailable — it is fail-soft.
    entity_graph: EntityGraph = Field(default_factory=EntityGraph)

    # Media, filled in by the audio/slides branch; may be absent if that
    # branch hasn't completed or credentials aren't configured.
    audio_path: str | None = None
    audio_title: str | None = None
    audio_subtitle: str | None = None
    slides_pptx_path: str | None = None
    # Self-hosted PDF export of the same deck — what deck_embed.html.j2
    # embeds, since a browser cannot render a .pptx inline.
    slides_pdf_path: str | None = None
    # Optional Google Slides override; when set, the page prefers this
    # iframe over the self-hosted PDF.
    slides_preview_url: str | None = None
    slides_edit_url: str | None = None

    # True when this package is a COPY of a pre-existing, hand-built article
    # (the root artigo.html/blog.html case) rather than a from-scratch run —
    # controls the "canonical points back to the root originals" SEO rule.
    is_copy_of_existing: bool = False
    copy_canonical_override: str | None = None


class Theme(BaseModel):
    """A display theme grouping one or more inferred `tema` slugs.

    The pipeline's infer_theme node invents a slug per run, so the same subject
    drifts: three runs of one paper produced `sistemas-sensiveis-ao-contexto`,
    `sistemas-multi-agentes-contexto` and `sistemas-multiagente-contexto`. This
    registry is the human-curated layer that keeps those together in one
    gallery without renaming any published directory.
    """

    slug: str = Field(description="URL segment: articles/<slug>/index.html")
    name: str = Field(description="Display name, e.g. 'CSS - Context Sensitive Systems'")
    description: str = ""
    temas: list[str] = Field(
        default_factory=list, description="Inferred tema slugs belonging to this theme"
    )


class SitemapEntry(BaseModel):
    loc: str
    lastmod: str
    changefreq: str = "monthly"
    priority: float = 0.5


class ManifestEntry(BaseModel):
    """One row in pipeline/articles.yaml — the single source of truth that
    sitemap.xml and llms.txt are regenerated from on every publish.
    """

    slug: str
    tema: str
    title: str
    title_pt: str = ""
    pdf_source: str
    doi: str = ""
    authors: list[str]
    date_published: str
    pages: dict[str, str] = Field(
        description="page_kind -> relative URL, e.g. {'article': 'articles/.../index.html'}"
    )
    # One-paragraph blurb for the theme gallery card. Taken from hero.lede at
    # publish time — already a reader-facing paragraph in Portuguese, so the
    # gallery costs no extra LLM call.
    briefing: str = ""
    has_audio: bool = False
    has_slides: bool = False
    slides_pptx_path: str | None = None
    slides_pdf_path: str | None = None
    slides_preview_url: str | None = None
    slides_edit_url: str | None = None
    status: Literal["draft", "published", "copy-of-root"] = "draft"
    include_in_sitemap: bool = True
    include_in_llms_txt: bool = True
    sitemap_priority_override: float | None = None
    canonical_override: str | None = Field(
        default=None,
        description="Set for copies of pre-existing root pages, pointing canonical back at the original",
    )
