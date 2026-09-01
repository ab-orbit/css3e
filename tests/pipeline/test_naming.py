"""CASRAI file-naming conventions.

Rules from casrai.org/guides/file-naming-and-folder-structure-conventions-for-research-data:
ISO 8601 compact dates, underscore/hyphen separators only, [a-z0-9_-] charset,
one consistent case, two-digit versions, full path under ~255 chars, most
stable element first.
"""

from __future__ import annotations

from datetime import date

import pytest

from pipeline.naming import PROJECT_ID, casrai_filename, slugify_description


class TestSlugifyDescription:
    def test_lowercases_and_hyphenates(self):
        assert slugify_description("Context Aware MAS") == "context-aware-mas"

    def test_transliterates_accents(self):
        """Accented characters are explicitly listed as 'avoid' — they break
        scripts and encode differently across filesystems.
        """
        assert slugify_description("Sistemas Sensíveis ao Contexto") == (
            "sistemas-sensiveis-ao-contexto"
        )
        assert slugify_description("Ação e Coordenação") == "acao-e-coordenacao"

    @pytest.mark.parametrize("char", list('/:*?"<>|&%#@$!'))
    def test_strips_every_reserved_character(self, char):
        assert char not in slugify_description(f"a{char}b")

    def test_collapses_runs_of_separators(self):
        assert slugify_description("a   --  b") == "a-b"

    def test_strips_leading_and_trailing_separators(self):
        assert slugify_description("  -- hello --  ") == "hello"

    def test_underscores_become_hyphens_inside_the_description(self):
        """The pattern reserves '_' to separate the four elements, so the
        description itself must not contain one or the parts stop parsing.
        """
        assert "_" not in slugify_description("Context_AwareMAS")


class TestCasraiFilename:
    def test_follows_the_documented_pattern(self):
        name = casrai_filename(
            "A Comprehensive Survey on Context-Aware Multi-Agent Systems",
            when=date(2026, 8, 29),
        )
        assert name.startswith(f"{PROJECT_ID}_")
        assert name.endswith("_20260829_v01.pdf")

    def test_date_is_iso_compact_so_it_sorts_as_text(self):
        earlier = casrai_filename("paper", when=date(2026, 1, 5))
        later = casrai_filename("paper", when=date(2026, 11, 20))
        assert earlier < later

    def test_version_is_two_digits_so_v09_sorts_before_v10(self):
        v9 = casrai_filename("paper", when=date(2026, 1, 1), version=9)
        v10 = casrai_filename("paper", when=date(2026, 1, 1), version=10)
        assert "_v09." in v9 and "_v10." in v10
        assert v9 < v10

    def test_charset_is_restricted(self):
        name = casrai_filename("Ação: Métodos & Análise (2026)", when=date(2026, 8, 29))
        stem = name.rsplit(".", 1)[0]
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
        assert set(stem) <= allowed, f"{name} contains {set(stem) - allowed}"

    def test_no_spaces(self):
        assert " " not in casrai_filename("a b c d", when=date(2026, 8, 29))

    def test_extension_is_preserved_and_lowercased(self):
        assert casrai_filename("paper", when=date(2026, 1, 1), suffix=".PDF").endswith(".pdf")

    def test_long_titles_are_truncated_to_keep_paths_workable(self):
        name = casrai_filename("word " * 100, when=date(2026, 1, 1))
        assert len(name) <= 120
        assert name.endswith("_20260101_v01.pdf")

    def test_truncation_does_not_leave_a_trailing_separator(self):
        name = casrai_filename("aaaa " * 100, when=date(2026, 1, 1))
        description = name.split("_")[1]
        assert not description.endswith("-")

    def test_empty_description_still_produces_a_valid_name(self):
        name = casrai_filename("...", when=date(2026, 1, 1))
        assert name == f"{PROJECT_ID}_untitled_20260101_v01.pdf"


class TestUniqueFilename:
    def test_bumps_version_when_the_name_is_taken(self, tmp_path):
        from pipeline.naming import unique_casrai_filename

        first = unique_casrai_filename(tmp_path, "paper", when=date(2026, 1, 1))
        (tmp_path / first).write_bytes(b"x")

        second = unique_casrai_filename(tmp_path, "paper", when=date(2026, 1, 1))
        assert "_v01." in first
        assert "_v02." in second

    def test_long_title_in_a_deep_directory_still_fits_the_path_limit(self, tmp_path):
        """The description shrinks to fit the budget the directory leaves."""
        from pipeline.naming import unique_casrai_filename

        deep = tmp_path / ("d" * 40) / ("e" * 40)
        deep.mkdir(parents=True)

        name = unique_casrai_filename(deep, "word " * 100, when=date(2026, 1, 1))

        assert len(str(deep / name)) < 255
        assert name.endswith("_20260101_v01.pdf")

    def test_impossible_directory_fails_loudly(self, tmp_path):
        """A directory so deep that no conformant filename fits must raise, not
        silently emit a path that breaks sync clients downstream.
        """
        from pipeline.naming import unique_casrai_filename

        too_deep = tmp_path / ("d" * 100) / ("e" * 100)
        too_deep.mkdir(parents=True)

        with pytest.raises(ValueError, match="too long"):
            unique_casrai_filename(too_deep, "paper", when=date(2026, 1, 1))
