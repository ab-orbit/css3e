"""Tests for prompt placeholder substitution.

Regression guard: the prompts are Portuguese prose that uses braces as
ordinary notation ("uma lista ordenada de atributos {label, texto}"). Passing
those through str.format raises KeyError: 'label, texto' and killed a full
end-to-end run at the analyze_paper node.
"""

from __future__ import annotations

import re

import pytest

from pipeline.llm.client import PROMPTS_DIR, load_prompt, render_prompt


def test_substitutes_declared_placeholders():
    out = render_prompt("Texto: {paper_text}\nURL: {source_pdf_url}", {
        "paper_text": "ABC",
        "source_pdf_url": "http://x/y.pdf",
    })
    assert out == "Texto: ABC\nURL: http://x/y.pdf"


def test_leaves_prose_braces_untouched():
    template = "liste atributos {label, texto} do artigo: {paper_text}"
    assert render_prompt(template, {"paper_text": "ABC"}) == (
        "liste atributos {label, texto} do artigo: ABC"
    )


def test_leaves_json_examples_untouched():
    template = 'Responda como {"code": "CAT-A"} usando {paper_analysis_json}'
    out = render_prompt(template, {"paper_analysis_json": "{}"})
    assert '{"code": "CAT-A"}' in out


def test_unknown_variable_raises():
    """A variable with no placeholder is a silently-dropped input — it would
    send a subtly wrong prompt to the model instead of failing loudly.
    """
    with pytest.raises(KeyError, match="no placeholder for"):
        render_prompt("sem nada", {"paper_text": "ABC"})


def test_substituted_value_containing_braces_is_not_re_expanded():
    """paper_analysis_json is JSON, so it is full of braces. They must survive
    substitution as literal text, not be treated as further placeholders.
    """
    out = render_prompt("{paper_analysis_json}", {"paper_analysis_json": '{"a": {"b": 1}}'})
    assert out == '{"a": {"b": 1}}'


@pytest.mark.parametrize(
    "prompt_path", sorted(PROMPTS_DIR.glob("*.md")), ids=lambda p: p.stem
)
def test_every_shipped_prompt_renders_with_its_placeholders(prompt_path):
    """Each prompt must survive rendering with a value for every placeholder it
    declares — catching any template that still relies on str.format semantics.
    """
    template = load_prompt(prompt_path.stem)
    placeholders = set(re.findall(r"\{(\w+)\}", template))
    rendered = render_prompt(template, {name: f"<{name}>" for name in placeholders})

    for name in placeholders:
        assert f"<{name}>" in rendered
        assert "{" + name + "}" not in rendered
