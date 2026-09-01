from __future__ import annotations

from pipeline.graph.state import PipelineState
from pipeline.schemas.entities import EntityGraph
from pipeline.schemas.package import ArticlePackage


def assemble(state: PipelineState) -> dict:
    """Fan-in: collects every independent node's output into one
    ArticlePackage, serializable to package.json for re-render without
    re-running the LLM.
    """
    pkg = ArticlePackage(
        slug=state["slug"],
        tema=state["tema"],
        paper=state["paper"],
        hero=state["hero"],
        categories=state["categories"],
        mindmap=state["mindmap"],
        tables=state["tables"],
        essay_condensed=state["essay_condensed"],
        essay_full=state["essay_full"],
        workshop=state["workshop"],
        seo_pages=list(state["seo_pages"].values()),
        downloads=state["downloads"],
        entity_graph=state.get("entity_graph") or EntityGraph(),
        audio_path=state.get("audio_path"),
        audio_title=state.get("audio_title"),
        audio_subtitle=state.get("audio_subtitle"),
        slides_pptx_path=state.get("slides_pptx_path"),
        slides_pdf_path=state.get("slides_pdf_path"),
        slides_preview_url=state.get("slides_preview_url"),
        slides_edit_url=state.get("slides_edit_url"),
        is_copy_of_existing=state.get("is_copy_of_existing", False),
        copy_canonical_override=state.get("copy_canonical_root"),
    )
    return {"package": pkg}
