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
