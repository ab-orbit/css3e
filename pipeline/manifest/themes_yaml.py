"""pipeline/themes.yaml — the curated theme registry.

`infer_theme` produces a fresh slug on every run, so one subject drifts across
near-identical directory names. Rather than rename published directories (which
would break every existing link), this registry maps many `tema` slugs onto one
display theme, and the gallery is generated per theme.

The file is meant to be edited by hand: when a run introduces an unrecognized
tema, a provisional theme is created and logged, and a human folds it into the
right one afterwards.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from pipeline.config import REPO_ROOT
from pipeline.schemas.package import Theme

logger = logging.getLogger(__name__)

THEMES_PATH = REPO_ROOT / "pipeline" / "themes.yaml"


def load_themes(path: Path = THEMES_PATH) -> list[Theme]:
    if not Path(path).exists():
        return []
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    return [Theme.model_validate(row) for row in raw]


def save_themes(themes: list[Theme], path: Path = THEMES_PATH) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        yaml.safe_dump(
            [t.model_dump() for t in themes],
            allow_unicode=True,
            sort_keys=False,
            width=100,
        ),
        encoding="utf-8",
    )


def theme_for_tema(tema: str, *, path: Path = THEMES_PATH) -> Theme | None:
    """The theme owning `tema`, or None when it is not registered anywhere."""
    return next((t for t in load_themes(path) if tema in t.temas), None)


def register_tema(
    tema: str, *, theme_slug: str | None = None, path: Path = THEMES_PATH
) -> Theme:
    """Ensure `tema` belongs to a theme, and return that theme.

    With `theme_slug`, adds it to that theme, erroring if the slug is unknown —
    inventing a theme from a typo would scatter articles across near-duplicate
    galleries, which is what this registry exists to prevent.

    Without it, an unregistered tema becomes its own provisional theme with a
    title-cased name, and a warning asks for a human to fold it in. Dropping it
    instead would orphan the article from every gallery.
    """
    themes = load_themes(path)

    existing = next((t for t in themes if tema in t.temas), None)
    if existing is not None:
        return existing

    if theme_slug is not None:
        target = next((t for t in themes if t.slug == theme_slug), None)
        if target is None:
            raise ValueError(
                f"no theme with slug {theme_slug!r} in {path}; "
                f"known slugs: {[t.slug for t in themes]}"
            )
        target.temas.append(tema)
        save_themes(themes, path)
        return target

    provisional = Theme(
        slug=tema,
        name=tema.replace("-", " ").title(),
        description="",
        temas=[tema],
    )
    themes.append(provisional)
    save_themes(themes, path)
    logger.warning(
        "tema %r matched no theme; created a provisional one. Fold it into the "
        "right theme in %s and re-run publish.",
        tema,
        path,
    )
    return provisional
