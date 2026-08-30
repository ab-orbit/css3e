"""Tests for the LangSmith env bridge.

pydantic-settings reads .env into the Settings object without exporting
anything to the process environment, but LangChain reads os.environ directly.
Without configure_tracing(), LANGCHAIN_TRACING_V2/LANGCHAIN_API_KEY in .env
are inert and the LangSmith project silently stays empty.
"""

from __future__ import annotations

import logging

from pipeline.config import Settings, configure_tracing

LANGSMITH_VARS = (
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_PROJECT",
)


def _clean_env(monkeypatch):
    for var in LANGSMITH_VARS:
        monkeypatch.delenv(var, raising=False)


def test_disabled_by_default_exports_nothing(monkeypatch):
    _clean_env(monkeypatch)
    settings = Settings(LANGCHAIN_TRACING_V2=False, LANGCHAIN_API_KEY="lsv2_x")

    assert configure_tracing(settings) is False
    import os

    assert not any(var in os.environ for var in LANGSMITH_VARS)


def test_enabled_exports_all_three(monkeypatch):
    _clean_env(monkeypatch)
    settings = Settings(
        LANGCHAIN_TRACING_V2=True,
        LANGCHAIN_API_KEY="lsv2_from_dotenv",
        LANGCHAIN_PROJECT="my-project",
    )

    assert configure_tracing(settings) is True
    import os

    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_API_KEY"] == "lsv2_from_dotenv"
    assert os.environ["LANGCHAIN_PROJECT"] == "my-project"


def test_existing_shell_key_is_not_clobbered(monkeypatch):
    """An operator who exported a key in their shell meant THAT key. Replacing
    it with the .env one would ship traces to the wrong workspace.
    """
    _clean_env(monkeypatch)
    monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_from_shell")
    settings = Settings(LANGCHAIN_TRACING_V2=True, LANGCHAIN_API_KEY="lsv2_from_dotenv")

    configure_tracing(settings)
    import os

    assert os.environ["LANGCHAIN_API_KEY"] == "lsv2_from_shell"


def test_enabled_without_any_key_warns_and_stays_off(monkeypatch, caplog):
    _clean_env(monkeypatch)
    settings = Settings(LANGCHAIN_TRACING_V2=True, LANGCHAIN_API_KEY="")

    with caplog.at_level(logging.WARNING, logger="pipeline.config"):
        assert configure_tracing(settings) is False

    assert "no LANGCHAIN_API_KEY" in caplog.text
    import os

    assert "LANGCHAIN_TRACING_V2" not in os.environ


def test_build_graph_activates_tracing(monkeypatch):
    """The bridge has to run on every pipeline run, not just via the CLI."""
    _clean_env(monkeypatch)
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "")
    called: list[bool] = []

    import pipeline.graph.build_graph as bg

    monkeypatch.setattr(bg, "configure_tracing", lambda: called.append(True))
    bg.build_graph(skip_content_review=True)

    assert called == [True]
