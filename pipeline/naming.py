"""CASRAI-conformant filenames for incoming research PDFs.

Rules from the CASRAI guide "File naming and folder structure conventions for
research data":

- ISO 8601 compact dates (YYYYMMDD) so names sort correctly as plain text
- underscores/hyphens as separators, never spaces (spaces split a filename
  into two arguments in command-line tools)
- letters, numbers, underscores and hyphens only; reserved characters
  (/ : * ? " < > | & % # @ $ !) and accented characters break scripts
- one consistent case for the whole project; lowercase is the safest default,
  since case-insensitive filesystems otherwise allow silent collisions
- two-digit version numbers, so v09 sorts before v10
- full path under roughly 255 characters
- most stable element first, most variable element last

Pattern: ``<project>_<description>_<YYYYMMDD>_v<NN>.<ext>``
Example: ``css3e_context-aware-multi-agent-systems_20260829_v01.pdf``

The slug used in URLs is deliberately NOT this name. A filename carries a date
and a version and changes when the paper is revised; a slug is the article's
permanent web identity. Tying them together would break every published link
the moment a v02 arrived.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path

PROJECT_ID = "css3e"

# Longest description kept in a name. The guide caps the FULL path near 255
# chars; leaving the description generous but bounded keeps room for the
# articles/<tema>/<slug>/ prefix without truncating mid-run.
MAX_DESCRIPTION_CHARS = 80

# Reserved by operating systems or listed as "avoid" by the guide.
_RESERVED = r'/:*?"<>|&%#@$!'


def slugify_description(text: str) -> str:
    """Reduce free text to the CASRAI-safe description element.

    Accents are transliterated rather than stripped, so "Sensíveis" becomes
    "sensiveis" and not "sensveis". Underscores collapse to hyphens because the
    pattern reserves "_" for separating the four elements — a description
    containing one would make the name ambiguous to parse.
    """
    # NFKD splits an accented character into base + combining mark; dropping
    # the marks leaves the ASCII base letter.
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_text = ascii_text.encode("ascii", "ignore").decode("ascii")

    lowered = ascii_text.lower()
    for char in _RESERVED:
        lowered = lowered.replace(char, " ")
    # Everything that is not a kept character becomes a separator, including
    # the underscore (reserved for element separation).
    hyphenated = re.sub(r"[^a-z0-9]+", "-", lowered)
    return hyphenated.strip("-")


def _truncate(description: str, limit: int = MAX_DESCRIPTION_CHARS) -> str:
    """Cut to `limit` without leaving a dangling separator or a split word."""
    if len(description) <= limit:
        return description
    cut = description[:limit]
    # Prefer cutting at the last word boundary; fall back to a hard cut if the
    # first "word" is itself longer than the limit.
    if "-" in cut:
        cut = cut.rsplit("-", 1)[0]
    return cut.strip("-")


def casrai_filename(
    description: str,
    *,
    when: date | None = None,
    version: int = 1,
    suffix: str = ".pdf",
) -> str:
    """Build ``<project>_<description>_<YYYYMMDD>_v<NN><suffix>``."""
    when = when or date.today()
    slug = _truncate(slugify_description(description)) or "untitled"
    stamp = when.strftime("%Y%m%d")
    return f"{PROJECT_ID}_{slug}_{stamp}_v{version:02d}{suffix.lower()}"


def unique_casrai_filename(
    directory: Path,
    description: str,
    *,
    when: date | None = None,
    suffix: str = ".pdf",
    max_version: int = 99,
) -> str:
    """Like `casrai_filename`, bumping the version until the name is free.

    A repeat ingest of the same paper is a new version of that file, which is
    exactly what the version element is for — so this never overwrites and
    never invents a "-copy" suffix outside the convention.
    """
    directory = Path(directory)

    # The guide caps the FULL path (drive + folders + filename), not just the
    # filename. Solve for the description budget once, from the fixed cost of
    # everything else, rather than shrinking in a loop.
    fixed = len(f"{directory}/{PROJECT_ID}__20260101_v01{suffix.lower()}")
    budget = min(MAX_DESCRIPTION_CHARS, 254 - fixed)
    if budget < 1:
        raise ValueError(
            f"Directory path is too long to hold any CASRAI filename: {directory}"
        )

    slug = _truncate(slugify_description(description), limit=budget) or "untitled"
    for version in range(1, max_version + 1):
        name = casrai_filename(slug, when=when, version=version, suffix=suffix)
        if not (directory / name).exists():
            return name
    raise ValueError(
        f"Exhausted versions v01..v{max_version:02d} for {description!r} in {directory}"
    )
