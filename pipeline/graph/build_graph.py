"""LangGraph StateGraph: ingest -> analyze -> [interrupt] -> infer_theme ->
fan-out (hero/categories/mindmap/tables/essay×2/workshop/seo/downloads) in
parallel with a media branch (audio -> slides) -> assemble -> [interrupt] ->
render -> publish.

The two interrupts are the human-in-the-loop checkpoints: `review_extraction`
(after analyze_paper, before spending tokens on the N-way fan-out — this is
the single highest-leverage QA point since every artifact inherits errors
from PaperAnalysis) and `review_content` (after assemble, before writing
files — optional, skip with skip_content_review=True for unattended runs).
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from pipeline.config import configure_tracing
from pipeline.graph.nodes.analyze import analyze_paper
from pipeline.graph.nodes.assemble import assemble
from pipeline.graph.nodes.audio import generate_audio
from pipeline.graph.nodes.categories import gen_categories
from pipeline.graph.nodes.downloads import gen_downloads
from pipeline.graph.nodes.entities import gen_entities
from pipeline.graph.nodes.essay import gen_essay_condensed, gen_essay_full
from pipeline.graph.nodes.hero import gen_hero
from pipeline.graph.nodes.infer_theme import infer_theme
from pipeline.graph.nodes.ingest import ingest_pdf
from pipeline.graph.nodes.mindmap import gen_mindmap
from pipeline.graph.nodes.publish import update_manifest_and_publish
from pipeline.graph.nodes.render import render_html
from pipeline.graph.nodes.seo import gen_seo
from pipeline.graph.nodes.slides import generate_slides
from pipeline.graph.nodes.tables import gen_tables
from pipeline.graph.nodes.workshop import gen_workshop
from pipeline.graph.state import PipelineState


def _review_extraction(state: PipelineState) -> dict:
    """Pauses the graph, surfacing PaperAnalysis for a human to inspect/edit
    before any of the N downstream generators spend tokens on it.
    """
    decision = interrupt(
        {
            "checkpoint": "review_extraction",
            "paper_analysis": state["paper"].model_dump(),
            "instructions": "Edit and resume with {'paper': <corrected dict>} or {} to accept as-is.",
        }
    )
    if decision and decision.get("paper"):
        from pipeline.schemas.paper import PaperAnalysis

        return {"paper": PaperAnalysis.model_validate(decision["paper"])}
    return {}


def _review_content(state: PipelineState) -> dict:
    decision = interrupt(
        {
            "checkpoint": "review_content",
            "package": state["package"].model_dump(),
            "instructions": "Edit and resume with {'package': <corrected dict>} or {} to accept as-is.",
        }
    )
    if decision and decision.get("package"):
        from pipeline.schemas.package import ArticlePackage

        return {"package": ArticlePackage.model_validate(decision["package"])}
    return {}


def build_graph(*, skip_content_review: bool = False):
    # Bridges the LangSmith settings from .env into os.environ, where
    # LangChain actually reads them. No-op when tracing is off.
    configure_tracing()

    g = StateGraph(PipelineState)

    g.add_node("ingest_pdf", ingest_pdf)
    g.add_node("analyze_paper", analyze_paper)
    g.add_node("review_extraction", _review_extraction)
    g.add_node("infer_theme", infer_theme)

    g.add_node("gen_hero", gen_hero)
    g.add_node("gen_categories", gen_categories)
    g.add_node("gen_mindmap", gen_mindmap)
    g.add_node("gen_tables", gen_tables)
    g.add_node("gen_essay_condensed", gen_essay_condensed)
    g.add_node("gen_essay_full", gen_essay_full)
    g.add_node("gen_workshop", gen_workshop)
    g.add_node("gen_seo", gen_seo)
    g.add_node("gen_downloads", gen_downloads)
    g.add_node("gen_entities", gen_entities)

    g.add_node("generate_audio", generate_audio)
    g.add_node("generate_slides", generate_slides)

    g.add_node("assemble", assemble)
    g.add_node("review_content", _review_content)
    g.add_node("render_html", render_html)
    g.add_node("publish", update_manifest_and_publish)

    g.add_edge(START, "ingest_pdf")
    g.add_edge("ingest_pdf", "analyze_paper")
    g.add_edge("analyze_paper", "review_extraction")
    g.add_edge("review_extraction", "infer_theme")

    # Fan-out: LLM content generators.
    fanout = [
        "gen_hero",
        "gen_categories",
        "gen_mindmap",
        "gen_tables",
        "gen_essay_condensed",
        "gen_essay_full",
        "gen_workshop",
        "gen_seo",
        "gen_downloads",
        "gen_entities",
    ]
    for node in fanout:
        g.add_edge("infer_theme", node)

    # Media branch: runs in parallel with the fan-out, only needs the PDF.
    g.add_edge("infer_theme", "generate_audio")
    g.add_edge("generate_audio", "generate_slides")

    # Fan-in: assemble waits on every fan-out node AND the media branch.
    for node in [*fanout, "generate_slides"]:
        g.add_edge(node, "assemble")

    if skip_content_review:
        g.add_edge("assemble", "render_html")
    else:
        g.add_edge("assemble", "review_content")
        g.add_edge("review_content", "render_html")

    g.add_edge("render_html", "publish")
    g.add_edge("publish", END)

    return g.compile(checkpointer=MemorySaver())
