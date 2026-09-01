"""Regenerates sitemap.xml IN FULL from pipeline/articles.yaml on every
publish, preserving the hand-maintained root-level entries (index.html,
index_extended.html, artigo.html, blog.html, resources/*) that predate the
pipeline — those are re-emitted verbatim from ROOT_ENTRIES below, never
patched by regex/XML surgery.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from pipeline.config import REPO_ROOT, get_settings
from pipeline.schemas.package import ManifestEntry, SitemapEntry

SITEMAP_PATH = REPO_ROOT / "sitemap.xml"

# The hand-built pages that existed before the pipeline. Kept as a fixed list
# rather than re-scanned, so a pipeline run can never silently drop them.
ROOT_ENTRIES: list[SitemapEntry] = [
    SitemapEntry(loc="{base}index_extended.html", lastmod="2026-08-28", priority=1.0),
    SitemapEntry(loc="{base}index.html", lastmod="2026-08-28", priority=0.9),
    SitemapEntry(loc="{base}artigo.html", lastmod="2026-08-28", priority=0.9),
    SitemapEntry(loc="{base}blog.html", lastmod="2026-08-28", priority=0.9),
    SitemapEntry(loc="{base}resources/index.html", lastmod="2026-08-28", priority=0.7),
    SitemapEntry(loc="{base}resources/cases/index.html", lastmod="2026-08-28", priority=0.7),
    *[
        SitemapEntry(loc=f"{{base}}resources/cases/case-{i}.html", lastmod="2026-08-28", priority=0.5)
        for i in range(1, 6)
    ],
]

PAGE_PRIORITY = {"article": 0.8, "blog": 0.75, "workshop": 0.6}


def build_sitemap_entries(
    manifest: list[ManifestEntry], base_url: str
) -> list[SitemapEntry]:
    entries = [
        SitemapEntry(loc=e.loc.format(base=base_url), lastmod=e.lastmod, priority=e.priority)
        for e in ROOT_ENTRIES
    ]
    for m in manifest:
        if not m.include_in_sitemap:
            continue
        for page_kind, relative_url in m.pages.items():
            priority = m.sitemap_priority_override or PAGE_PRIORITY.get(page_kind, 0.5)
            entries.append(
                SitemapEntry(
                    loc=f"{base_url}{relative_url}",
                    lastmod=m.date_published,
                    priority=priority,
                )
            )
    return entries


def render_sitemap_xml(entries: list[SitemapEntry]) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for e in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(e.loc)}</loc>")
        lines.append(f"    <lastmod>{e.lastmod}</lastmod>")
        lines.append(f"    <changefreq>{e.changefreq}</changefreq>")
        lines.append(f"    <priority>{e.priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    return "\n".join(lines)


def regenerate_sitemap(manifest: list[ManifestEntry], path: Path = SITEMAP_PATH) -> None:
    settings = get_settings()
    entries = build_sitemap_entries(manifest, settings.site_base_url)
    path.write_text(render_sitemap_xml(entries), encoding="utf-8")
