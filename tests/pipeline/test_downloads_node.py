"""Downloads grid stays inside the article's own folder.

The user's constraint is that an article page links only its own content. The
prompt used to instruct the model to add a fixed site-wide "Simuladores" link,
and it did — so this validates every href against the files actually offered.
"""

from __future__ import annotations

import logging

import pytest

from pipeline.graph.nodes import downloads as mod
from pipeline.schemas.components import DownloadItem


def _stub(monkeypatch, items):
    monkeypatch.setattr(
        mod, "run_structured", lambda *a, **k: mod._Downloads(items=items)
    )


def _item(href, title="Item"):
    return DownloadItem(title=title, description="d", href=href, arrow_label="→")


@pytest.fixture
def state():
    return {
        "slug": "meu-artigo",
        "paper": None,
        "audio_path": "audio/meu-artigo.m4a",
        "slides_pdf_path": "slides/deck.pdf",
    }


@pytest.fixture(autouse=True)
def _no_paper_json(monkeypatch):
    monkeypatch.setattr(mod, "paper_json", lambda state: "{}")


def test_keeps_the_articles_own_files(monkeypatch, state):
    _stub(monkeypatch, [
        _item("meu-artigo.pdf"), _item("blog.html"),
        _item("audio/meu-artigo.m4a"), _item("slides/deck.pdf"),
    ])
    assert len(mod.gen_downloads(state)["downloads"]) == 4


def test_drops_a_site_wide_link(monkeypatch, state, caplog):
    _stub(monkeypatch, [
        _item("meu-artigo.pdf"),
        _item("../../resources/cases/index.html", title="Simuladores"),
    ])
    with caplog.at_level(logging.WARNING):
        kept = mod.gen_downloads(state)["downloads"]

    assert [i.href for i in kept] == ["meu-artigo.pdf"]
    assert "Simuladores" in caplog.text


def test_drops_an_invented_external_url(monkeypatch, state):
    _stub(monkeypatch, [_item("https://example.com/paper.pdf"), _item("blog.html")])
    assert [i.href for i in mod.gen_downloads(state)["downloads"]] == ["blog.html"]


def test_media_hrefs_are_not_offered_when_absent(monkeypatch):
    """Without audio or slides, a link to them would 404."""
    _stub(monkeypatch, [_item("blog.html"), _item("audio/x.m4a"), _item("slides/deck.pdf")])
    kept = mod.gen_downloads({"slug": "x", "audio_path": None, "slides_pdf_path": None})
    assert [i.href for i in kept["downloads"]] == ["blog.html"]
