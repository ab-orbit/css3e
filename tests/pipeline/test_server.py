"""Authoring server: upload, streaming, and the static site it serves.

The graph is stubbed. What is under test is the server's own contract — the
run lifecycle, SSE framing, and the safety properties that matter for a process
holding API keys and a filesystem write path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline.server import app as app_module
from pipeline.server.runner import Run, RunRegistry, article_card, summarize


@pytest.fixture
def client():
    return TestClient(app_module.app)


@pytest.fixture
def stub_run(monkeypatch):
    """Replace graph execution with a scripted sequence of events."""
    started: list[Run] = []

    def _fake_start(self, run: Run) -> None:
        started.append(run)
        run.progress.complete("ingest_pdf")
        run.emit("progress", run.progress.snapshot())
        run.emit("node", {"node": "ingest_pdf", "summary": "121.021 caracteres"})
        run.emit("article", {"href": "x/index.html", "title": "T", "briefing": "B"})
        run.emit("done", {"elapsed": 1.0})
        run.finished = True

    monkeypatch.setattr(RunRegistry, "start", _fake_start)
    return started


class TestUpload:
    def test_starts_a_run_and_returns_its_id(self, client, stub_run):
        response = client.post(
            "/api/runs", files={"pdf": ("Context_AwareMAS.pdf", b"%PDF-1.4", "application/pdf")}
        )

        assert response.status_code == 200
        assert response.json()["run_id"]
        assert len(stub_run) == 1

    def test_slug_is_derived_from_the_filename_when_omitted(self, client, stub_run):
        response = client.post(
            "/api/runs", files={"pdf": ("Context_AwareMAS.pdf", b"%PDF", "application/pdf")}
        )
        assert response.json()["slug"] == "context-awaremas"

    def test_explicit_slug_wins(self, client, stub_run):
        response = client.post(
            "/api/runs",
            files={"pdf": ("x.pdf", b"%PDF", "application/pdf")},
            data={"slug": "meu-slug"},
        )
        assert response.json()["slug"] == "meu-slug"

    def test_non_pdf_is_rejected(self, client, stub_run):
        response = client.post(
            "/api/runs", files={"pdf": ("notas.txt", b"texto", "text/plain")}
        )
        assert response.status_code == 400
        assert not stub_run

    def test_upload_is_staged_outside_the_repo(self, client, stub_run):
        """publish decides where a PDF belongs; an upload must not land in the
        published tree before the pipeline has run.
        """
        client.post("/api/runs", files={"pdf": ("x.pdf", b"%PDF", "application/pdf")})

        staged = stub_run[0].pdf_path
        assert staged.exists()
        assert "articles" not in staged.parts


class TestEventStream:
    def _events(self, body: str) -> list[tuple[str, dict]]:
        events = []
        for block in body.split("\n\n"):
            if not block.startswith("event:"):
                continue
            name = block.split("event: ", 1)[1].split("\n", 1)[0]
            payload = block.split("data: ", 1)[1]
            events.append((name, json.loads(payload)))
        return events

    def test_streams_the_run_events_in_order(self, client, stub_run):
        run_id = client.post(
            "/api/runs", files={"pdf": ("x.pdf", b"%PDF", "application/pdf")}
        ).json()["run_id"]

        events = self._events(client.get(f"/api/runs/{run_id}/events").text)

        assert [name for name, _ in events] == ["progress", "node", "article", "done"]

    def test_payloads_are_json_with_accents_intact(self, client):
        """Portuguese log lines must survive the wire unescaped."""
        run = app_module.registry.create(Path("x.pdf"), slug="s", tema=None)
        run.emit("log", {"message": "Extração concluída"})
        run.emit("done", {"elapsed": 1})
        run.finished = True

        assert "Extração concluída" in client.get(f"/api/runs/{run.run_id}/events").text

    def test_the_stream_closes_after_done(self, client, stub_run):
        """Anything queued after a terminal event belongs to no run the client
        is still watching."""
        run_id = client.post(
            "/api/runs", files={"pdf": ("x.pdf", b"%PDF", "application/pdf")}
        ).json()["run_id"]
        run = app_module.registry.get(run_id)
        run.emit("log", {"message": "tarde demais"})

        assert "tarde demais" not in client.get(f"/api/runs/{run_id}/events").text

    def test_content_type_is_event_stream(self, client, stub_run):
        run_id = client.post(
            "/api/runs", files={"pdf": ("x.pdf", b"%PDF", "application/pdf")}
        ).json()["run_id"]
        response = client.get(f"/api/runs/{run_id}/events")

        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"

    def test_unknown_run_is_404(self, client):
        assert client.get("/api/runs/naoexiste/events").status_code == 404


class TestStatus:
    def test_reports_progress(self, client, stub_run):
        run_id = client.post(
            "/api/runs", files={"pdf": ("x.pdf", b"%PDF", "application/pdf")}
        ).json()["run_id"]

        body = client.get(f"/api/runs/{run_id}").json()
        assert body["finished"] is True
        assert "phases" in body and body["total_pct"] >= 0


class TestSummarize:
    def test_describes_a_known_node(self):
        assert "121,021" in summarize("ingest_pdf", {"paper_text": "x" * 121021})

    def test_a_wrong_field_name_cannot_kill_a_run(self):
        """This exact failure already cost a complete 10-minute pass."""
        class Exploding:
            def __getattr__(self, name):
                raise AttributeError(name)

        assert "sem resumo" in summarize("gen_hero", {"hero": Exploding()})


class TestArticleCard:
    def test_card_appears_as_soon_as_the_hero_exists(self):
        class Hero:
            h1 = "Título"
            lede = "Resumo."

        run = Run(run_id="r", pdf_path=Path("x.pdf"), slug="s", tema="t")
        card = article_card("gen_hero", {"hero": Hero()}, run)

        assert card["title"] == "Título"
        assert card["href"] == "../t/s/index.html"

    def test_no_card_before_the_hero(self):
        run = Run(run_id="r", pdf_path=Path("x.pdf"), slug="s")
        assert article_card("ingest_pdf", {"paper_text": "x"}, run) is None
