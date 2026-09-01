"""robots.txt stays hand-maintained (the AI-crawler allowlist rarely
changes). The pipeline only verifies the Sitemap: line points at the
configured site_base_url and warns — never rewrites the file.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pipeline.config import REPO_ROOT

logger = logging.getLogger(__name__)

ROBOTS_PATH = REPO_ROOT / "robots.txt"


def verify_sitemap_reference(base_url: str, path: Path = ROBOTS_PATH) -> bool:
    if not path.exists():
        logger.warning("robots.txt not found at %s", path)
        return False
    expected = f"Sitemap: {base_url}sitemap.xml"
    if expected not in path.read_text(encoding="utf-8"):
        logger.warning(
            "robots.txt does not reference %s — add `%s` manually.", expected, expected
        )
        return False
    return True
