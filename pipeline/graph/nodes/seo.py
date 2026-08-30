from __future__ import annotations

from pipeline.config import get_settings
from pipeline.graph.nodes._util import paper_json
from pipeline.graph.state import PipelineState
from pipeline.llm.client import run_structured
from pipeline.schemas.components import SeoMeta

PAGE_KINDS = {
    "article": "index.html",
    "blog": "blog.html",
    "workshop": "workshop.html",
}


def gen_seo(state: PipelineState) -> dict:
    settings = get_settings()
    authors = ", ".join(a.name for a in state["paper"].authors) or settings.default_authors
    seo_pages: dict[str, SeoMeta] = {}
    for page_kind, filename in PAGE_KINDS.items():
        relative_path = f"articles/{state['tema']}/{state['slug']}/{filename}"
        seo_pages[page_kind] = run_structured(
            "seo",
            SeoMeta,
            variables={
                "page_kind": page_kind,
                "relative_path": relative_path,
                "site_base_url": settings.site_base_url,
                "authors": authors,
                "published_date": state["paper"].date_published,
                "paper_analysis_json": paper_json(state),
            },
        )
    return {"seo_pages": seo_pages}
