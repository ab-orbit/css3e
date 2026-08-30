"""LangGraph state. Fan-out nodes each write one field; the assemble node
reads them all back into an ArticlePackage. Optional fields default to None
so nodes can run in any order / be skipped (e.g. audio/slides without
credentials) without breaking the graph.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TypedDict

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


class PipelineState(TypedDict, total=False):
    pdf_path: Path
    slug: str
    tema: Optional[str]  # if None, infer_theme fills it in
    copy_only: bool
    is_copy_of_existing: bool
    copy_canonical_root: Optional[str]  # e.g. "https://ab-orbit.github.io/css3e/artigo.html"

    paper_text: str
    paper: PaperAnalysis

    hero: HeroMeta
    categories: list[CategoryCard]
    mindmap: MindMapSpec
    tables: list[TableSpec]
    essay_condensed: EssayVariant
    essay_full: EssayVariant
    workshop: WorkshopSpec
    seo_pages: dict[str, SeoMeta]
    downloads: list[DownloadItem]
    entity_graph: EntityGraph

    audio_path: Optional[str]
    audio_title: Optional[str]
    audio_subtitle: Optional[str]
    slides_pptx_path: Optional[str]
    slides_pdf_path: Optional[str]  # what the page embeds; PPTX is the download
    # Optional Google Slides override, set manually via `pipeline set-slides`.
    slides_preview_url: Optional[str]
    slides_edit_url: Optional[str]

    package: object  # ArticlePackage; typed as object to avoid a circular import
    rendered_pages: dict[str, str]
    output_dir: Path
