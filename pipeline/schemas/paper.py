"""Shared 'paper understanding' extraction — every downstream generation node
reads ONLY this object, never the raw PDF text again (bounds token cost and
keeps every generated artifact consistent with a single reading of the paper).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Author(BaseModel):
    name: str
    affiliation: str = ""


class CategoryRaw(BaseModel):
    """One member of the paper's core taxonomy (e.g. SMCAS/UDCAS/VSCAS)."""

    tag: str = Field(description="Short label, e.g. 'Categoria I · interna'")
    name: str = Field(description="e.g. 'SMCAS'")
    subtitle: str = Field(description="e.g. 'Self-Managing Context-Aware System'")
    description: str
    attributes: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Ordered {label, text} pairs, e.g. [('Direção', '...'), ('Mecanismo', '...')]",
    )


class SectionSummary(BaseModel):
    heading: str
    summary: str


class PaperAnalysis(BaseModel):
    """Structured comprehension of the source PDF. Produced once by the
    analyze_paper node; every other node in the graph reads this, not the PDF.
    """

    title: str
    subtitle: str = ""
    authors: list[Author]
    venue: str
    pages: str = ""
    date_published: str = Field(description="Year or ISO date, best available")
    doi: str = ""
    source_pdf_url: str = Field(
        description="Repo-relative or absolute URL to the original PDF"
    )
    abstract: str

    keywords: list[str] = Field(default_factory=list)
    problem_statement: str = Field(
        description="One paragraph: the gap or obstacle the paper addresses"
    )
    key_concepts: list[str] = Field(
        description="Named concepts/terms central to the paper, e.g. 'SDBC', 'AORTA', 'Ciclo MAPE'"
    )

    categories: list[CategoryRaw] = Field(
        default_factory=list,
        description="The paper's core taxonomy/typology, if it proposes one; empty if not applicable",
    )

    section_outline: list[SectionSummary]
    formal_notation_present: bool = Field(
        description="True if the paper includes formal predicates/pseudocode/notation worth reproducing verbatim"
    )
    formal_notation_block: str = Field(
        default="", description="Verbatim or lightly-cleaned notation block, if formal_notation_present"
    )
    case_study_present: bool
    case_summary: str = Field(
        default="", description="Summary of the illustrative case/example, if any"
    )

    closing_question: str = Field(
        description="A provocative, open question the paper's argument leads to — used as the closer callout"
    )
