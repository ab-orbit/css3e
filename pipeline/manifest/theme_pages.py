"""Theme gallery pages, regenerated on every publish.

One page per registered theme, listing the articles of every `tema` slug that
theme owns. Written to ``articles/<theme-slug>/index.html`` so it sits one
level above the article directories and can link them relatively.

The page is a plain static document. It also carries an authoring console that
reveals itself only under localhost — see partials/theme_console.html.j2.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pipeline.config import ARTICLES_DIR, SHARED_STYLESHEET, Settings, get_settings
from pipeline.manifest.themes_yaml import load_themes
from pipeline.render.jinja_env import get_env
from pipeline.schemas.package import ManifestEntry, Theme

logger = logging.getLogger(__name__)

# A draft has no published page to link. A copy-of-root does — it is excluded
# from the sitemap to avoid duplicate-content penalties, but a reader can still
# open it, so it belongs in the gallery.
VISIBLE_STATUSES = {"published", "copy-of-root"}


def entries_for_theme(theme: Theme, manifest: list[ManifestEntry]) -> list[ManifestEntry]:
    """Articles belonging to `theme`, newest first."""
    owned = [
        e for e in manifest if e.tema in theme.temas and e.status in VISIBLE_STATUSES
    ]
    return sorted(owned, key=lambda e: (e.date_published, e.slug), reverse=True)


PAGE_FILES = {"article": "index.html", "blog": "blog.html", "workshop": "workshop.html"}

# What a card links to when the entry has no article page. Some entries publish
# only a workshop; linking them at index.html regardless yields a 404.
PAGE_PREFERENCE = ("article", "blog", "workshop")


def _article_href(entry: ManifestEntry, page_kind: str | None = None) -> str:
    """Link from articles/<theme>/index.html to one of an entry's pages.

    Derived from the path the manifest records, never rebuilt from tema+slug:
    an entry's pages do not always live in a directory named after its slug.
    `three-categories-of-cas-workshop` publishes into the
    `three-categories-of-cas` folder it shares, and reconstructing its href
    produced a 404 on the gallery.

    The theme directory is a sibling of the tema directories, so stripping the
    leading "articles/" and prefixing "../" reaches them.
    """
    if page_kind is None:
        page_kind = next(
            (kind for kind in PAGE_PREFERENCE if kind in entry.pages), "article"
        )

    recorded = entry.pages.get(page_kind)
    if recorded:
        return "../" + recorded.removeprefix("articles/")

    # No recorded path for this kind: fall back to the conventional location.
    return f"../{entry.tema}/{entry.slug}/{PAGE_FILES[page_kind]}"


def build_theme_page(
    theme: Theme, entries: list[ManifestEntry], *, settings: Settings | None = None
) -> str:
    settings = settings or get_settings()
    base = settings.site_base_url.rstrip("/") + "/"

    template = get_env().get_template("theme.html.j2")
    return template.render(
        theme=theme,
        entries=entries,
        article_href=_article_href,
        stylesheet=SHARED_STYLESHEET,
        canonical_url=f"{base}articles/{theme.slug}/index.html",
        site_base_url=settings.site_base_url,
    )


def regenerate_theme_pages(
    manifest: list[ManifestEntry], *, settings: Settings | None = None
) -> list[Path]:
    """Rewrite every theme gallery from the manifest. Returns the paths written.

    Regenerated whole rather than patched, for the same reason the sitemap is:
    a gallery assembled from partial edits drifts out of sync with the manifest
    that is supposed to be the single source of truth.
    """
    settings = settings or get_settings()
    written: list[Path] = []

    for theme in load_themes():
        entries = entries_for_theme(theme, manifest)
        if not entries:
            logger.info("Theme %r has no published articles; skipping", theme.slug)
            continue

        destination = ARTICLES_DIR / theme.slug / "index.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            build_theme_page(theme, entries, settings=settings), encoding="utf-8"
        )
        written.append(destination)
        logger.info("Wrote %s (%s articles)", destination, len(entries))

    return written
