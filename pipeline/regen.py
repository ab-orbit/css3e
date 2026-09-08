"""Regenerating one media artifact of an already-published article.

A full run costs ~25 minutes and re-does extraction plus eleven generators to
change one thing. Everything needed to skip that is already on disk:
`articles/<tema>/<slug>/package.json` holds the whole ArticlePackage, and the
published PDF sits beside it. So a regeneration reloads the package, replaces
one field, and re-renders — no LLM fan-out, no second extraction.

Only the NotebookLM artifacts (audio, slide deck) are regenerable here: they
are the ones whose output is steered by a free-text prompt, which is what the
console lets an author edit.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import ARTICLES_DIR, get_settings, published_pdf_name
from pipeline.llm.prompt_store import load_prompt, save_prompt
from pipeline.media.notebooklm_client import (
    AUDIO_PROMPT,
    SLIDES_PROMPT,
    generate_audio_overview,
    generate_slide_deck,
)
from pipeline.schemas.package import ArticlePackage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Artifact:
    """One regenerable artifact: what to call, and what it writes back."""

    id: str
    label: str
    prompt_name: str
    generate: Callable[[Path, str, str, object], dict]
    # Package fields this artifact owns, used to report what exists today.
    fields: tuple[str, ...]


def _regen_audio(pdf: Path, slug: str, instructions: str, article_dir) -> dict:
    generate_audio_overview(
        pdf,
        title=slug,
        dest_path=article_dir / "audio" / f"{slug}.m4a",
        settings=get_settings(),
        instructions=instructions,
    )
    return {
        "audio_path": f"audio/{slug}.m4a",
        "audio_title": f"Comentário em áudio: {slug}",
        "audio_subtitle": "Faixa 01 · gerada via NotebookLM Audio Overview",
    }


def _regen_slides(pdf: Path, slug: str, instructions: str, article_dir) -> dict:
    generate_slide_deck(
        pdf,
        title=slug,
        pptx_dest=article_dir / "slides" / "deck.pptx",
        pdf_dest=article_dir / "slides" / "deck.pdf",
        settings=get_settings(),
        instructions=instructions,
    )
    return {"slides_pptx_path": "slides/deck.pptx", "slides_pdf_path": "slides/deck.pdf"}


ARTIFACTS: dict[str, Artifact] = {
    "audio": Artifact(
        id="audio",
        label="Áudio (NotebookLM Audio Overview)",
        prompt_name=AUDIO_PROMPT,
        generate=_regen_audio,
        fields=("audio_path", "audio_title", "audio_subtitle"),
    ),
    "slides": Artifact(
        id="slides",
        label="Slides (NotebookLM Slide Deck)",
        prompt_name=SLIDES_PROMPT,
        generate=_regen_slides,
        fields=("slides_pptx_path", "slides_pdf_path"),
    ),
}


class RegenError(RuntimeError):
    pass


def article_dir(tema: str, slug: str) -> Path:
    return ARTICLES_DIR / tema / slug


def load_package(tema: str, slug: str) -> ArticlePackage:
    path = article_dir(tema, slug) / "package.json"
    if not path.exists():
        raise RegenError(f"Sem package.json em {path.parent}")
    return ArticlePackage.model_validate_json(path.read_text(encoding="utf-8"))


def source_pdf(tema: str, slug: str) -> Path:
    """The published PDF, which is the source every artifact was built from."""
    path = article_dir(tema, slug) / published_pdf_name(slug)
    if not path.exists():
        raise RegenError(f"PDF publicado não encontrado: {path}")
    return path


def list_artifacts(tema: str, slug: str) -> list[dict]:
    """Regenerable artifacts for one article, each with its current prompt."""
    pkg = load_package(tema, slug)
    return [
        {
            "id": artifact.id,
            "label": artifact.label,
            "prompt": load_prompt(artifact.prompt_name),
            "prompt_name": artifact.prompt_name,
            "current": {field: getattr(pkg, field, None) for field in artifact.fields},
        }
        for artifact in ARTIFACTS.values()
    ]


def regenerate(
    tema: str,
    slug: str,
    artifact_id: str,
    *,
    prompt: str | None = None,
    save_as_default: bool = False,
) -> Path:
    """Regenerate one artifact and re-publish the article's pages.

    `prompt` overrides the stored instructions for this run only, unless
    `save_as_default` also writes it back to the prompt file — which shows up
    as a reviewable diff rather than hidden state.
    """
    artifact = ARTIFACTS.get(artifact_id)
    if artifact is None:
        raise RegenError(
            f"Artefato desconhecido: {artifact_id!r}. Conhecidos: {sorted(ARTIFACTS)}"
        )

    pkg = load_package(tema, slug)
    pdf = source_pdf(tema, slug)

    instructions = (prompt or "").strip() or load_prompt(artifact.prompt_name)
    if save_as_default and prompt and prompt.strip():
        save_prompt(artifact.prompt_name, prompt.strip())
        logger.info("Prompt %s salvo como padrão", artifact.prompt_name)

    logger.info("Regerando %s de %s/%s", artifact.id, tema, slug)
    updates = artifact.generate(pdf, slug, instructions, article_dir(tema, slug))
    pkg = pkg.model_copy(update=updates)

    return _render_and_publish(pkg, pdf)


def _render_and_publish(pkg: ArticlePackage, pdf: Path) -> Path:
    """Re-run only the tail of the graph, reusing its nodes verbatim.

    Calling the node functions directly (rather than duplicating them) is what
    keeps a regenerated article byte-identical to a fully-run one: the same
    render context, the same manifest upsert, the same sitemap/llms.txt/theme
    gallery regeneration.
    """
    from pipeline.graph.nodes.publish import update_manifest_and_publish
    from pipeline.graph.nodes.render import render_html

    state = {
        "package": pkg,
        "tema": pkg.tema,
        "slug": pkg.slug,
        "pdf_path": pdf,
        "is_copy_of_existing": False,
        "copy_canonical_root": None,
    }
    state.update(render_html(state))
    result = update_manifest_and_publish(state)
    return result["output_dir"]
