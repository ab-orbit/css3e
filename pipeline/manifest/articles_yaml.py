"""pipeline/articles.yaml — single source of truth. Every `publish` run
upserts this article's ManifestEntry by slug, then sitemap.py/llms_txt.py
fully regenerate their targets from the complete file (never patched).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from pipeline.config import MANIFEST_PATH
from pipeline.schemas.package import ManifestEntry


def load_manifest(path: Path = MANIFEST_PATH) -> list[ManifestEntry]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [ManifestEntry.model_validate(row) for row in raw]


def save_manifest(entries: list[ManifestEntry], path: Path = MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [e.model_dump(exclude_none=False) for e in entries]
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )


def upsert(entry: ManifestEntry, path: Path = MANIFEST_PATH) -> list[ManifestEntry]:
    entries = load_manifest(path)
    entries = [e for e in entries if e.slug != entry.slug]
    entries.append(entry)
    entries.sort(key=lambda e: (e.tema, e.slug))
    save_manifest(entries, path)
    return entries
