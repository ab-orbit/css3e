"""Unit tests for the Calia PDF-extraction backend.

httpx.post is monkeypatched so these run offline; the contract under test is
the request shape (URL, params, auth header, multipart body) and the response
handling (cleaned_text, success flag, injection_signals, error paths).
"""

from __future__ import annotations

import logging

import httpx
import pytest

from pipeline.config import Settings
from pipeline.extraction.pdf import PdfExtractionError, extract_text


@pytest.fixture
def settings() -> Settings:
    return Settings(
        PDF_EXTRACTOR="calia",
        CALIA_API_KEY="test-key",
        CALIA_API_URL="https://example.test/calia",
    )


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    return path


def _fake_post(captured: dict, *, status_code: int = 200, json_body=None, text_body=""):
    def _post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        request = httpx.Request("POST", url)
        if json_body is not None:
            return httpx.Response(status_code, json=json_body, request=request)
        return httpx.Response(status_code, text=text_body, request=request)

    return _post


def _ok_body(cleaned_text="## Title\n\nBody text.", **extra):
    data = {"success": True, "detected_type": "pdf", "cleaned_text": cleaned_text}
    data.update(extra)
    return {"data": data, "metadata": {}}


def test_calia_returns_cleaned_text(monkeypatch, settings, pdf):
    captured: dict = {}
    monkeypatch.setattr(httpx, "post", _fake_post(captured, json_body=_ok_body()))

    assert extract_text(pdf, settings) == "## Title\n\nBody text."


def test_calia_request_shape(monkeypatch, settings, pdf):
    captured: dict = {}
    monkeypatch.setattr(httpx, "post", _fake_post(captured, json_body=_ok_body()))

    extract_text(pdf, settings)

    assert captured["url"] == "https://example.test/calia/api/convert/to-markdown"
    assert captured["params"] == {"include_raw": "false", "redact": "none"}
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["data"] == {"url": ""}
    name, _handle, content_type = captured["files"]["file"]
    assert name == "paper.pdf"
    assert content_type == "application/pdf"


def test_calia_missing_key_raises(pdf):
    settings = Settings(PDF_EXTRACTOR="calia", CALIA_API_KEY="")
    with pytest.raises(PdfExtractionError, match="CALIA_API_KEY is not set"):
        extract_text(pdf, settings)


def test_calia_http_error_raises(monkeypatch, settings, pdf):
    captured: dict = {}
    monkeypatch.setattr(
        httpx, "post", _fake_post(captured, status_code=401, text_body="unauthorized")
    )
    with pytest.raises(PdfExtractionError, match="HTTP 401"):
        extract_text(pdf, settings)


def test_calia_success_false_raises(monkeypatch, settings, pdf):
    captured: dict = {}
    body = {"data": {"success": False, "error": "unsupported"}, "metadata": {}}
    monkeypatch.setattr(httpx, "post", _fake_post(captured, json_body=body))
    with pytest.raises(PdfExtractionError, match="reported failure"):
        extract_text(pdf, settings)


def test_calia_empty_text_raises(monkeypatch, settings, pdf):
    captured: dict = {}
    monkeypatch.setattr(
        httpx, "post", _fake_post(captured, json_body=_ok_body(cleaned_text="   "))
    )
    with pytest.raises(PdfExtractionError, match="returned no text"):
        extract_text(pdf, settings)


def test_calia_transport_error_raises(monkeypatch, settings, pdf):
    def _boom(url, **kwargs):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(httpx, "post", _boom)
    with pytest.raises(PdfExtractionError, match="Calia request failed"):
        extract_text(pdf, settings)


def test_calia_logs_injection_risk(monkeypatch, settings, pdf, caplog):
    captured: dict = {}
    signals = {
        "risk": "medium",
        "score": 1,
        "signals": [{"rule": "reader_directed_imperative", "tier": "weak"}],
    }
    monkeypatch.setattr(
        httpx, "post", _fake_post(captured, json_body=_ok_body(injection_signals=signals))
    )

    with caplog.at_level(logging.WARNING, logger="pipeline.extraction.pdf"):
        extract_text(pdf, settings)

    assert "risk=medium" in caplog.text
    assert "reader_directed_imperative" in caplog.text


def test_calia_low_risk_is_silent(monkeypatch, settings, pdf, caplog):
    captured: dict = {}
    signals = {"risk": "low", "score": 0, "signals": []}
    monkeypatch.setattr(
        httpx, "post", _fake_post(captured, json_body=_ok_body(injection_signals=signals))
    )

    with caplog.at_level(logging.WARNING, logger="pipeline.extraction.pdf"):
        extract_text(pdf, settings)

    assert caplog.text == ""


def test_unknown_backend_raises(pdf):
    settings = Settings(PDF_EXTRACTOR="nope")
    with pytest.raises(PdfExtractionError, match="Unknown PDF_EXTRACTOR"):
        extract_text(pdf, settings)
