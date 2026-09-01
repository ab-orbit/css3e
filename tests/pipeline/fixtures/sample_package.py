"""Builds a minimal but structurally complete ArticlePackage for tests,
without any LLM/network calls.
"""

from __future__ import annotations

from pipeline.schemas.components import (
    CategoryCard,
    DownloadItem,
    EssaySection,
    EssayVariant,
    FacilitatorScriptStep,
    FacilitatorTrack,
    HeroMeta,
    MindMapNode,
    MindMapSpec,
    PaletteEntry,
    ParticipantStep,
    ParticipantTrack,
    PullQuote,
    SeoMeta,
    TableSpec,
    WorkshopSpec,
)
from pipeline.schemas.package import ArticlePackage
from pipeline.schemas.paper import Author, CategoryRaw, PaperAnalysis, SectionSummary


def make_sample_package(slug: str = "sample-paper", tema: str = "teste") -> ArticlePackage:
    paper = PaperAnalysis(
        title="Sample Paper Title",
        authors=[Author(name="Jane Doe", affiliation="Test University")],
        venue="Test Symposium 2026",
        pages="1-10",
        date_published="2026",
        doi="10.0000/test",
        source_pdf_url="tests/pipeline/fixtures/sample.pdf",
        abstract="A sample abstract for testing.",
        keywords=["testing", "fixtures"],
        problem_statement="How do we test a rendering pipeline without live data?",
        key_concepts=["Concept A", "Concept B"],
        categories=[
            CategoryRaw(
                tag="Category I",
                name="CAT-A",
                subtitle="First category",
                description="Description A",
                attributes=[("Direção", "internal"), ("Exemplo", "example A")],
            ),
            CategoryRaw(
                tag="Category II",
                name="CAT-B",
                subtitle="Second category",
                description="Description B",
                attributes=[("Direção", "external")],
            ),
        ],
        section_outline=[SectionSummary(heading="Intro", summary="Introductory summary")],
        formal_notation_present=False,
        case_study_present=False,
        closing_question="Who decides when categories conflict?",
    )

    hero = HeroMeta(
        eyebrow="Test Symposium 2026 · pp. 1-10",
        h1="Sample Paper Title",
        lede="A short lede describing the sample paper.",
        toc_anchors=[("categorias", "Categorias"), ("mapa", "Mapa mental")],
        authors_line="Jane Doe",
        affiliations="Test University",
        kv_rows=[("Publicado em", "Test Symposium 2026"), ("DOI", "10.0000/test")],
        problem_statement="How do we test a rendering pipeline without live data?",
    )

    categories = [
        CategoryCard(
            tag="Category I",
            accent_index=0,
            name="CAT-A",
            subtitle="First category",
            dl_items=[("DIREÇÃO", "internal"), ("EXEMPLO", "example A")],
        ),
        CategoryCard(
            tag="Category II",
            accent_index=1,
            name="CAT-B",
            subtitle="Second category",
            dl_items=[("DIREÇÃO", "external")],
        ),
    ]

    mindmap = MindMapSpec(
        root=MindMapNode(
            t="Sample Paper Title",
            k="root",
            children=[
                MindMapNode(t="Categories", k="cat", children=[MindMapNode(t="CAT-A"), MindMapNode(t="CAT-B")]),
            ],
        ),
        palette=[
            PaletteEntry(kind="root", fill="#3d3a58", text="#fff", label="raiz"),
            PaletteEntry(kind="cat", fill="#2E7D5B", text="#fff", label="categorias"),
        ],
    )

    tables = [TableSpec(caption="Test table", columns=["Concept", "Meaning"], rows=[["A", "Means A"], ["B", "Means B"]])]

    def essay_variant(variant: str) -> EssayVariant:
        return EssayVariant(
            variant=variant,
            sections=[
                EssaySection(
                    no="1",
                    heading="First section",
                    paragraphs=["First paragraph about Concept A."],
                    bullets=["Bullet one", "Bullet two"],
                    pullquote=PullQuote(text="A pull quote.", cite="Section 1"),
                    terms=["Concept A"],
                )
            ],
            drop_cap_paragraph="An opening paragraph for the essay.",
            closing_paragraph="A closing paragraph before the final question.",
        )

    workshop = WorkshopSpec(
        title="Sample Workshop",
        framing="Ciclo de Kolb adaptado",
        duration_minutes=60,
        participant_track=ParticipantTrack(
            steps=[ParticipantStep(phase="Abertura", instruction="Reflita sobre X.", self_check_prompt="Você entendeu X?")],
            materials_needed=["Caderno", "Acesso ao artigo"],
            reflection_questions=["O que mudou na sua visão sobre X?"],
        ),
        facilitator_track=FacilitatorTrack(
            script=[
                FacilitatorScriptStep(
                    time_marker="0-5 min",
                    activity="Abertura",
                    facilitator_notes="Apresente o tema.",
                    discussion_prompts=["O que vocês já sabem sobre X?"],
                )
            ],
            timing_table=TableSpec(caption="Timing", columns=["Tempo", "Atividade"], rows=[["0-5 min", "Abertura"]]),
            debrief_structure=["Recapitular", "Perguntas abertas"],
            consolidation_goal="Participantes conseguem aplicar CAT-A e CAT-B a um cenário novo.",
        ),
    )

    seo_pages = [
        SeoMeta(
            page_kind="article",
            title="Sample Paper Title",
            description="A sample description.",
            keywords=["testing"],
            og_type="article",
            jsonld_type="Article",
            authors=["Jane Doe"],
            canonical_url="https://example.test/articles/teste/sample-paper/index.html",
            published_date="2026",
            modified_date="2026",
            about=["Concept A", "Concept B"],
            article_tags=["CAT-A", "CAT-B"],
        ),
        SeoMeta(
            page_kind="blog",
            title="Sample Paper Title — blog",
            description="A sample blog description.",
            keywords=["testing"],
            og_type="article",
            jsonld_type="BlogPosting",
            authors=["Jane Doe"],
            canonical_url="https://example.test/articles/teste/sample-paper/blog.html",
            published_date="2026",
            modified_date="2026",
            about=["Concept A"],
        ),
        SeoMeta(
            page_kind="workshop",
            title="Sample Workshop",
            description="A sample workshop description.",
            keywords=["testing"],
            og_type="article",
            jsonld_type="LearningResource",
            authors=["Jane Doe"],
            canonical_url="https://example.test/articles/teste/sample-paper/workshop.html",
            published_date="2026",
            modified_date="2026",
            about=["Concept A"],
        ),
    ]

    downloads = [DownloadItem(title="Artigo original", description="PDF", href="../../../tests/pipeline/fixtures/sample.pdf", arrow_label="PDF ↓")]

    return ArticlePackage(
        slug=slug,
        tema=tema,
        paper=paper,
        hero=hero,
        categories=categories,
        mindmap=mindmap,
        tables=tables,
        essay_condensed=essay_variant("condensed"),
        essay_full=essay_variant("full"),
        workshop=workshop,
        seo_pages=seo_pages,
        downloads=downloads,
    )
