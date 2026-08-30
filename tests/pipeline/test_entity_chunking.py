"""Sliding-window chunking and offset remapping.

The encoder takes a few hundred tokens; a paper runs to 120k+ characters. The
text is therefore windowed, and every offset a model reports is local to its
window. Remapping those back onto the full text is what preserves provenance —
get it wrong and every quote on the published page points at the wrong span,
silently.
"""

from __future__ import annotations

import pytest

from pipeline.extraction.chunking import Chunk, chunk_text, remap_offset


class TestChunkText:
    def test_short_text_is_a_single_chunk_at_offset_zero(self):
        chunks = chunk_text("uma frase curta", max_chars=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0].start == 0
        assert chunks[0].text == "uma frase curta"

    def test_chunks_cover_the_whole_text(self):
        text = "\n\n".join(f"Paragrafo numero {i} com algum conteudo." for i in range(40))
        chunks = chunk_text(text, max_chars=200, overlap=40)

        covered = set()
        for c in chunks:
            covered.update(range(c.start, c.start + len(c.text)))
        assert covered == set(range(len(text)))

    def test_every_chunk_text_matches_the_source_at_its_offset(self):
        """The invariant the whole remapping rests on."""
        text = "\n\n".join(f"Bloco {i}: conteudo variado aqui." for i in range(30))
        for c in chunk_text(text, max_chars=150, overlap=30):
            assert text[c.start : c.start + len(c.text)] == c.text

    def test_chunks_respect_the_size_limit(self):
        text = "palavra " * 500
        for c in chunk_text(text, max_chars=200, overlap=20):
            assert len(c.text) <= 200

    def test_consecutive_chunks_overlap(self):
        """Overlap keeps an entity that straddles a boundary findable in at
        least one window."""
        text = "\n\n".join(f"Secao {i} texto." for i in range(30))
        chunks = chunk_text(text, max_chars=120, overlap=40)
        assert len(chunks) > 1
        for prev, nxt in zip(chunks, chunks[1:]):
            assert nxt.start < prev.start + len(prev.text)

    def test_prefers_paragraph_boundaries(self):
        text = "Primeiro paragrafo aqui.\n\nSegundo paragrafo aqui.\n\nTerceiro aqui."
        chunks = chunk_text(text, max_chars=30, overlap=0)
        assert any(c.text.startswith("Segundo") for c in chunks)

    def test_empty_text_yields_no_chunks(self):
        assert chunk_text("", max_chars=100, overlap=10) == []

    def test_word_longer_than_the_window_does_not_loop_forever(self):
        text = "x" * 500
        chunks = chunk_text(text, max_chars=100, overlap=20)
        assert chunks
        assert sum(len(c.text) for c in chunks) >= 500

    def test_overlap_larger_than_window_is_rejected(self):
        """Would make each chunk start before the previous one — no progress."""
        with pytest.raises(ValueError):
            chunk_text("abc", max_chars=10, overlap=10)


class TestRemapOffset:
    def test_maps_local_offset_to_global(self):
        chunk = Chunk(start=1000, text="Context-Aware Systems are useful")
        assert remap_offset(chunk, 0) == 1000
        assert remap_offset(chunk, 14) == 1014

    def test_roundtrip_recovers_the_exact_span(self):
        text = "prefixo " * 50 + "Multi-Agent Systems" + " sufixo" * 50
        local_start = 5
        chunk = Chunk(start=text.index("Multi-Agent") - local_start,
                      text=text[text.index("Multi-Agent") - local_start :][:60])

        global_start = remap_offset(chunk, local_start)
        assert text[global_start : global_start + len("Multi-Agent Systems")] == (
            "Multi-Agent Systems"
        )

    def test_offset_outside_the_chunk_is_rejected(self):
        """A model returning an out-of-range span is a bug worth surfacing, not
        an offset to silently clamp into a wrong quote.
        """
        chunk = Chunk(start=100, text="curto")
        with pytest.raises(ValueError):
            remap_offset(chunk, 99)
