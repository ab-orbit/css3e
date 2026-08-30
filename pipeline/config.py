"""Settings loaded from .env (see .env.example for the full list)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = REPO_ROOT / "articles"
MANIFEST_PATH = REPO_ROOT / "pipeline" / "articles.yaml"
SHARED_STYLESHEET = "resources/cases/style.css"
SHARED_OG_IMAGE = "three-categories.png"


def published_pdf_name(slug: str) -> str:
    """Filename the source PDF is published under, inside the article folder.

    The PDF is copied next to the pages (like audio/ and slides/) so the site
    is self-contained: linking to wherever the operator happened to keep the
    file — usually somewhere under their home directory — produces a link that
    only ever works on that one machine.
    """
    return f"{slug}.pdf"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="anthropic/claude-sonnet-4.5", alias="OPENROUTER_MODEL"
    )
    openrouter_model_fast: str = Field(
        default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL_FAST"
    )

    site_base_url: str = Field(
        default="https://ab-orbit.github.io/css3e/", alias="SITE_BASE_URL"
    )
    default_authors: str = Field(
        default="Bruna Juliana Melo da Costa,Jefferson Wellington da Cunha",
        alias="DEFAULT_AUTHORS",
    )
    default_publisher_name: str = Field(
        default="Centro de Informática, UFPE", alias="DEFAULT_PUBLISHER_NAME"
    )

    notebooklm_auth_json: str = Field(default="", alias="NOTEBOOKLM_AUTH_JSON")

    # PDF -> text. "calia" (default) uses the Aeonbridge Calia
    # /api/convert/to-markdown service; "pdftotext"/"pypdf" are local fallbacks.
    pdf_extractor: str = Field(default="calia", alias="PDF_EXTRACTOR")
    calia_api_url: str = Field(default="https://aeonbridge.io/calia", alias="CALIA_API_URL")
    calia_api_key: str = Field(default="", alias="CALIA_API_KEY")
    # Ask for the raw (uncleaned) text alongside cleaned_text. The pipeline only
    # consumes cleaned_text, so this stays off to keep responses small.
    calia_include_raw: bool = Field(default=False, alias="CALIA_INCLUDE_RAW")
    # Server-side PII redaction mode: "none" | "mask" | "hash" (service-defined).
    calia_redact: str = Field(default="none", alias="CALIA_REDACT")
    # Long papers take tens of seconds to convert; well above httpx's 5s default.
    calia_timeout_seconds: float = Field(default=180.0, alias="CALIA_TIMEOUT_SECONDS")

    # --- Entity/relation extraction (GLiNER + GLiREL) ---
    # Off by default: enabling it pulls torch and downloads ~2GB of models.
    entity_extraction: bool = Field(default=False, alias="ENTITY_EXTRACTION")
    # HF_HOME for the models. Points at external storage so a 2GB download does
    # not land in the home directory by surprise.
    entity_model_dir: str = Field(
        default="/Volumes/T9/lm-studio/models/hf", alias="ENTITY_MODEL_DIR"
    )
    gliner_model: str = Field(default="urchade/gliner_multi-v2.1", alias="GLINER_MODEL")
    glirel_model: str = Field(default="jackboyla/glirel-large-v0", alias="GLIREL_MODEL")
    entity_device: str = Field(default="auto", alias="ENTITY_DEVICE")
    # Window sizing. The encoder handles a few hundred tokens; the overlap keeps
    # an entity that straddles a cut findable in at least one window.
    entity_chunk_chars: int = Field(default=1200, alias="ENTITY_CHUNK_CHARS")
    entity_chunk_overlap: int = Field(default=200, alias="ENTITY_CHUNK_OVERLAP")
    entity_threshold: float = Field(default=0.5, alias="ENTITY_THRESHOLD")
    relation_threshold: float = Field(default=0.6, alias="RELATION_THRESHOLD")
    # Caps keep the rendered graph readable; a 120k-char survey otherwise
    # yields hundreds of nodes that draw as an unreadable hairball.
    entity_max_count: int = Field(default=40, alias="ENTITY_MAX_COUNT")
    relation_max_count: int = Field(default=60, alias="RELATION_MAX_COUNT")
    relation_quote_chars: int = Field(default=400, alias="RELATION_QUOTE_CHARS")

    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str = Field(default="", alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="css3e-pipeline", alias="LANGCHAIN_PROJECT")

    @property
    def default_authors_list(self) -> list[str]:
        return [a.strip() for a in self.default_authors.split(",") if a.strip()]


def get_settings() -> Settings:
    return Settings()

def configure_tracing(settings: Settings | None = None) -> bool:
    """Export the LangSmith variables into os.environ and report whether
    tracing is on.

    Necessary because pydantic-settings reads .env into this Settings object
    WITHOUT exporting anything to the process environment, while LangChain
    reads os.environ directly. Without this bridge, LANGCHAIN_TRACING_V2 and
    LANGCHAIN_API_KEY in .env are inert and the LangSmith project stays empty.

    A value already present in os.environ wins — an operator who exported a key
    in their shell meant that key, and silently replacing it with the one in
    .env would send traces to the wrong workspace.
    """
    settings = settings or get_settings()
    if not settings.langchain_tracing_v2:
        return False
    if not settings.langchain_api_key and not os.environ.get("LANGCHAIN_API_KEY"):
        logger.warning(
            "LANGCHAIN_TRACING_V2 is on but no LANGCHAIN_API_KEY is set; "
            "LangChain will not be able to upload traces."
        )
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
    logger.info(
        "LangSmith tracing enabled, project=%s", os.environ["LANGCHAIN_PROJECT"]
    )
    return True

