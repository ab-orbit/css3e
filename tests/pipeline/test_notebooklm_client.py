"""Unit tests for the notebooklm-py wrapper.

The NotebookLM client is replaced with a fake exposing the same async surface
the wrapper calls, so these run offline. What is under test is the wrapper's
own contract: auth materialization, the create/upload/generate/wait/download
call order, error mapping onto NotebookLMError, and atomic PPTX staging.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace

import notebooklm as nb
import pytest

from pipeline.config import Settings
from pipeline.media import notebooklm_client as mod
from pipeline.media.notebooklm_client import (
    NotebookLMError,
    generate_audio_overview,
    generate_slide_deck,
)

STORAGE_STATE = base64.b64encode(json.dumps({"cookies": []}).encode()).decode()


@pytest.fixture(autouse=True)
def no_idle_wait(monkeypatch):
    """Never sleep on the notebook's queue in tests."""
    monkeypatch.setattr(mod, "_IDLE_WAIT_SECONDS", 0.0)
    monkeypatch.setattr(mod, "_IDLE_POLL_SECONDS", 0.0)


@pytest.fixture
def settings() -> Settings:
    return Settings(NOTEBOOKLM_AUTH_JSON=STORAGE_STATE)


@pytest.fixture
def pdf(tmp_path) -> Path:
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    return path


class FakeNotebooks:
    def __init__(self, calls, *, existing=None):
        self._calls = calls
        self._existing = existing or []

    async def list(self):
        self._calls.append(("notebooks.list",))
        return [SimpleNamespace(id=nb_id, title=title) for nb_id, title in self._existing]

    async def create(self, title: str):
        self._calls.append(("notebooks.create", title))
        return SimpleNamespace(id="nb-1")


class FakeSources:
    def __init__(self, calls, *, existing=None):
        self._calls = calls
        self._sources = list(existing or [])

    async def list(self, notebook_id, **kwargs):
        self._calls.append(("sources.list", notebook_id))
        return list(self._sources)

    async def add_file(self, notebook_id, file_path, **kwargs):
        self._calls.append(("sources.add_file", notebook_id, Path(file_path).name, kwargs))
        source = SimpleNamespace(id="src-1", title=kwargs.get("title") or Path(file_path).stem)
        self._sources.append(source)
        return source


class FakeArtifacts:
    def __init__(self, calls, *, error=None, download_raises=None, audio=None, wait_raises=None):
        self._calls = calls
        self._error = error
        self._download_raises = download_raises
        self._audio = list(audio or [])
        self._wait_raises = wait_raises

    async def list_audio(self, notebook_id):
        self._calls.append(("list_audio", notebook_id))
        return list(self._audio)

    async def generate_audio(self, notebook_id, **kwargs):
        self._calls.append(("generate_audio", notebook_id, kwargs))
        return SimpleNamespace(task_id="task-1")

    async def generate_slide_deck(self, notebook_id, **kwargs):
        self._calls.append(("generate_slide_deck", notebook_id, kwargs))
        return SimpleNamespace(task_id="task-2")

    async def wait_for_completion(self, notebook_id, task_id, **kwargs):
        self._calls.append(("wait_for_completion", notebook_id, task_id))
        if self._wait_raises is not None:
            raise self._wait_raises
        return SimpleNamespace(error=self._error, error_code=7 if self._error else None)

    async def download_audio(self, notebook_id, output_path, artifact_id=None, **kwargs):
        self._calls.append(("download_audio", notebook_id, output_path, artifact_id))
        Path(output_path).write_bytes(b"audio")
        return output_path

    async def download_slide_deck(self, notebook_id, output_path, **kwargs):
        self._calls.append(("download_slide_deck", notebook_id, output_path, kwargs))
        if self._download_raises is not None:
            raise self._download_raises
        Path(output_path).write_bytes(b"pptx")
        return output_path


class FakeClient:
    def __init__(self, calls, *, existing=None, sources=None, **artifact_kwargs):
        self.notebooks = FakeNotebooks(calls, existing=existing)
        self.sources = FakeSources(calls, existing=sources)
        self.artifacts = FakeArtifacts(calls, **artifact_kwargs)


def install_fake_client(monkeypatch, calls, *, seen_paths=None, **artifact_kwargs):
    """Patch _open_client so the wrapper talks to FakeClient, recording the
    storage-state path it would have handed to from_storage.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_open(settings):
        if not settings.notebooklm_auth_json:
            raise NotebookLMError("NOTEBOOKLM_AUTH_JSON is not set.")
        if seen_paths is not None:
            seen_paths.append(settings.notebooklm_auth_json)
        yield FakeClient(calls, **artifact_kwargs)

    monkeypatch.setattr(mod, "_open_client", _fake_open)


def test_audio_happy_path(monkeypatch, settings, pdf, tmp_path):
    calls: list = []
    install_fake_client(monkeypatch, calls)
    dest = tmp_path / "out" / "audio.m4a"

    result = generate_audio_overview(
        pdf, notebook_title="tema", source_title="paper", dest_path=dest, settings=settings
    )
    assert result == dest
    assert dest.read_bytes() == b"audio"

    names = [c[0] for c in calls]
    assert names == [
        "notebooks.list",
        "notebooks.create",
        "sources.list",
        "sources.add_file",
        "sources.list",
        "list_audio",
        "generate_audio",
        "wait_for_completion",
        "download_audio",
    ], names


def test_audio_passes_source_ids_and_format(monkeypatch, settings, pdf, tmp_path):
    calls: list = []
    install_fake_client(monkeypatch, calls)

    generate_audio_overview(
        pdf, notebook_title="tema", source_title="paper", dest_path=tmp_path / "a.m4a", settings=settings
    )

    kwargs = next(c[2] for c in calls if c[0] == "generate_audio")
    assert kwargs["source_ids"] == ["src-1"]
    assert kwargs["language"] == "pt-BR"
    assert kwargs["audio_format"] == nb.AudioFormat.DEEP_DIVE


def test_source_upload_waits(monkeypatch, settings, pdf, tmp_path):
    calls: list = []
    install_fake_client(monkeypatch, calls)

    generate_audio_overview(
        pdf, notebook_title="tema", source_title="paper", dest_path=tmp_path / "a.m4a",
        settings=settings,
    )

    kwargs = next(c[3] for c in calls if c[0] == "sources.add_file")
    assert kwargs["wait"] is True
    assert kwargs["mime_type"] == "application/pdf"


def test_unknown_audio_style_raises(settings, pdf, tmp_path):
    with pytest.raises(NotebookLMError, match="Unknown audio style"):
        generate_audio_overview(
            pdf, notebook_title="tema", source_title="p", dest_path=tmp_path / "a.m4a", settings=settings, style="podcast"
        )


def test_failed_generation_raises(monkeypatch, settings, pdf, tmp_path):
    calls: list = []
    install_fake_client(monkeypatch, calls, error="quota exhausted")

    with pytest.raises(NotebookLMError, match="Audio overview generation failed"):
        generate_audio_overview(pdf, notebook_title="tema", source_title="p", dest_path=tmp_path / "a.m4a", settings=settings)


def test_slides_downloads_both_formats(monkeypatch, settings, pdf, tmp_path):
    """One generation, two downloads: PPTX for the download button, PDF for the
    embedded preview. A second generate call would burn quota and risk the
    preview drifting from the download.
    """
    calls: list = []
    install_fake_client(monkeypatch, calls)
    pptx = tmp_path / "slides" / "deck.pptx"
    pdf_out = tmp_path / "slides" / "deck.pdf"

    assert generate_slide_deck(
        pdf, notebook_title="tema", source_title="paper", pptx_dest=pptx, pdf_dest=pdf_out, settings=settings
    ) == (pptx, pdf_out)
    assert pptx.read_bytes() == b"pptx"
    assert pdf_out.read_bytes() == b"pptx"

    assert [c[0] for c in calls].count("generate_slide_deck") == 1
    formats = [c[3]["output_format"] for c in calls if c[0] == "download_slide_deck"]
    assert formats == ["pptx", "pdf"]


def test_slides_staging_file_shares_filesystem(monkeypatch, settings, pdf, tmp_path):
    """The .partial staging file must sit beside each destination — Path.replace
    cannot move across devices, and the system temp dir is a separate volume.
    """
    calls: list = []
    install_fake_client(monkeypatch, calls)
    pptx = tmp_path / "slides" / "deck.pptx"
    pdf_out = tmp_path / "other" / "deck.pdf"

    generate_slide_deck(pdf, notebook_title="tema", source_title="p", pptx_dest=pptx, pdf_dest=pdf_out, settings=settings)

    staged = [Path(c[2]).parent for c in calls if c[0] == "download_slide_deck"]
    assert staged == [pptx.parent, pdf_out.parent]


def test_slides_failed_download_leaves_no_partial(monkeypatch, settings, pdf, tmp_path):
    calls: list = []
    install_fake_client(
        monkeypatch, calls, download_raises=nb.ArtifactDownloadError("connection reset")
    )
    pptx = tmp_path / "slides" / "deck.pptx"
    pdf_out = tmp_path / "slides" / "deck.pdf"

    with pytest.raises(NotebookLMError, match="notebooklm-py call failed"):
        generate_slide_deck(
            pdf, notebook_title="tema", source_title="p", pptx_dest=pptx, pdf_dest=pdf_out, settings=settings
        )

    assert not pptx.exists()
    assert not pdf_out.exists()
    assert list(pptx.parent.glob("*.partial")) == []


def test_missing_auth_raises(pdf, tmp_path):
    settings = Settings(NOTEBOOKLM_AUTH_JSON="")
    with pytest.raises(NotebookLMError, match="NOTEBOOKLM_AUTH_JSON is not set"):
        generate_audio_overview(pdf, notebook_title="tema", source_title="p", dest_path=tmp_path / "a.m4a", settings=settings)


def test_invalid_base64_auth_raises(pdf, tmp_path):
    settings = Settings(NOTEBOOKLM_AUTH_JSON="not base64!!!")
    with pytest.raises(NotebookLMError, match="not valid base64"):
        generate_audio_overview(pdf, notebook_title="tema", source_title="p", dest_path=tmp_path / "a.m4a", settings=settings)


def test_auth_tempfile_is_removed(monkeypatch, settings, pdf, tmp_path):
    """_open_client writes storage_state to a private temp file and must clean
    it up — a stale Google session cookie left in /tmp is a real leak.
    """
    written: list[Path] = []
    real_mkstemp = mod.tempfile.mkstemp

    def _spy_mkstemp(*args, **kwargs):
        fd, name = real_mkstemp(*args, **kwargs)
        written.append(Path(name))
        return fd, name

    monkeypatch.setattr(mod.tempfile, "mkstemp", _spy_mkstemp)

    class _Boom:
        def from_storage(self, **kwargs):
            raise AssertionError("should not connect")

    fake_nb = SimpleNamespace(
        NotebookLMClient=SimpleNamespace(
            from_storage=lambda **kw: (_ for _ in ()).throw(nb.AuthError("expired"))
        ),
        AuthError=nb.AuthError,
        NotebookLMError=nb.NotebookLMError,
        AudioFormat=nb.AudioFormat,
    )
    monkeypatch.setattr(mod, "_import_notebooklm", lambda: fake_nb)

    with pytest.raises(NotebookLMError):
        generate_audio_overview(pdf, notebook_title="tema", source_title="p", dest_path=tmp_path / "a.m4a", settings=settings)

    assert written, "expected a temp storage-state file to be created"
    assert all(not p.exists() for p in written)


def test_reuses_the_theme_notebook_and_selects_every_source(
    monkeypatch, settings, pdf, tmp_path
):
    """One notebook per theme: an artifact cites every paper already in it."""
    calls: list = []
    install_fake_client(
        monkeypatch,
        calls,
        existing=[("nb-tema", "tema")],
        sources=[
            SimpleNamespace(id="src-outro", title="outro-paper"),
            SimpleNamespace(id="src-paper", title="paper"),
        ],
    )

    generate_audio_overview(
        pdf, notebook_title="tema", source_title="paper", dest_path=tmp_path / "a.m4a",
        settings=settings,
    )

    names = [c[0] for c in calls]
    assert "notebooks.create" not in names
    # Already listed under this title: no second upload of the same paper.
    assert "sources.add_file" not in names
    kwargs = next(c[2] for c in calls if c[0] == "generate_audio")
    assert kwargs["source_ids"] == ["src-outro", "src-paper"]


def test_uploads_into_the_existing_theme_notebook(monkeypatch, settings, pdf, tmp_path):
    """A new paper joins the theme's notebook rather than getting its own."""
    calls: list = []
    install_fake_client(
        monkeypatch,
        calls,
        existing=[("nb-tema", "tema")],
        sources=[SimpleNamespace(id="src-outro", title="outro-paper")],
    )

    generate_audio_overview(
        pdf, notebook_title="tema", source_title="paper", dest_path=tmp_path / "a.m4a",
        settings=settings,
    )

    upload = next(c for c in calls if c[0] == "sources.add_file")
    assert upload[1] == "nb-tema"
    assert upload[3]["title"] == "paper"
    assert "notebooks.create" not in [c[0] for c in calls]
    kwargs = next(c[2] for c in calls if c[0] == "generate_audio")
    assert kwargs["source_ids"] == ["src-outro", "src-1"]


def test_slides_share_the_theme_notebook(monkeypatch, settings, pdf, tmp_path):
    """Slides used to get their own '<title> (slides)' notebook."""
    calls: list = []
    install_fake_client(
        monkeypatch,
        calls,
        existing=[("nb-tema", "tema")],
        sources=[SimpleNamespace(id="src-paper", title="paper")],
    )

    generate_slide_deck(
        pdf,
        notebook_title="tema",
        source_title="paper",
        pptx_dest=tmp_path / "deck.pptx",
        pdf_dest=tmp_path / "deck.pdf",
        settings=settings,
    )

    assert "notebooks.create" not in [c[0] for c in calls]
    assert next(c[1] for c in calls if c[0] == "generate_slide_deck") == "nb-tema"


def test_notebook_listing_failure_falls_back_to_creating(monkeypatch, settings, pdf, tmp_path):
    """Listing is an optimisation; a failure must not abort the generation."""
    calls: list = []
    install_fake_client(monkeypatch, calls)

    async def _boom(self):
        raise RuntimeError("listing unavailable")

    monkeypatch.setattr(FakeNotebooks, "list", _boom)

    generate_audio_overview(
        pdf, notebook_title="tema", source_title="paper", dest_path=tmp_path / "a.m4a",
        settings=settings,
    )

    assert "notebooks.create" in [c[0] for c in calls]


def test_both_artifacts_are_pinned_to_brazilian_portuguese(
    monkeypatch, settings, pdf, tmp_path
):
    """Sources are in English; narration and slides must not follow them."""
    calls: list = []
    install_fake_client(monkeypatch, calls)

    generate_audio_overview(
        pdf, notebook_title="tema", source_title="paper", dest_path=tmp_path / "a.m4a",
        settings=settings,
    )
    generate_slide_deck(
        pdf,
        notebook_title="tema",
        source_title="paper",
        pptx_dest=tmp_path / "deck.pptx",
        pdf_dest=tmp_path / "deck.pdf",
        settings=settings,
    )

    for call in ("generate_audio", "generate_slide_deck"):
        kwargs = next(c[2] for c in calls if c[0] == call)
        assert kwargs["language"] == "pt-BR"
        assert "português do Brasil (pt-BR)" in kwargs["instructions"]


def _audio_artifact(artifact_id, status, minutes_ago=0):
    from datetime import datetime, timedelta, timezone

    return SimpleNamespace(
        id=artifact_id,
        status=status,
        created_at=datetime.now(timezone.utc) + timedelta(minutes=minutes_ago),
    )


def test_a_timed_out_generation_downloads_the_artifact_that_landed(
    monkeypatch, settings, pdf, tmp_path
):
    """The backend often finishes after the client stops waiting."""
    calls: list = []
    install_fake_client(
        monkeypatch,
        calls,
        sources=[SimpleNamespace(id="src-1", title="paper")],
        audio=[_audio_artifact("art-ready", 3, minutes_ago=1)],
        wait_raises=mod.NotebookLMError("Task x timed out after 2400.0s"),
    )

    dest = tmp_path / "a.m4a"
    generate_audio_overview(
        pdf, notebook_title="tema", source_title="paper", dest_path=dest, settings=settings
    )

    download = next(c for c in calls if c[0] == "download_audio")
    assert download[3] == "art-ready"


def test_a_timeout_with_nothing_ready_still_fails(monkeypatch, settings, pdf, tmp_path):
    calls: list = []
    install_fake_client(
        monkeypatch,
        calls,
        sources=[SimpleNamespace(id="src-1", title="paper")],
        audio=[_audio_artifact("art-running", 2, minutes_ago=1)],
        wait_raises=mod.NotebookLMError("Task x timed out after 2400.0s"),
    )

    with pytest.raises(NotebookLMError, match="timed out"):
        generate_audio_overview(
            pdf, notebook_title="tema", source_title="paper",
            dest_path=tmp_path / "a.m4a", settings=settings,
        )


def test_a_failure_that_is_not_a_timeout_is_not_recovered(monkeypatch, settings, pdf, tmp_path):
    """Only a client-side timeout justifies picking up a stray artifact."""
    calls: list = []
    install_fake_client(
        monkeypatch,
        calls,
        sources=[SimpleNamespace(id="src-1", title="paper")],
        audio=[_audio_artifact("art-ready", 3, minutes_ago=1)],
        wait_raises=mod.NotebookLMError("Audio overview generation failed: quota"),
    )

    with pytest.raises(NotebookLMError, match="quota"):
        generate_audio_overview(
            pdf, notebook_title="tema", source_title="paper",
            dest_path=tmp_path / "a.m4a", settings=settings,
        )


def test_an_artifact_older_than_this_run_is_not_reused(monkeypatch, settings, pdf, tmp_path):
    """Downloading a previous article's audio would be worse than failing."""
    calls: list = []
    install_fake_client(
        monkeypatch,
        calls,
        sources=[SimpleNamespace(id="src-1", title="paper")],
        audio=[_audio_artifact("art-old", 3, minutes_ago=-30)],
        wait_raises=mod.NotebookLMError("Task x timed out after 2400.0s"),
    )

    with pytest.raises(NotebookLMError, match="timed out"):
        generate_audio_overview(
            pdf, notebook_title="tema", source_title="paper",
            dest_path=tmp_path / "a.m4a", settings=settings,
        )
