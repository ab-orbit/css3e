"""schema.org JSON-LD for one article.

Consumers are search engines and LLM answer engines. Both read the graph and
both fail silently on a malformed one, so the shape is asserted in tests rather
than eyeballed in a validator.

Vocabulary note: schema.org has no general mechanism for arbitrary relations.
`about` and `mentions` carry the entities; a statement like "CAS integrates
with MAS" has no canonical property. Relations therefore travel in a
namespaced `css3e:relations` key — ignored by search engines, readable by an
LLM parsing the page, and the source the on-page graph view renders from.
"""

from __future__ import annotations

import json

from pipeline.schemas.entities import EntityGraph
from pipeline.schemas.package import ArticlePackage

# How many entities are promoted from `mentions` to `about`. `about` claims the
# article is *primarily* about a term, so it stays a short list.
PRIMARY_TOPIC_COUNT = 8


def build_jsonld(
    pkg: ArticlePackage,
    graph: EntityGraph,
    *,
    site_base_url: str,
    page_path: str,
) -> dict:
    """Assemble the @graph document for `pkg`."""
    base = site_base_url.rstrip("/") + "/"
    page_url = base + page_path.lstrip("/")

    primary = graph.top_entities(PRIMARY_TOPIC_COUNT)
    primary_keys = {e.key for e in primary}
    # An entity in both `about` and `mentions` would make the graph
    # self-contradictory about what the article is primarily about.
    secondary = [e for e in graph.entities if e.key not in primary_keys]

    article: dict = {
        "@type": "ScholarlyArticle",
        "@id": page_url,
        "url": page_url,
        "name": pkg.paper.title,
        "headline": pkg.hero.h1,
        "inLanguage": "pt-BR",
        "author": [{"@type": "Person", "name": a.name} for a in pkg.paper.authors],
    }

    if pkg.paper.abstract:
        article["abstract"] = pkg.paper.abstract
    if pkg.hero.lede:
        article["description"] = pkg.hero.lede
    if pkg.paper.date_published:
        article["datePublished"] = pkg.paper.date_published
    if pkg.paper.venue:
        article["publication"] = pkg.paper.venue
    if pkg.paper.keywords:
        article["keywords"] = list(pkg.paper.keywords)
    if pkg.paper.doi:
        article["identifier"] = {
            "@type": "PropertyValue",
            "propertyID": "DOI",
            "value": pkg.paper.doi,
        }
        article["sameAs"] = f"https://doi.org/{pkg.paper.doi}"

    if primary:
        article["about"] = [_defined_term(e) for e in primary]
    if secondary:
        article["mentions"] = [_defined_term(e) for e in secondary]

    document: dict = {
        "@context": "https://schema.org",
        "@graph": [article],
        "css3e:relations": _relations(graph),
    }
    if graph.engine:
        # Reproducibility: the page can say which models produced its graph.
        document["css3e:extractedBy"] = graph.engine
    return document


def _defined_term(entity) -> dict:
    """One entity as a DefinedTerm, carrying its own provenance counts."""
    return {
        "@type": "DefinedTerm",
        "name": entity.name,
        "termCode": entity.key,
        "inDefinedTermSet": entity.label,
        "css3e:mentionCount": entity.frequency,
        "css3e:confidence": round(entity.score, 3),
    }


def _relations(graph: EntityGraph) -> list[dict]:
    """Relations with both endpoints resolved to display names.

    `connected_relations()` drops edges orphaned by entity capping — rendering
    one would put an unlabelled node on the page.
    """
    resolved = []
    for relation in graph.connected_relations():
        source = graph.entity_by_key(relation.source_key)
        target = graph.entity_by_key(relation.target_key)
        resolved.append(
            {
                "source": source.name,
                "sourceCode": relation.source_key,
                "label": relation.label,
                "target": target.name,
                "targetCode": relation.target_key,
                "confidence": round(relation.score, 3),
                "quote": relation.quote,
                "quoteOffset": relation.quote_start,
            }
        )
    return resolved


def render_jsonld_script(document: dict) -> str:
    """Serialize into an inline <script type="application/ld+json"> block.

    `</` is escaped because an entity name containing "</script>" would
    otherwise close the block early and inject the rest as markup — the text
    comes from a PDF, so it is untrusted input.
    """
    payload = json.dumps(document, ensure_ascii=False, indent=2)
    payload = payload.replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{payload}\n</script>'
