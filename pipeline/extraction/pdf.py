"""PDF text extraction. Three backends, selected via Settings.pdf_extractor:

- "calia" (default): posts the PDF to the Aeonbridge Calia
  `/api/convert/to-markdown` endpoint, which returns cleaned Markdown with
  headings, tables and inline math preserved. Far better structural fidelity
  on multi-column academic papers than the local backends, and the Markdown
  headings/tables are what the downstream LLM nodes key off of.
- "pdftotext" (poppler, `pdftotext -layout`): local fallback, no network.
  Requires the `pdftotext` binary on PATH (brew install poppler on macOS).
- "pypdf": pure-Python fallback, no external binary, worst layout fidelity
  on multi-column papers.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from pipeline.config import Settings

logger = logging.getLogger(__name__)


class PdfExtractionError(RuntimeError):
    pass


def extract_text(pdf_path: Path, settings: Settings) -> str:
    if settings.pdf_extractor == "calia":
        return _extract_with_calia(pdf_path, settings)
    if settings.pdf_extractor == "pdftotext":
        return _extract_with_pdftotext(pdf_path)
    if settings.pdf_extractor == "pypdf":
        return _extract_with_pypdf(pdf_path)
    raise PdfExtractionError(f"Unknown PDF_EXTRACTOR: {settings.pdf_extractor!r}")


def _extract_with_calia(pdf_path: Path, settings: Settings) -> str:
    """POST the PDF as multipart/form-data and return `data.cleaned_text`.

    The response also carries `injection_signals` — the service's own
    heuristic scan for prompt-injection-shaped content in the document. The
    extracted text is fed verbatim into every downstream LLM prompt, so a
    medium/high risk score is logged loudly here rather than silently passed
    on; it is a warning, not a hard failure, since academic PDFs trip the
    weak rules routinely (imperative sentences in reference titles, etc).
    """
    import httpx

    if not settings.calia_api_key:
        raise PdfExtractionError(
            "CALIA_API_KEY is not set. Copy .env.example to .env and fill it in, "
            "or set PDF_EXTRACTOR=pdftotext to use the local backend."
        )

    url = settings.calia_api_url.rstrip("/") + "/api/convert/to-markdown"
    params = {
        "include_raw": str(settings.calia_include_raw).lower(),
        "redact": settings.calia_redact,
    }
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {settings.calia_api_key}",
    }

    try:
        with pdf_path.open("rb") as fh:
            response = httpx.post(
                url,
                params=params,
                headers=headers,
                files={"file": (pdf_path.name, fh, "application/pdf")},
                data={"url": ""},
                timeout=settings.calia_timeout_seconds,
            )
    except httpx.HTTPError as exc:
        raise PdfExtractionError(f"Calia request failed: {exc}") from exc

    if response.status_code != 200:
        raise PdfExtractionError(
            f"Calia returned HTTP {response.status_code}: {response.text[:500]}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise PdfExtractionError(
            f"Calia returned a non-JSON body: {response.text[:500]}"
        ) from exc

    data = payload.get("data") or {}
    if not data.get("success", False):
        raise PdfExtractionError(f"Calia reported failure: {payload!r}")

    signals = data.get("injection_signals") or {}
    risk = signals.get("risk")
    if risk in {"medium", "high"}:
        rules = sorted({s.get("rule") for s in signals.get("signals", []) if s.get("rule")})
        logger.warning(
            "Calia flagged prompt-injection risk=%s (score=%s, rules=%s) in %s. "
            "This text is fed verbatim into every LLM prompt — review it at the "
            "review_extraction checkpoint before letting the fan-out run.",
            risk,
            signals.get("score"),
            ", ".join(rules) or "unnamed",
            pdf_path.name,
        )

    text = data.get("cleaned_text") or ""
    if not text.strip():
        raise PdfExtractionError(f"Calia returned no text for {pdf_path.name}")
    return text


def _extract_with_pdftotext(pdf_path: Path) -> str:
    if shutil.which("pdftotext") is None:
        raise PdfExtractionError(
            "pdftotext not found on PATH. Install poppler (`brew install poppler`) "
            "or set PDF_EXTRACTOR=pypdf in .env."
        )
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PdfExtractionError(f"pdftotext failed: {result.stderr.strip()}")
    return result.stdout


def _extract_with_pypdf(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise PdfExtractionError("pypdf not installed") from exc

    reader = PdfReader(str(pdf_path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)
