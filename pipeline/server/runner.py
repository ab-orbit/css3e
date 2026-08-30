"""Runs the pipeline in a background thread and publishes events to a queue.

The graph is synchronous and long-running (about 22 minutes), so it runs in a
worker thread while the SSE endpoint drains its event queue. Two sources feed
that queue: LangGraph's own per-node stream, and a logging handler that
captures what the pipeline logs while a node is still working — which is what
the console shows under "Em processamento".
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langgraph.types import Command

from pipeline.server.progress import RunProgress

logger = logging.getLogger(__name__)

# Anything longer is a stack trace or a dumped payload, not a status line.
MAX_LOG_LINE = 300
# Bounded so a chatty run cannot grow the queue without limit when no client is
# attached; the oldest lines are the least interesting on reconnect.
QUEUE_SIZE = 2000


@dataclass
class Event:
    name: str
    data: dict


@dataclass
class Run:
    run_id: str
    pdf_path: Path
    slug: str
    tema: str | None = None
    events: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=QUEUE_SIZE))
    progress: RunProgress = field(default_factory=RunProgress)
    started_at: float = field(default_factory=time.time)
    finished: bool = False

    def emit(self, name: str, data: dict) -> None:
        try:
            self.events.put_nowait(Event(name, data))
        except queue.Full:
            # Dropping a log line is preferable to blocking the pipeline
            # thread on a console nobody is watching.
            pass


class _QueueLogHandler(logging.Handler):
    """Forwards pipeline log records to a run's event queue."""

    def __init__(self, run: Run) -> None:
        super().__init__(level=logging.INFO)
        self._run = run

    def emit(self, record: logging.LogRecord) -> None:  # noqa: A003
        try:
            message = record.getMessage()[:MAX_LOG_LINE]
        except Exception:  # noqa: BLE001 - a broken record must not kill the run
            return
        self._run.emit("log", {"message": f"{record.name.split('.')[-1]}: {message}"})


class RunRegistry:
    """In-memory registry of runs. Process-local and deliberately not durable:
    the console is an authoring tool, and a run that outlives the server has
    already written its output to disk.
    """

    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._lock = threading.Lock()

    def create(self, pdf_path: Path, *, slug: str, tema: str | None) -> Run:
        run = Run(run_id=uuid.uuid4().hex[:12], pdf_path=pdf_path, slug=slug, tema=tema)
        with self._lock:
            self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(run_id)

    def start(self, run: Run) -> None:
        threading.Thread(target=self._execute, args=(run,), daemon=True).start()

    def _execute(self, run: Run) -> None:
        handler = _QueueLogHandler(run)
        pipeline_logger = logging.getLogger("pipeline")
        pipeline_logger.addHandler(handler)

        try:
            self._drive_graph(run)
        except Exception as exc:  # noqa: BLE001 - surfaced to the client
            logger.exception("Run %s failed", run.run_id)
            run.emit("failed", {"error": f"{type(exc).__name__}: {exc}"})
        finally:
            pipeline_logger.removeHandler(handler)
            run.finished = True

    def _drive_graph(self, run: Run) -> None:
        from pipeline.graph.build_graph import build_graph

        graph = build_graph(skip_content_review=True)
        config = {
            "configurable": {"thread_id": run.run_id},
            "recursion_limit": 50,
        }
        payload: Any = {
            "pdf_path": run.pdf_path,
            "slug": run.slug,
            "tema": run.tema,
            "copy_only": False,
            "is_copy_of_existing": False,
            "copy_canonical_root": None,
        }

        run.emit("progress", run.progress.snapshot())
        resumes = 0

        while True:
            interrupted = False
            for chunk in graph.stream(payload, config=config, stream_mode="updates"):
                for node, update in chunk.items():
                    if node == "__interrupt__":
                        interrupted = True
                        run.emit(
                            "log",
                            {"message": f"checkpoint {update[0].value['checkpoint']}: aceito"},
                        )
                        continue

                    run.progress.complete(node)
                    run.emit("node", {"node": node, "summary": summarize(node, update)})
                    run.emit("progress", run.progress.snapshot())

                    card = article_card(node, update, run)
                    if card:
                        run.emit("article", card)

            if not interrupted:
                break
            resumes += 1
            if resumes > 4:
                raise RuntimeError("graph kept interrupting; aborting")
            # Must be truthy: Command(resume={}) reads as "no resume value" and
            # the node interrupts again forever.
            payload = Command(resume={"accepted": True})

        run.emit("done", {"elapsed": round(time.time() - run.started_at, 1)})


def summarize(node: str, update: Any) -> str:
    """One line describing what a node produced.

    Guarded: a wrong field name here must never kill a run. That already cost a
    complete 10-minute pass during development.
    """
    try:
        return _summarize(update)
    except Exception as exc:  # noqa: BLE001
        return f"<sem resumo: {type(exc).__name__}>"


def _summarize(update: Any) -> str:
    if not isinstance(update, dict):
        return str(update)[:120]

    parts = []
    for key, value in update.items():
        if value is None:
            continue
        if key == "paper_text":
            parts.append(f"{len(value):,} caracteres")
        elif key == "paper":
            parts.append(f"{value.title[:50]} · {len(value.authors)} autores")
        elif key == "hero":
            parts.append(value.h1[:60])
        elif key == "categories":
            parts.append(f"{len(value)} categorias")
        elif key == "tables":
            parts.append(f"{len(value)} tabelas")
        elif key == "entity_graph":
            parts.append(f"{len(value.entities)} entidades, {len(value.relations)} relações")
        elif key in ("essay_condensed", "essay_full"):
            parts.append(f"{value.variant}: {len(value.sections)} seções")
        elif key == "workshop":
            parts.append(f"{value.duration_minutes} min")
        elif key == "seo_pages":
            parts.append(f"{len(value)} páginas")
        elif key == "downloads":
            parts.append(f"{len(value)} downloads")
        elif key == "rendered_pages":
            parts.append(", ".join(sorted(value)))
        elif key == "tema":
            parts.append(f"tema {value}")
        elif key.startswith("audio") or key.startswith("slides"):
            parts.append(str(value))
        elif key == "output_dir":
            parts.append(str(value))
    return " · ".join(parts) or "concluído"


def article_card(node: str, update: Any, run: Run) -> dict | None:
    """Card data for the gallery, as soon as a node knows enough to fill it.

    The card appears the moment the hero exists, rather than waiting for the
    twenty-minute media branch to finish.
    """
    if not isinstance(update, dict):
        return None

    hero = update.get("hero")
    if hero is None:
        return None

    tema = run.tema or "geral"
    return {
        "href": f"../{tema}/{run.slug}/index.html",
        "title": hero.h1,
        "briefing": hero.lede,
        "date": "em processamento",
    }
