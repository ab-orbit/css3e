import json

import pytest
from pydantic import ValidationError

from pipeline.schemas.base import CoercingModel
from pipeline.schemas.components import EssayVariant, MindMapSpec
from tests.pipeline.fixtures.sample_package import make_sample_package


def test_sample_package_builds_and_round_trips_json():
    pkg = make_sample_package()
    dumped = pkg.model_dump_json()
    assert '"slug":"sample-paper"' in dumped.replace(" ", "")

    from pipeline.schemas.package import ArticlePackage

    reloaded = ArticlePackage.model_validate_json(dumped)
    assert reloaded.paper.title == pkg.paper.title
    assert len(reloaded.categories) == 2
    assert reloaded.mindmap.root.children[0].t == "Categories"


def test_category_card_accent_index_is_sequential():
    pkg = make_sample_package()
    indices = [c.accent_index for c in pkg.categories]
    assert indices == [0, 1]


def test_mindmap_spec_accepts_stringified_root():
    """Some OpenRouter providers return the recursive tree as a JSON string."""
    root_json = json.dumps({"t": "Raiz", "k": "a", "children": [{"t": "Filho"}]})
    palette_json = json.dumps([{"kind": "a", "fill": "#000", "label": "a"}])

    spec = MindMapSpec(root=root_json, palette=palette_json)

    assert spec.root.t == "Raiz"
    assert spec.root.children[0].t == "Filho"
    assert spec.palette[0].kind == "a"


def test_mindmap_spec_rejects_non_json_root():
    """A string that is not JSON must still surface as a validation error."""
    with pytest.raises(ValidationError):
        MindMapSpec(root="not json at all", palette=[])


def test_essay_variant_accepts_stringified_sections():
    """The failure that killed the ethics run: a list arriving as a JSON string."""
    sections = json.dumps([{"no": "01", "heading": "Método", "paragraphs": ["um"]}])
    variant = EssayVariant.model_validate(
        {
            "variant": "full",
            "sections": sections,
            "drop_cap_paragraph": "abertura",
            "closing_paragraph": "fecho",
        }
    )

    assert variant.sections[0].heading == "Método"


def test_coercing_model_leaves_plain_strings_alone():
    """A text field holding JSON-looking prose must not be parsed away."""

    class Sample(CoercingModel):
        text: str
        items: list[str]

    sample = Sample(text='{"nao": "json"}', items='["a", "b"]')

    assert sample.text == '{"nao": "json"}'
    assert sample.items == ["a", "b"]
