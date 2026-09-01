from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date

from pipeline.config import ARTICLES_DIR, get_settings, published_pdf_name
from pipeline.naming import unique_casrai_filename
from pipeline.render.jsonld import build_jsonld
from pathlib import Path

from pipeline.graph.state import PipelineState
from pipeline.manifest.articles_yaml import upsert
from pipeline.manifest.llms_txt import regenerate_llms_txt
from pipeline.manifest.robots import verify_sitemap_reference
from pipeline.manifest.sitemap import regenerate_sitemap
from pipeline.manifest.theme_pages import regenerate_theme_pages
from pipeline.manifest.themes_yaml import register_tema
from pipeline.schemas.package import ManifestEntry


def _already_archived(output_dir: Path, source_pdf: Path) -> bool:
    """Whether an identical CASRAI-named copy of `source_pdf` is already here.

    Compares content hashes rather than filenames: the name encodes a date and
    a version, so it changes between runs even when the bytes do not.
    """
    digest = _digest(source_pdf)
    return any(_digest(existing) == digest for existing in output_dir.glob("css3e_*.pdf"))


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def update_manifest_and_publish(state: PipelineState) -> dict:
    """Writes the rendered pages under articles/<tema>/<slug>/, upserts the
    manifest, and regenerates sitemap.xml/llms.txt from it. NEVER touches
    root-level files (artigo.html, blog.html, index*.html, sitemap.xml's
    root entries) — those are re-emitted from the fixed ROOT_ENTRIES list.
    """
    settings = get_settings()
    tema = state["tema"]
    slug = state["slug"]
    output_dir = ARTICLES_DIR / tema / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in state["rendered_pages"].items():
        (output_dir / filename).write_text(content, encoding="utf-8")

    # Copy the source PDF in beside the pages so every download link on the
    # published site resolves. Without this the pages link at the operator's
    # local filesystem path, which 404s for everyone else.
    source_pdf = Path(state["pdf_path"])
    published_pdf = output_dir / published_pdf_name(slug)
    if source_pdf.resolve() != published_pdf.resolve():
        shutil.copyfile(source_pdf, published_pdf)

    pkg = state["package"]
    # ArticlePackage is the whole LLM output for this article. Persisting it
    # means a template change can be re-rendered without paying for the fan-out
    # again — which is the point of the schema, and was documented on
    # ArticlePackage but never actually written to disk.
    # A CASRAI-conformant copy alongside it, for anyone archiving the paper as
    # research data. The web copy keeps the slug name because that is what the
    # published pages link to and a link must not change when a v02 arrives.
    # Skip when this exact PDF is already archived here. The version element
    # means "a new revision of the paper", not "publish ran twice" — and it does
    # run twice per graph execution, which otherwise produced an identical v01
    # and v02 of the same 1.5MB file.
    if not _already_archived(output_dir, source_pdf):
        archival_name = unique_casrai_filename(
            output_dir, pkg.paper.title or slug, when=date.today()
        )
        shutil.copyfile(source_pdf, output_dir / archival_name)

    (output_dir / "package.json").write_text(
        pkg.model_dump_json(indent=2, exclude_none=False), encoding="utf-8"
    )

    # The JSON-LD is also inlined in index.html; this standalone copy is what a
    # crawler or an LLM agent can fetch without parsing the page.
    (output_dir / f"{slug}.jsonld").write_text(
        json.dumps(
            build_jsonld(
                pkg,
                pkg.entity_graph,
                site_base_url=settings.site_base_url,
                page_path=f"articles/{tema}/{slug}/index.html",
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pages = {
        page_kind: f"articles/{tema}/{slug}/{filename}"
        for page_kind, filename in {
            "article": "index.html",
            "blog": "blog.html",
            "workshop": "workshop.html",
        }.items()
    }

    is_copy = state.get("is_copy_of_existing", False)
    entry = ManifestEntry(
        slug=slug,
        tema=tema,
        title=pkg.paper.title,
        pdf_source=f"articles/{tema}/{slug}/{published_pdf_name(slug)}",
        doi=pkg.paper.doi,
        authors=[a.name for a in pkg.paper.authors],
        date_published=pkg.paper.date_published,
        pages=pages,
        briefing=pkg.hero.lede,
        has_audio=bool(pkg.audio_path),
        has_slides=bool(pkg.slides_pdf_path or pkg.slides_preview_url),
        slides_pptx_path=pkg.slides_pptx_path,
        slides_pdf_path=pkg.slides_pdf_path,
        slides_preview_url=pkg.slides_preview_url,
        slides_edit_url=pkg.slides_edit_url,
        status="copy-of-root" if is_copy else "published",
        # A copy of a pre-existing root page is excluded from sitemap/llms.txt
        # (avoids duplicate-content SEO) and its canonical points back at the
        # original root URL.
        include_in_sitemap=not is_copy,
        include_in_llms_txt=not is_copy,
        canonical_override=state.get("copy_canonical_root"),
    )

    manifest = upsert(entry)
    # Make sure this article's tema belongs to a theme before regenerating the
    # galleries: an unregistered tema would otherwise leave the article with no
    # gallery linking to it.
    register_tema(tema)
    regenerate_theme_pages(manifest, settings=settings)
    regenerate_sitemap(manifest)
    regenerate_llms_txt(manifest, settings.site_base_url)
    verify_sitemap_reference(settings.site_base_url)

    return {"output_dir": output_dir}
