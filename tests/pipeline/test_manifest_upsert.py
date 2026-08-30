from pipeline.manifest.articles_yaml import load_manifest, save_manifest, upsert
from pipeline.manifest.llms_txt import render_llms_txt
from pipeline.manifest.sitemap import build_sitemap_entries, render_sitemap_xml
from pipeline.schemas.package import ManifestEntry


def _entry(slug: str, tema: str = "teste") -> ManifestEntry:
    return ManifestEntry(
        slug=slug,
        tema=tema,
        title=f"Title {slug}",
        pdf_source="x.pdf",
        authors=["Jane Doe"],
        date_published="2026",
        pages={"article": f"articles/{tema}/{slug}/index.html"},
        status="published",
    )


def test_upsert_is_idempotent(tmp_path):
    path = tmp_path / "articles.yaml"
    save_manifest([], path)

    entries = upsert(_entry("a"), path)
    assert len(entries) == 1

    entries = upsert(_entry("a"), path)  # re-run same slug
    assert len(entries) == 1

    entries = upsert(_entry("b"), path)
    assert len(entries) == 2
    assert {e.slug for e in entries} == {"a", "b"}

    reloaded = load_manifest(path)
    assert {e.slug for e in reloaded} == {"a", "b"}


def test_sitemap_includes_root_entries_and_manifest_entries():
    entries = build_sitemap_entries([_entry("a")], base_url="https://example.test/")
    xml = render_sitemap_xml(entries)

    assert "<loc>https://example.test/artigo.html</loc>" in xml
    assert "<loc>https://example.test/articles/teste/a/index.html</loc>" in xml


def test_sitemap_excludes_entries_marked_include_false():
    e = _entry("a")
    e.include_in_sitemap = False
    entries = build_sitemap_entries([e], base_url="https://example.test/")
    xml = render_sitemap_xml(entries)
    assert "articles/teste/a" not in xml


def test_llms_txt_includes_generated_section_only_when_manifest_nonempty():
    empty = render_llms_txt([], base_url="https://example.test/")
    assert "## Generated articles" not in empty

    with_entry = render_llms_txt([_entry("a")], base_url="https://example.test/")
    assert "## Generated articles" in with_entry
    assert "articles/teste/a/index.html" in with_entry
    # Header/footer content is preserved verbatim.
    assert "## Core pages" in with_entry
    assert "## Optional" in with_entry


def test_publish_writes_package_json(tmp_path, monkeypatch):
    """ArticlePackage must be persisted next to the pages: without it a
    template tweak means re-running the whole LLM fan-out to re-render.
    """
    import json

    import pipeline.config as config
    import pipeline.graph.nodes.publish as publish_mod
    from pipeline.schemas.package import ArticlePackage
    from tests.pipeline.fixtures.sample_package import make_sample_package

    pkg = make_sample_package()
    articles_dir = tmp_path / "articles"
    manifest_path = tmp_path / "articles.yaml"

    monkeypatch.setattr(publish_mod, "ARTICLES_DIR", articles_dir)
    monkeypatch.setattr(config, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(publish_mod, "upsert", lambda entry: [entry])
    monkeypatch.setattr(publish_mod, "regenerate_sitemap", lambda m: None)
    monkeypatch.setattr(publish_mod, "regenerate_llms_txt", lambda m, url: None)
    monkeypatch.setattr(publish_mod, "verify_sitemap_reference", lambda url: None)

    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF-1.4")

    state = {
        "tema": pkg.tema,
        "slug": pkg.slug,
        "pdf_path": source_pdf,
        "package": pkg,
        "rendered_pages": {"index.html": "<html></html>"},
    }
    result = publish_mod.update_manifest_and_publish(state)

    written = result["output_dir"] / "package.json"
    assert written.exists()
    restored = ArticlePackage.model_validate(json.loads(written.read_text()))
    assert restored.slug == pkg.slug
    assert restored.hero.h1 == pkg.hero.h1
    assert len(restored.tables) == len(pkg.tables)


def _publish_state(tmp_path, monkeypatch, pdf_path):
    """Wire publish() to a temp articles dir with the manifest side effects stubbed."""
    import pipeline.graph.nodes.publish as publish_mod
    from tests.pipeline.fixtures.sample_package import make_sample_package

    pkg = make_sample_package()
    monkeypatch.setattr(publish_mod, "ARTICLES_DIR", tmp_path / "articles")
    captured: dict = {}
    monkeypatch.setattr(
        publish_mod, "upsert", lambda entry: captured.setdefault("entry", entry) and [entry]
    )
    monkeypatch.setattr(publish_mod, "regenerate_sitemap", lambda m: None)
    monkeypatch.setattr(publish_mod, "regenerate_llms_txt", lambda m, url: None)
    monkeypatch.setattr(publish_mod, "verify_sitemap_reference", lambda url: None)

    state = {
        "tema": pkg.tema,
        "slug": pkg.slug,
        "pdf_path": pdf_path,
        "package": pkg,
        "rendered_pages": {"index.html": "<html></html>"},
    }
    return publish_mod, pkg, state, captured


def test_publish_copies_source_pdf_into_article_folder(tmp_path, monkeypatch):
    """The published site must serve its own copy of the paper. Linking at the
    operator's local path (e.g. ~/Downloads/paper.pdf) yields a download link
    that 404s for every visitor.
    """
    source = tmp_path / "elsewhere" / "Context_AwareMAS.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"%PDF-1.4 source")

    publish_mod, pkg, state, _ = _publish_state(tmp_path, monkeypatch, source)
    result = publish_mod.update_manifest_and_publish(state)

    copied = result["output_dir"] / f"{pkg.slug}.pdf"
    assert copied.exists()
    assert copied.read_bytes() == b"%PDF-1.4 source"


def test_publish_records_repo_relative_pdf_source(tmp_path, monkeypatch):
    """pdf_source in the manifest must be a repo-relative path, not an absolute
    one from the machine that happened to run the build.
    """
    source = tmp_path / "elsewhere" / "paper.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"%PDF")

    publish_mod, pkg, state, captured = _publish_state(tmp_path, monkeypatch, source)
    publish_mod.update_manifest_and_publish(state)

    pdf_source = captured["entry"].pdf_source
    assert pdf_source == f"articles/{pkg.tema}/{pkg.slug}/{pkg.slug}.pdf"
    assert not pdf_source.startswith("/")


def test_publish_is_idempotent_when_pdf_already_in_place(tmp_path, monkeypatch):
    """Re-publishing must not copy a file onto itself (shutil.copyfile raises
    SameFileError), which would break every re-render of a published article.
    """
    import pipeline.graph.nodes.publish as publish_mod
    from tests.pipeline.fixtures.sample_package import make_sample_package

    pkg = make_sample_package()
    articles = tmp_path / "articles"
    target_dir = articles / pkg.tema / pkg.slug
    target_dir.mkdir(parents=True)
    in_place = target_dir / f"{pkg.slug}.pdf"
    in_place.write_bytes(b"%PDF already here")

    publish_mod, _pkg, state, _ = _publish_state(tmp_path, monkeypatch, in_place)
    publish_mod.update_manifest_and_publish(state)

    assert in_place.read_bytes() == b"%PDF already here"


def test_republishing_does_not_duplicate_the_archival_pdf(tmp_path, monkeypatch):
    """Version numbers mean new content, not the same file written twice.

    publish currently runs twice per graph execution (the fan-out and the media
    branch land in different supersteps), which produced an identical v01 and
    v02 of a 1.5MB PDF on a real run.
    """
    source = tmp_path / "src" / "paper.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"%PDF-1.4 identical bytes")

    publish_mod, pkg, state, _ = _publish_state(tmp_path, monkeypatch, source)

    result = publish_mod.update_manifest_and_publish(state)
    publish_mod.update_manifest_and_publish(state)

    archival = sorted(result["output_dir"].glob("css3e_*.pdf"))
    assert len(archival) == 1, [p.name for p in archival]
    assert "_v01." in archival[0].name


def test_a_genuinely_different_pdf_gets_a_new_version(tmp_path, monkeypatch):
    """The version element still has to work for an actual revision."""
    source = tmp_path / "src" / "paper.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"%PDF original")

    publish_mod, pkg, state, _ = _publish_state(tmp_path, monkeypatch, source)
    result = publish_mod.update_manifest_and_publish(state)

    source.write_bytes(b"%PDF revised, materially different content")
    publish_mod.update_manifest_and_publish(state)

    archival = sorted(p.name for p in result["output_dir"].glob("css3e_*.pdf"))
    assert len(archival) == 2
    assert "_v01." in archival[0] and "_v02." in archival[1]
