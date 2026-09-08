"""Wrapper around notebooklm-py (verified against the installed 0.8.1 API).

Generates the podcast-style Audio Overview used by the floating player, and
the Slide Deck, downloaded in both formats NotebookLM exports: PPTX (the
editable download) and PDF (what the page actually embeds, since browsers
cannot render a .pptx inline). Both come from ONE generation — the deck is
generated once and downloaded twice — so there is no second job, no extra
quota, and no risk of the preview drifting from the download.

Notebooks are scoped to a THEME, not to an article or an artifact: every paper
of a theme is a source in the same notebook, and each generation selects all of
them, so an artifact can place its paper among its neighbours.

The upstream client is fully async and is used as an async context manager;
the LangGraph nodes that call into here are sync, so each public function
opens its own client inside a single `asyncio.run`.

Auth: notebooklm-py reads a Google session from a Playwright storage-state
file (`~/.notebooklm/profiles/<profile>/storage_state.json`), bootstrapped
once with `notebooklm login --browser chrome`. For unattended runs that file
is base64-encoded into NOTEBOOKLM_AUTH_JSON and materialized here into a
private temp file — never over the developer's real profile. Sessions expire
every few weeks and need periodic re-login; this is NOT set-and-forget.

The underlying NotebookLM API is undocumented/reverse-engineered, so treat
every call as best-effort: the graph nodes catch NotebookLMError and continue
without audio/slides rather than failing the build. Rate limiting is handled
by the client itself (`rate_limit_max_retries`), so there is no hand-rolled
backoff here.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import os
import tempfile
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TypeVar

from pipeline.config import Settings
from pipeline.llm.prompt_store import load_prompt

logger = logging.getLogger(__name__)

T = TypeVar("T")

# The NotebookLM backend queues generation jobs; a deep-dive audio overview on
# a full paper regularly runs past the library's 300s default.
_ARTIFACT_TIMEOUT_SECONDS = 900.0
# Sources must finish server-side processing before an artifact can cite them.
_SOURCE_TIMEOUT_SECONDS = 300.0

# The site is written in Brazilian Portuguese, and the papers it ingests are in
# English. NotebookLM defaults to English and, given a bare "pt", has produced
# European Portuguese narration; the region tag plus an explicit instruction is
# what reliably pins both artifacts to pt-BR.
#
# The instructions themselves live in pipeline/llm/prompts/ so the authoring
# console can show them, edit them for one regeneration, and optionally save
# the edit back as the new default.
_LANGUAGE = "pt-BR"
AUDIO_PROMPT = "audio_instructions"
SLIDES_PROMPT = "slides_instructions"


class NotebookLMError(RuntimeError):
    pass


def _import_notebooklm():
    try:
        import notebooklm  # type: ignore[import-not-found]
    except ImportError as exc:
        raise NotebookLMError(
            "notebooklm-py is not installed. `uv pip install -e .` and run "
            "`notebooklm login --browser chrome` once to bootstrap auth."
        ) from exc
    return notebooklm


@asynccontextmanager
async def _open_client(settings: Settings):
    """Yield an authenticated NotebookLMClient.

    NOTEBOOKLM_AUTH_JSON (base64 of a storage_state.json) is decoded into a
    0600 temp file passed as `from_storage(path=...)`, so an unattended run
    never reads or overwrites the developer's real profile. The temp file is
    removed in the finally block.
    """
    nb = _import_notebooklm()

    if not settings.notebooklm_auth_json:
        raise NotebookLMError(
            "NOTEBOOKLM_AUTH_JSON is not set. Run `notebooklm login --browser chrome`, "
            "then `base64 -i ~/.notebooklm/profiles/default/storage_state.json | "
            "tr -d '\\n'` and put the result in .env."
        )

    try:
        storage_state = base64.b64decode(settings.notebooklm_auth_json, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise NotebookLMError(
            "NOTEBOOKLM_AUTH_JSON is not valid base64. Re-encode storage_state.json "
            "with `base64 -i ... | tr -d '\\n'` (the trailing newline must be stripped)."
        ) from exc

    fd, tmp_name = tempfile.mkstemp(prefix="notebooklm-auth-", suffix=".json")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(storage_state)
        os.chmod(tmp_path, 0o600)

        try:
            async with nb.NotebookLMClient.from_storage(path=str(tmp_path)) as client:
                yield client
        except nb.AuthError as exc:
            raise NotebookLMError(
                f"NotebookLM auth rejected ({exc}). The session has most likely "
                "expired — re-run `notebooklm login --browser chrome` and refresh "
                "NOTEBOOKLM_AUTH_JSON."
            ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


def _run(coro_fn: Callable[[], Awaitable[T]]) -> T:
    """Run one async workflow from sync graph-node code, mapping the library's
    own exceptions onto NotebookLMError so callers only catch one type.
    """
    nb = _import_notebooklm()
    try:
        return asyncio.run(coro_fn())
    except NotebookLMError:
        raise
    except nb.NotebookLMError as exc:  # the library's own base exception
        raise NotebookLMError(f"notebooklm-py call failed: {exc}") from exc


async def _prepare_notebook(
    client: Any, title: str, pdf_path: Path, source_title: str
) -> tuple[str, list[str]]:
    """Return (notebook_id, source_ids) for the notebook named `title`.

    One notebook per THEME, holding every paper of that theme, and every
    artifact is generated from all of its sources. That is what makes an audio
    overview or a deck able to relate one paper to its neighbours instead of
    reading it in isolation — and it keeps the account from accumulating a
    notebook per article, or the pair per artifact this used to create.

    The PDF is uploaded under `source_title` (the article slug, not the upload's
    temporary filename) and only when the notebook does not already hold a
    source by that name, so a re-run adopts what earlier runs left behind
    rather than duplicating the paper.
    """
    notebook_id = await _find_notebook_id(client, title)
    if notebook_id is None:
        notebook = await client.notebooks.create(title=title)
        notebook_id = notebook.id
        logger.info("Created NotebookLM notebook %r (%s)", title, notebook_id)

    existing = await _sources(client, notebook_id)
    if not any(source.title == source_title for source in existing):
        await client.sources.add_file(
            notebook_id,
            pdf_path,
            mime_type="application/pdf",
            wait=True,
            wait_timeout=_SOURCE_TIMEOUT_SECONDS,
            title=source_title,
        )
        existing = await _sources(client, notebook_id)

    source_ids = [source.id for source in existing]
    if not source_ids:
        raise NotebookLMError(
            f"Notebook {title!r} has no usable source after upload; refusing to "
            "generate an artifact that would cite nothing."
        )
    logger.info(
        "Notebook %r (%s): %d fonte(s) selecionada(s)", title, notebook_id, len(source_ids)
    )
    return notebook_id, source_ids


async def _sources(client: Any, notebook_id: str) -> list[Any]:
    """The notebook's sources, or an empty list when it has none yet."""
    try:
        return list(await client.sources.list(notebook_id))
    except Exception as exc:  # noqa: BLE001 - an empty notebook may 404 here
        logger.warning("Could not list sources of %s (%s)", notebook_id, exc)
        return []


async def _find_notebook_id(client: Any, title: str) -> str | None:
    """The id of the most recent notebook titled exactly `title`, if any.

    Listing is best-effort: a failure here must not stop a generation that
    would otherwise succeed with a fresh notebook.
    """
    try:
        notebooks = await client.notebooks.list()
    except Exception as exc:  # noqa: BLE001 - listing is an optimisation
        logger.warning("Could not list NotebookLM notebooks (%s); creating a new one", exc)
        return None
    matches = [nb.id for nb in notebooks if nb.title == title]
    return matches[0] if matches else None


def notebook_url(notebook_id: str) -> str:
    """Public NotebookLM URL for a notebook id."""
    return f"https://notebooklm.google.com/notebook/{notebook_id}"


async def _await_artifact(client: Any, notebook_id: str, status: Any, what: str) -> None:
    """Block until a generation task finishes, raising on a failed terminal state."""
    final = await client.artifacts.wait_for_completion(
        notebook_id, status.task_id, timeout=_ARTIFACT_TIMEOUT_SECONDS
    )
    if final.error:
        raise NotebookLMError(
            f"{what} generation failed: {final.error} (code={final.error_code})"
        )


def generate_audio_overview(
    pdf_path: Path,
    *,
    notebook_title: str,
    source_title: str,
    dest_path: Path,
    settings: Settings,
    style: str = "DEEP_DIVE",
    language: str = _LANGUAGE,
    instructions: str | None = None,
) -> Path:
    """Generate a podcast-style audio overview and download it to `dest_path`.

    `notebook_title` names the theme notebook the source joins (see
    _prepare_notebook); `source_title` is how this paper is listed inside it.

    `style` names an AudioFormat member: BRIEF, DEEP_DIVE, CRITIQUE, DEBATE.
    """
    nb = _import_notebooklm()
    instructions = instructions or load_prompt(AUDIO_PROMPT)
    try:
        audio_format = getattr(nb.AudioFormat, style.upper())
    except AttributeError as exc:
        valid = [m for m in dir(nb.AudioFormat) if m.isupper()]
        raise NotebookLMError(
            f"Unknown audio style {style!r}. Valid AudioFormat members: {valid}"
        ) from exc

    async def _work() -> Path:
        async with _open_client(settings) as client:
            notebook_id, source_ids = await _prepare_notebook(
                client, notebook_title, pdf_path, source_title
            )
            logger.info("Audio from notebook %s", notebook_url(notebook_id))
            status = await client.artifacts.generate_audio(
                notebook_id,
                source_ids=source_ids,
                language=language,
                instructions=instructions,
                audio_format=audio_format,
            )
            await _await_artifact(client, notebook_id, status, "Audio overview")

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            await client.artifacts.download_audio(notebook_id, str(dest_path))
            return dest_path

    return _run(_work)


def generate_slide_deck(
    pdf_path: Path,
    *,
    notebook_title: str,
    source_title: str,
    pptx_dest: Path,
    pdf_dest: Path,
    settings: Settings,
    language: str = _LANGUAGE,
    instructions: str | None = None,
) -> tuple[Path, Path]:
    """Generate a slide deck once and download it twice — PPTX and PDF.

    `notebook_title` names the theme notebook the source joins; `source_title`
    is how this paper is listed inside it.

    Both formats come from the same generated artifact: PPTX is the editable
    file offered for download, PDF is what deck_embed.html.j2 puts in an
    iframe. A browser cannot render a .pptx inline, so the PDF is what makes a
    self-hosted preview possible at all — which is the whole point of not
    routing the deck through Google Drive.
    """
    nb = _import_notebooklm()
    instructions = instructions or load_prompt(SLIDES_PROMPT)

    async def _work() -> tuple[Path, Path]:
        async with _open_client(settings) as client:
            notebook_id, source_ids = await _prepare_notebook(
                client, notebook_title, pdf_path, source_title
            )
            logger.info("Slide deck from notebook %s", notebook_url(notebook_id))
            status = await client.artifacts.generate_slide_deck(
                notebook_id,
                source_ids=source_ids,
                language=language,
                instructions=instructions,
                slide_format=nb.SlideDeckFormat.PRESENTER_SLIDES,
            )
            await _await_artifact(client, notebook_id, status, "Slide deck")

            for dest, fmt in ((pptx_dest, "pptx"), (pdf_dest, "pdf")):
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Download beside the destination, then rename into place, so a
                # failed/partial download never leaves a truncated file that a
                # later run would treat as done. The staging file must share a
                # filesystem with the destination — Path.replace cannot cross
                # devices, and the system temp dir is a separate volume on macOS.
                staged = dest.with_name(dest.name + ".partial")
                try:
                    await client.artifacts.download_slide_deck(
                        notebook_id, str(staged), output_format=fmt
                    )
                    staged.replace(dest)
                finally:
                    staged.unlink(missing_ok=True)

            return pptx_dest, pdf_dest

    return _run(_work)
