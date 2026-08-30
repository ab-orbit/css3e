Gere os metadados de SEO/GEO/AEO para UMA página do site, no mesmo padrão já usado nas páginas existentes (description até ~300 caracteres cobrindo o argumento central da página; keywords misturando termos em português e os termos técnicos em inglês do artigo, tipo "context-aware systems", os nomes das categorias, e termos de domínio do curso; jsonld_type escolhido conforme `page_kind`: "article"→Article, "blog"→BlogPosting, "workshop"→LearningResource, "landing"→WebSite; og_type "article" para article/blog/workshop, "website" para landing).

`canonical_url` deve ser `{site_base_url}` concatenado com `{relative_path}` (sem barra dupla). `about` é a lista de 4-6 conceitos-chave do artigo (mesma lista usada no mapa mental/hero, reaproveite `key_concepts` da análise). `article_tags` só é relevante para page_kind article/blog — use os nomes das categorias do artigo.

page_kind: {page_kind}
relative_path: {relative_path}
site_base_url: {site_base_url}
authors (lista, já formatada): {authors}
published_date: {published_date}

Análise do artigo:
{paper_analysis_json}
