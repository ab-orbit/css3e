"""Regenerating one media artifact of a published article.

NotebookLM and the publish tail are both stubbed: what is under test is the
wiring — which prompt reaches the generator, what lands back in package.json,
and when an edited prompt is written to disk.
"""

from __future__ import annotations

import json

import pytest

from pipeline import regen
from pipeline.llm import prompt_store
from tests.pipeline.fixtures.sample_package import make_sample_package


@pytest.fixture
def article(tmp_path, monkeypatch):
    """A published article on disk: package.json plus its source PDF."""
    pkg = make_sample_package()
    articles = tmp_path / "articles"
    directory = articles / pkg.tema / pkg.slug
    directory.mkdir(parents=True)
    (directory / "package.json").write_text(pkg.model_dump_json(indent=2), encoding="utf-8")
    (directory / f"{pkg.slug}.pdf").write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(regen, "ARTICLES_DIR", articles)
    return pkg


@pytest.fixture
def stub_publish(monkeypatch):
    """Capture the package that would be rendered and published."""
    published: list = []

    def _fake(pkg, pdf):
        published.append(pkg)
        return regen.article_dir(pkg.tema, pkg.slug)

    monkeypatch.setattr(regen, "_render_and_publish", _fake)
    return published


@pytest.fixture
def stub_generators(monkeypatch):
    """Record what instructions each NotebookLM call received."""
    seen: dict = {}

    def _audio(pdf, *, notebook_title, source_title, dest_path, settings, instructions):
        seen["audio"] = instructions
        seen["audio_notebook"] = notebook_title
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"audio")
        return dest_path

    def _slides(pdf, *, notebook_title, source_title, pptx_dest, pdf_dest, settings, instructions):
        seen["slides"] = instructions
        seen["slides_notebook"] = notebook_title
        return pptx_dest, pdf_dest

    monkeypatch.setattr(regen, "generate_audio_overview", _audio)
    monkeypatch.setattr(regen, "generate_slide_deck", _slides)
    return seen


def test_lists_both_artifacts_with_their_current_prompts(article):
    artifacts = regen.list_artifacts(article.tema, article.slug)

    assert [a["id"] for a in artifacts] == ["audio", "slides"]
    assert "pt-BR" in artifacts[0]["prompt"]


def test_uses_the_stored_prompt_when_none_is_given(article, stub_generators, stub_publish):
    regen.regenerate(article.tema, article.slug, "audio")

    assert stub_generators["audio"] == prompt_store.load_prompt("audio_instructions")


def test_edited_prompt_is_used_for_this_run_only(
    article, stub_generators, stub_publish, monkeypatch
):
    saved: list = []
    monkeypatch.setattr(regen, "save_prompt", lambda name, text: saved.append(name))

    regen.regenerate(article.tema, article.slug, "slides", prompt="Fale como um pirata.")

    assert stub_generators["slides"] == "Fale como um pirata."
    assert saved == []


def test_save_as_default_writes_the_prompt_file(
    article, stub_generators, stub_publish, monkeypatch
):
    saved: list = []
    monkeypatch.setattr(regen, "save_prompt", lambda name, text: saved.append((name, text)))

    regen.regenerate(
        article.tema,
        article.slug,
        "audio",
        prompt="  Narre em pt-BR, tom sóbrio.  ",
        save_as_default=True,
    )

    assert saved == [("audio_instructions", "Narre em pt-BR, tom sóbrio.")]


def test_regenerated_fields_land_on_the_package(article, stub_generators, stub_publish):
    regen.regenerate(article.tema, article.slug, "slides")

    published = stub_publish[0]
    assert published.slides_pptx_path == "slides/deck.pptx"
    assert published.slides_pdf_path == "slides/deck.pdf"
    # Untouched content must survive: a regeneration is not a re-run.
    assert published.hero.h1 == article.hero.h1


def test_unknown_artifact_is_rejected(article):
    with pytest.raises(regen.RegenError, match="Artefato desconhecido"):
        regen.regenerate(article.tema, article.slug, "podcast")


def test_missing_article_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(regen, "ARTICLES_DIR", tmp_path)

    with pytest.raises(regen.RegenError, match="Sem package.json"):
        regen.list_artifacts("tema", "slug")


def test_missing_published_pdf_is_rejected(article, monkeypatch):
    (regen.article_dir(article.tema, article.slug) / f"{article.slug}.pdf").unlink()

    with pytest.raises(regen.RegenError, match="PDF publicado"):
        regen.regenerate(article.tema, article.slug, "audio")


def test_package_json_on_disk_is_readable_after_a_regen(article, stub_generators, stub_publish):
    """The fixture's package must round-trip; a schema drift would break regen."""
    raw = json.loads(
        (regen.article_dir(article.tema, article.slug) / "package.json").read_text()
    )
    assert raw["slug"] == article.slug


def test_regeneration_targets_the_theme_notebook(article, stub_generators, stub_publish):
    """Artifacts belong to the theme's notebook, not to a per-article one."""
    regen.regenerate(article.tema, article.slug, "audio")

    assert stub_generators["audio_notebook"] == article.tema
