"""Local authoring server.

Serves the theme galleries and drives pipeline runs from the browser. Binds to
127.0.0.1 by design: it holds the OpenRouter key, a NotebookLM session and a
filesystem write path, none of which belong on a listening public port.

The gallery page it serves is byte-identical to the one published to GitHub
Pages. The console inside it reveals itself only under localhost, so the same
file is both the authoring tool and the deliverable.
"""

from __future__ import annotations

import json
import logging
import queue
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from pipeline.config import ARTICLES_DIR, REPO_ROOT
from pipeline.manifest.themes_yaml import load_themes
from pipeline.naming import slugify_description
from pipeline.server.runner import RunRegistry

logger = logging.getLogger(__name__)

registry = RunRegistry()

app = FastAPI(title="css3e — console de autoria", docs_url=None, redoc_url=None)


@app.get("/")
def home() -> RedirectResponse:
    """Land on the first registered theme's gallery."""
    themes = load_themes()
    if not themes:
        raise HTTPException(
            status_code=404,
            detail="Nenhum tema registrado. Edite pipeline/themes.yaml.",
        )
    return RedirectResponse(f"/articles/{themes[0].slug}/index.html")


@app.post("/api/runs")
async def create_run(
    pdf: UploadFile,
    slug: str = Form(default=""),
    tema: str = Form(default=""),
) -> dict:
    """Accept a PDF and start a pipeline run."""
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .pdf")

    # Kept outside the repo until publish decides where it belongs.
    staging = Path(tempfile.mkdtemp(prefix="css3e-upload-"))
    destination = staging / Path(pdf.filename).name
    with destination.open("wb") as handle:
        shutil.copyfileobj(pdf.file, handle)

    resolved_slug = slug.strip() or slugify_description(Path(pdf.filename).stem)
    run = registry.create(destination, slug=resolved_slug, tema=tema.strip() or None)
    registry.start(run)

    logger.info("Run %s started for %s", run.run_id, destination.name)
    return {"run_id": run.run_id, "slug": resolved_slug}


@app.get("/api/articles/{tema}/{slug}/artifacts")
def article_artifacts(tema: str, slug: str) -> dict:
    """The regenerable artifacts of one published article, with their prompts."""
    from pipeline.regen import RegenError, list_artifacts

    try:
        return {"tema": tema, "slug": slug, "artifacts": list_artifacts(tema, slug)}
    except RegenError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/articles/{tema}/{slug}/regen")
def regen_artifact(
    tema: str,
    slug: str,
    artifact: str = Form(...),
    prompt: str = Form(default=""),
    save_as_default: bool = Form(default=False),
) -> dict:
    """Start a regeneration of one artifact of an already-published article."""
    from pipeline.regen import ARTIFACTS, RegenError, load_package

    if artifact not in ARTIFACTS:
        raise HTTPException(status_code=400, detail=f"Artefato desconhecido: {artifact}")
    try:
        load_package(tema, slug)
    except RegenError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    run = registry.create_regen(tema=tema, slug=slug, artifact=artifact)
    registry.start_regen(run, prompt=prompt or None, save_as_default=save_as_default)

    logger.info("Regen %s started for %s/%s (%s)", run.run_id, tema, slug, artifact)
    return {"run_id": run.run_id, "artifact": artifact}


@app.get("/api/runs/{run_id}/events")
def run_events(run_id: str) -> StreamingResponse:
    """Server-sent events for one run."""
    run = registry.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run desconhecido")

    def stream():
        while True:
            try:
                event = run.events.get(timeout=1.0)
            except queue.Empty:
                if run.finished:
                    break
                # Comment frame: keeps proxies and browsers from timing out a
                # connection during the twenty-minute media branch.
                yield ": keep-alive\n\n"
                continue

            yield f"event: {event.name}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
            if event.name in ("done", "failed"):
                break

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/runs/{run_id}")
def run_status(run_id: str) -> dict:
    run = registry.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run desconhecido")
    return {"run_id": run.run_id, "finished": run.finished, **run.progress.snapshot()}


def mount_static(application: FastAPI) -> None:
    """Serve the generated site straight from the repo.

    Mounted last so the API routes above win on any path collision.
    """
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    application.mount(
        "/articles", StaticFiles(directory=ARTICLES_DIR, html=True), name="articles"
    )
    resources = REPO_ROOT / "resources"
    if resources.exists():
        application.mount(
            "/resources", StaticFiles(directory=resources), name="resources"
        )


mount_static(app)


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    icon = REPO_ROOT / "favicon.ico"
    if not icon.exists():
        raise HTTPException(status_code=404)
    return FileResponse(icon)
