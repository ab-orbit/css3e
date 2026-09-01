Monte a lista de itens da grade de "downloads/fontes" para a página de leitura guiada do artigo abaixo.

Inclua, nesta ordem, APENAS os itens abaixo que estiverem disponíveis:

1. O PDF do artigo original — href exatamente `{pdf_relative_href}`
2. O post de blog do mesmo artigo — href exatamente `{blog_relative_href}`
3. O áudio comentado, somente se `has_audio` for verdadeiro — href exatamente `{audio_relative_href}`
4. O deck de apresentação, somente se `has_slides` for verdadeiro — href exatamente `{slides_relative_href}`

Regra obrigatória: cada `href` deve ser exatamente uma das strings fornecidas acima. NÃO invente links, NÃO adicione itens que apontem para outras seções do site, e NÃO inclua nada fora da pasta deste artigo. Esta página referencia apenas o próprio conteúdo do artigo; a navegação para o resto do site é feita em outro lugar.

Cada item tem title, description (1 frase, específica sobre o que aquele arquivo contém neste artigo), href e arrow_label (ex: "PDF ↓", "LER →", "ÁUDIO ↓", "DECK ↓").

has_audio: {has_audio}
has_slides: {has_slides}
pdf_relative_href: {pdf_relative_href}
blog_relative_href: {blog_relative_href}
audio_relative_href: {audio_relative_href}
slides_relative_href: {slides_relative_href}

Análise do artigo:
{paper_analysis_json}
