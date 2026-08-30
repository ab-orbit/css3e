# Extração de entidades e relações + JSON-LD por artigo

Status: aprovado 2026-08-29. Implementação em andamento.

## Objetivo

Extrair entidades e relações do texto do paper, emitir um JSON-LD schema.org
por artigo (SEO/GEO), e exibir o grafo resultante na página do artigo. Além
disso, normalizar o nome do PDF recebido segundo as convenções CASRAI.

## Decisões tomadas

**Propósito do JSON-LD: SEO/GEO por artigo.** Sem registro global de entidades,
sem dedup entre papers, sem vinculação a Wikidata. Cada artigo tem seu grafo.
Descartadas: grafo consultável entre artigos (exigiria registro canônico de
entidades e resolução entre papers) e formato livre só para visualização
(descartaria o valor de dado estruturado).

**Motor: GLiNER + GLiREL locais.** Modelos zero-shot rodando em MPS, baixados
em `/Volumes/T9/lm-studio/models`. Escolhidos pela proveniência: devolvem
offsets de caractere, então cada entidade aponta para onde apareceu no texto.
Grátis por run e offline. Descartado: extração via OpenRouter com quote
verificada (sem offsets nativos, custo por run).

**Ressalva de vocabulário:** schema.org não tem mecanismo geral para relações.
`about`/`mentions` cobrem entidades; "CAS integra-se a MAS" não tem propriedade
canônica. As relações vão como estrutura paralela no `@graph` — ignoradas por
buscadores, legíveis por LLMs, e são o que alimenta a view.

## Componentes

### 1. `pipeline/naming.py` — convenções CASRAI

Padrão: `css3e_<descricao>_<YYYYMMDD>_v01.pdf`

Regras aplicadas (de casrai.org/guides/file-naming-and-folder-structure-conventions-for-research-data):
- data ISO 8601 compacta `YYYYMMDD` (ordena como texto)
- separadores `_` e `-`, nunca espaço
- apenas `[a-z0-9_-]`; acentos transliterados, reservados removidos
- caixa única (minúsculas)
- versão de dois dígitos (`v09` antes de `v10`)
- caminho completo abaixo de 255 caracteres
- elemento mais estável primeiro, mais variável por último

O slug permanece separado do nome de arquivo: slug é identidade de URL: misturar
os dois quebraria links a cada nova versão do PDF.

### 2. `pipeline/extraction/entities.py` — extração

- GLiNER + GLiREL de `HF_HOME=/Volumes/T9/lm-studio/models`, device MPS
- rótulos de domínio (Method, Task, Dataset, Metric, System, Concept,
  Organization, Software), configuráveis
- **janela deslizante com remapeamento de offsets para o texto completo** — o
  encoder aceita ~384 tokens contra 121k caracteres de paper; sem o remapeamento
  a proveniência se perde, que é a razão da escolha do motor
- dedup por forma normalizada, ranking por frequência × score
- GLiREL sobre pares co-ocorrentes na mesma janela
- fail-soft: sem torch ou sem modelo, o run segue sem entidades

### 3. `pipeline/render/jsonld.py`

`@graph` com `ScholarlyArticle` (autores, `datePublished`, `identifier` DOI,
`isBasedOn` para o PDF), `about` com as entidades principais como `DefinedTerm`,
`mentions` com o restante, relações em paralelo. Gravado como `<slug>.jsonld` e
embutido inline em `<script type="application/ld+json">` no `index.html`.

### 4. `partials/entities_graph.html.j2`

Layout calculado em Python, SVG estático, JS inline mínimo para hover e filtro
por tipo. Sem biblioteca de grafo — mantém o padrão de zero requisição externa.
Abaixo, tabela de triplas com a frase de apoio, onde a proveniência fica
auditável.

### 5. Dependências

Extra opcional `[entities]` = `gliner`, `glirel`, `torch`. Instalação base
continua leve.

## Risco declarado

GLiREL é o elo fraco. Se as relações vierem ruins no teste real, o fallback é o
híbrido: GLiNER ancora as entidades e o LLM que já está no pipeline infere as
relações entre elas. Decisão tomada com a saída real em mãos, reportada antes
de mudar.

## Ordem de implementação

1. `naming.py` + testes (independente, sem dependências novas)
2. download dos modelos para T9
3. `extraction/entities.py` + testes
4. schemas de entidade
5. nó `gen_entities`, estado, assemble, package
6. `jsonld.py` + testes
7. partial + wiring de render + testes
8. run ponta a ponta real
