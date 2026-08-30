"""Article-to-site generator pipeline.

Given a source article PDF, reproduces the full set of hand-built deliverables
that were created for resources/ThreeCategoriesofCAS.pdf: a guided reading
page, a blog post, an audio player wired to a generated podcast-style audio
overview, a Google Slides preview, a facilitator+participant remote workshop
page, and the site-wide SEO/GEO/AEO wiring (meta tags, sitemap, llms.txt).

See pipeline/graph/build_graph.py for the orchestration entrypoint and
/Users/jwcunha/.claude/plans/agora-analisando-tudo-que-purrfect-salamander.md
for the full design rationale.
"""
