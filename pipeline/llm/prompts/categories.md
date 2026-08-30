Transforme a lista `categories` da análise do artigo abaixo em cartões prontos para renderização web. Para cada categoria, atribua um `accent_index` sequencial começando em 0 (0, 1, 2, ...) na mesma ordem em que aparecem — isso mapeia para uma variável CSS `--accent-N`, não uma classe nomeada, então funciona para qualquer quantidade de categorias. Preserve tag, name, subtitle e converta os atributos em `dl_items` (pares dt/dd), mantendo a ordem e reescrevendo os `dt` como rótulos curtos em maiúscula-de-seção (ex: "DIREÇÃO", "MECANISMO", "EXEMPLO") se ainda não estiverem nesse formato.

Se `categories` estiver vazia na análise, retorne uma lista vazia — não invente categorias que o artigo não propõe.

Análise do artigo:
{paper_analysis_json}
