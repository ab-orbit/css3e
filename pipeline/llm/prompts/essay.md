Escreva um ensaio em português (pt-BR), tom de divulgação técnica acessível (o tipo de texto que abre com uma cena concreta e cotidiana antes de introduzir o conceito técnico), baseado na análise do artigo abaixo.

Variante solicitada: **{variant}**.
- Se "condensed": versão curta (~40% do tamanho da versão completa), 3-4 seções, para ser embutida como um resumo dentro de uma página de leitura guiada maior que já tem outras seções (hero, categorias, tabelas). Evite repetir informação que já apareceria nessas outras seções — foque em costurar a narrativa entre elas.
- Se "full": versão completa e autônoma, pensada para ser o corpo inteiro de um post de blog independente — todas as seções do artigo desenvolvidas, com um parágrafo de abertura que estabelece uma cena/analogia concreta, e um fechamento que devolve a `closing_question` da análise ao leitor.

Cada seção tem: número (`no`), `heading`, uma lista de `paragraphs`, opcionalmente `bullets` quando o conteúdo é naturalmente uma lista, opcionalmente UMA `pullquote` (frase de efeito extraída ou sintetizada do conteúdo da seção, com `cite` indicando a origem, ex: "Aprendizado 1 · SMCAS"), e uma lista de `terms` (2-5 palavras/expressões técnicas centrais da seção, para destaque visual — devem aparecer literalmente dentro do texto de algum parágrafo).

Produza também `drop_cap_paragraph` (o parágrafo de abertura, antes da primeira seção numerada — vai receber uma letra capitular estilizada) e `closing_paragraph` (o fechamento, que antecede o callout com a `closing_question`).

Análise do artigo:
{paper_analysis_json}
