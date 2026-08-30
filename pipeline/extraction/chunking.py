"""Sliding-window chunking with offset bookkeeping.

Span-based extractors (GLiNER, GLiREL) run over a few hundred tokens at a time,
while a paper runs to 120k+ characters. The text is therefore cut into
overlapping windows, and every span a model reports comes back with offsets
local to its window.

Remapping those offsets onto the full text is what preserves provenance. It is
also the easiest thing in this pipeline to get quietly wrong: an off-by-N maps
every quote onto the wrong passage while still producing plausible-looking
output, so `Chunk.start` is treated as an invariant and verified in tests.
"""

from __future__ import annotations

from dataclasses import dataclass

# Paragraph first, then sentence, then any whitespace: cutting at a paragraph
# break keeps an entity and the sentence supporting it inside one window.
_BOUNDARIES = ("\n\n", ". ", "\n", " ")


@dataclass(frozen=True)
class Chunk:
    """A window of the source text, with the offset it starts at.

    Invariant: ``full_text[chunk.start : chunk.start + len(chunk.text)] == chunk.text``
    """

    start: int
    text: str

    @property
    def end(self) -> int:
        return self.start + len(self.text)


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 200) -> list[Chunk]:
    """Cut `text` into overlapping windows of at most `max_chars`.

    Windows prefer to end on a paragraph or sentence boundary. `overlap` keeps
    an entity that straddles a cut findable in at least one window.
    """
    if overlap >= max_chars:
        raise ValueError(
            f"overlap ({overlap}) must be smaller than max_chars ({max_chars}); "
            "otherwise each window starts before the previous one and the scan "
            "never advances"
        )
    if not text:
        return []

    chunks: list[Chunk] = []
    position = 0
    length = len(text)

    while position < length:
        window_end = min(position + max_chars, length)

        if window_end < length:
            window_end = _best_cut(text, position, window_end)

        chunks.append(Chunk(start=position, text=text[position:window_end]))

        if window_end >= length:
            break

        # Step forward by at least one character even when a boundary lands
        # badly, so an unbreakable run (a long token, a table row) cannot stall
        # the loop.
        position = max(window_end - overlap, position + 1)

    return chunks


def _best_cut(text: str, start: int, hard_end: int) -> int:
    """Find the latest natural boundary before `hard_end`.

    Only boundaries in the last third of the window are considered: cutting far
    earlier would waste most of the window and multiply the number of model
    calls.
    """
    earliest = start + (hard_end - start) * 2 // 3

    for boundary in _BOUNDARIES:
        found = text.rfind(boundary, earliest, hard_end)
        if found != -1:
            return found + len(boundary)

    return hard_end


def remap_offset(chunk: Chunk, local_offset: int) -> int:
    """Translate an offset inside `chunk` into an offset in the full text.

    Rejects an out-of-range offset rather than clamping it: a model returning a
    span outside the window it was given is a bug worth surfacing, and clamping
    would publish a quote pointing at the wrong passage.
    """
    if not 0 <= local_offset <= len(chunk.text):
        raise ValueError(
            f"local offset {local_offset} is outside a chunk of "
            f"{len(chunk.text)} chars (starting at {chunk.start})"
        )
    return chunk.start + local_offset
