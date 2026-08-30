from __future__ import annotations

import uuid
from pathlib import Path

import click


@click.group()
def main() -> None:
    """Article-to-site generator: PDF -> guided reading page, blog post,
    audio player, Google Slides preview, remote workshop page, and
    site-wide SEO/GEO/AEO wiring.
    """


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option("--tema", default=None, help="Theme/topic slug. Inferred by an LLM node if omitted.")
@click.option("--slug", default=None, help="Article slug. Derived from the PDF filename if omitted.")
@click.option("--copy-only", is_flag=True, help="Mark this run as a copy of a pre-existing root page.")
@click.option("--copy-canonical-root", default=None, help="Root URL the copy's canonical should point back to.")
@click.option("--skip-content-review", is_flag=True, help="Skip the pre-render human review interrupt.")
def build(
    pdf_path: Path,
    tema: str | None,
    slug: str | None,
    copy_only: bool,
    copy_canonical_root: str | None,
    skip_content_review: bool,
) -> None:
    """Run the full pipeline against PDF_PATH."""
    from pipeline.graph.build_graph import build_graph

    slug = slug or pdf_path.stem.lower().replace("_", "-").replace(" ", "-")
    graph = build_graph(skip_content_review=skip_content_review)

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    initial_state = {
        "pdf_path": pdf_path,
        "slug": slug,
        "tema": tema,
        "copy_only": copy_only,
        "is_copy_of_existing": copy_only,
        "copy_canonical_root": copy_canonical_root,
    }

    result = graph.invoke(initial_state, config=config)

    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        click.echo(f"\n--- paused at {payload['checkpoint']} ---")
        click.echo(payload["instructions"])
        click.echo("Press Enter to accept as-is, or Ctrl+C to abort and edit manually.")
        input()
        result = graph.invoke(None, config=config)

    output_dir = result.get("output_dir")
    click.echo(f"\nDone. Wrote pages to {output_dir}")


@main.command()
@click.option("--slug", required=True)
@click.option("--preview-url", required=True, help="docs.google.com/presentation/d/.../preview URL, after manual sharing")
@click.option("--edit-url", required=True)
def set_slides(slug: str, preview_url: str, edit_url: str) -> None:
    """OPTIONAL override: point this article's deck section at a Google Slides
    file instead of the self-hosted PDF.

    The pipeline does not need this. `pipeline build` downloads the NotebookLM
    deck as both deck.pdf (embedded in the page) and deck.pptx (offered for
    download), so the deck section works with no Google credentials and no
    manual sharing. Use this only when a deck genuinely lives in Google Slides
    and you have already set 'anyone with the link can view' on it.
    """
    from pipeline.manifest.articles_yaml import load_manifest, save_manifest

    entries = load_manifest()
    for e in entries:
        if e.slug == slug:
            e.slides_preview_url = preview_url
            e.slides_edit_url = edit_url
            e.has_slides = True
            break
    else:
        raise click.ClickException(f"No manifest entry for slug={slug!r}")
    save_manifest(entries)
    click.echo(f"Updated slides URLs for {slug}. Re-run `pipeline build` or edit the page's package.json + re-render.")


@main.command()
@click.option("--port", default=8000, show_default=True)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Loopback by default: the server holds API keys and writes to the repo.",
)
def serve(port: int, host: str) -> None:
    """Run the local authoring console.

    Serves the theme galleries and lets you start a pipeline run from the
    browser, streaming each node as it completes. The gallery page served here
    is the same file that gets published; its console reveals itself only under
    localhost.
    """
    import uvicorn

    from pipeline.server.app import app

    click.echo(f"Console em http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
