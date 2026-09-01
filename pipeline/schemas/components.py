"""One schema per reusable HTML component identified in artigo.html/blog.html.
Field shapes mirror exactly what each component's Jinja2 partial needs to
render — see pipeline/render/templates/partials/.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HeroMeta(BaseModel):
    eyebrow: str = Field(description="e.g. 'BMSD 2018 · Springer LNBIP 319 · pp. 185–202'")
    h1: str
    lede: str
    toc_anchors: list[tuple[str, str]] = Field(
        description="Ordered [(anchor_id, label), ...] for the in-page nav rail"
    )
    authors_line: str
    affiliations: str
    kv_rows: list[tuple[str, str]] = Field(
        description="[(label, value), ...] e.g. [('Publicado em', '...'), ('DOI', '...')]"
    )
    problem_statement: str


class CategoryCard(BaseModel):
    tag: str
    accent_index: int = Field(
        ge=0, description="Maps to CSS var --accent-N; NOT a named class, so N categories scale"
    )
    name: str
    subtitle: str
    dl_items: list[tuple[str, str]] = Field(description="[(dt, dd), ...]")


class PaletteEntry(BaseModel):
    kind: str = Field(description="Key referenced by MindMapNode.k")
    fill: str = Field(description="Hex color")
    text: str = Field(default="#fff")
    label: str = Field(description="Legend label, e.g. 'três categorias'")


class MindMapNode(BaseModel):
    t: str = Field(description="Node title/text")
    k: str | None = Field(default=None, description="Palette kind key; inherited from parent if unset")
    children: list["MindMapNode"] = Field(default_factory=list)


MindMapNode.model_rebuild()


class MindMapSpec(BaseModel):
    root: MindMapNode
    palette: list[PaletteEntry] = Field(
        description="Legend is generated FROM this list, never hand-written separately"
    )


class TableSpec(BaseModel):
    caption: str
    columns: list[str]
    rows: list[list[str]]


class PullQuote(BaseModel):
    text: str
    cite: str


class EssaySection(BaseModel):
    no: str = Field(description="Section number label, e.g. '01' or '1'")
    heading: str
    paragraphs: list[str]
    bullets: list[str] = Field(default_factory=list)
    pullquote: PullQuote | None = None
    terms: list[str] = Field(
        default_factory=list, description="Phrases to wrap in .term styling"
    )


class EssayVariant(BaseModel):
    variant: Literal["condensed", "full"]
    sections: list[EssaySection]
    drop_cap_paragraph: str = Field(description="Opening paragraph, styled with a drop cap")
    closing_paragraph: str


class ParticipantStep(BaseModel):
    phase: str
    instruction: str
    self_check_prompt: str


class ParticipantTrack(BaseModel):
    steps: list[ParticipantStep]
    materials_needed: list[str]
    reflection_questions: list[str]


class FacilitatorScriptStep(BaseModel):
    time_marker: str = Field(description="e.g. '0–5 min'")
    activity: str
    facilitator_notes: str
    discussion_prompts: list[str] = Field(default_factory=list)


class FacilitatorTrack(BaseModel):
    script: list[FacilitatorScriptStep]
    timing_table: TableSpec
    debrief_structure: list[str]
    consolidation_goal: str


class WorkshopSpec(BaseModel):
    title: str
    framing: str = Field(description="Pedagogical framing named explicitly, e.g. 'Ciclo de Kolb adaptado'")
    duration_minutes: int
    participant_track: ParticipantTrack
    facilitator_track: FacilitatorTrack


class SeoMeta(BaseModel):
    page_kind: Literal["article", "blog", "workshop", "landing"]
    title: str
    description: str
    keywords: list[str]
    og_type: Literal["article", "website"]
    jsonld_type: Literal["Article", "BlogPosting", "LearningResource", "WebSite"]
    authors: list[str]
    canonical_url: str
    published_date: str
    modified_date: str
    about: list[str]
    article_tags: list[str] = Field(default_factory=list)


class DownloadItem(BaseModel):
    title: str
    description: str
    href: str
    arrow_label: str
