# Pipeline: artigo em PDF → páginas do site

Converte um paper em PDF nas três páginas publicáveis do css3e — leitura guiada
(`index.html`), post de blog (`blog.html`) e dinâmica de workshop
(`workshop.html`) — junto com áudio comentado, deck de apresentação e a
regeneração de `sitemap.xml` / `llms.txt` / `robots.txt`.

Orquestrado com LangGraph. Uma passada de extração cara alimenta um fan-out de
nove geradores independentes, e uma branch de mídia corre em paralelo.

```
pipeline build artigo.pdf
```

---

## Índice

- [Como rodar](#como-rodar)
- [Configuração](#configuração)
- [Arquitetura](#arquitetura)
- [Estrutura de diretórios](#estrutura-de-diretórios)
- [Saída de um run](#saída-de-um-run)
- [Decisões de projeto](#decisões-de-projeto)
- [Testes](#testes)
- [Problemas conhecidos](#problemas-conhecidos)

---

## Como rodar

### Instalação

Dependências gerenciadas com [uv](https://docs.astral.sh/uv/); `uv.lock` está
versionado.

```bash
uv venv --python 3.12
uv pip install -e ".[dev,browser]"
```

O extra `browser` traz o Playwright, necessário só para o login interativo do
NotebookLM. Runs desassistidos usam `NOTEBOOKLM_AUTH_JSON` e nunca o carregam.

### Credenciais

```bash
cp .env.example .env    # preencher as chaves
```

O NotebookLM autentica por sessão de browser, não por chave de API. Bootstrap
uma vez:

```bash
.venv/bin/notebooklm login --browser chrome
base64 -i ~/.notebooklm/profiles/default/storage_state.json | tr -d '\n'
# colar o resultado em NOTEBOOKLM_AUTH_JSON no .env
```

`--browser chrome` porque o Chromium empacotado quebra em macOS 15+. **A sessão
expira em algumas semanas** — não é configurar e esquecer.

### Build

```bash
pipeline build caminho/do/artigo.pdf
pipeline build artigo.pdf --slug meu-slug --tema meu-tema
pipeline build artigo.pdf --skip-content-review    # pula o segundo checkpoint
```

O run pausa em `review_extraction` para inspeção humana da `PaperAnalysis`
antes de gastar tokens no fan-out. Enter aceita como está.

### Comando auxiliar

```bash
pipeline set-slides --slug X --preview-url ... --edit-url ...
```

Override **opcional**, para um deck que realmente viva no Google Slides. O
pipeline não precisa dele: o deck é auto-hospedado.

---

## Configuração

Tudo via `.env`, lido por `pydantic-settings` (ver `config.py`).

| Variável | Default | Papel |
|---|---|---|
| `OPENROUTER_API_KEY` | — | **Obrigatória.** Sem ela o fan-out falha. |
| `OPENROUTER_MODEL` | `anthropic/claude-sonnet-4.5` | Modelo principal |
| `OPENROUTER_MODEL_FAST` | `openai/gpt-4o-mini` | Nós de baixo risco |
| `PDF_EXTRACTOR` | `calia` | `calia`, `pdftotext` ou `pypdf` |
| `CALIA_API_KEY` | — | Obrigatória quando `PDF_EXTRACTOR=calia` |
| `CALIA_API_URL` | `https://aeonbridge.io/calia` | Endpoint de conversão |
| `CALIA_TIMEOUT_SECONDS` | `180` | Default do httpx (5s) é curto demais |
| `NOTEBOOKLM_AUTH_JSON` | — | base64 do `storage_state.json` |
| `SITE_BASE_URL` | `https://ab-orbit.github.io/css3e/` | Base de canonical e sitemap |
| `LANGCHAIN_TRACING_V2` | `false` | Liga o tracing no LangSmith |
| `LANGCHAIN_PROJECT` | `css3e-pipeline` | Projeto de destino dos traces |

Áudio e slides são **fail-soft**: sem credencial de NotebookLM o run continua
sem mídia. A chave da OpenRouter não é — sem ela, `make_chat_model` levanta erro.

### Sobre o tracing

`configure_tracing()` copia as variáveis do `Settings` para `os.environ`, e é
chamada pelo `build_graph()`. Necessário porque o `pydantic-settings` lê o
`.env` para dentro do objeto sem exportar nada para o ambiente do processo,
enquanto o LangChain lê `os.environ` direto. Uma chave já exportada na shell
tem precedência sobre a do `.env`.

---

## Arquitetura

```
ingest_pdf ──> analyze_paper ──> [review_extraction] ──> infer_theme
                                                              │
                    ┌─────────────────────────────────────────┤
                    │                                         │
              fan-out (9 nós, paralelo)              branch de mídia
                    │                                         │
     gen_hero ──────┤                              generate_audio
     gen_categories ┤                                    │
     gen_mindmap ───┤                              generate_slides
     gen_tables ────┤                                    │
     gen_essay_×2 ──┤                                    │
     gen_workshop ──┤                                    │
     gen_seo ───────┤                                    │
     gen_downloads ─┤                                    │
                    └──────────────> assemble <──────────┘
                                        │
                                 [review_content]
                                        │
                                  render_html
                                        │
                                     publish
```

**Por que esse formato.** `analyze_paper` é a única leitura do texto integral
do paper. Todo nó do fan-out lê apenas a `PaperAnalysis` resultante, nunca o
`paper_text` de novo — uma passada cara, nove baratas. É também por isso que
`review_extraction` é o checkpoint de maior alavancagem do grafo: qualquer erro
na `PaperAnalysis` é herdado por todos os nove artefatos.

A branch de mídia depende só do PDF, então roda em paralelo com o fan-out. Ela
domina o tempo de parede: num run real de 25 min, áudio (696s) e deck (664s)
foram 89% do total; os nove nós de LLM somaram 171s.

### Módulos

| Módulo | Responsabilidade |
|---|---|
| `extraction/` | PDF → texto. Três backends, um contrato |
| `llm/` | Cliente OpenRouter + os 10 prompts, em `.md` separados |
| `schemas/` | `PaperAnalysis` (extração) e `ArticlePackage` (fan-in) |
| `graph/` | Grafo LangGraph, estado e os 18 nós |
| `render/` | 15 templates Jinja2 → 3 páginas HTML |
| `manifest/` | `articles.yaml` como fonte da verdade; sitemap/llms/robots derivados |
| `media/` | Wrapper do NotebookLM (áudio + deck) |

### Fronteira de estado

`graph/state.py` define um `TypedDict` onde cada nó do fan-out escreve **um**
campo. `assemble` lê todos de volta num `ArticlePackage`. Campos opcionais
começam como `None`, então a ordem dos nós não importa e nós que falharam
(mídia sem credencial) não quebram o grafo.

---

## Estrutura de diretórios

```
pipeline/
├── cli.py                  # comandos build e set-slides
├── config.py               # Settings + configure_tracing
├── articles.yaml           # manifest — fonte da verdade do site
├── extraction/pdf.py       # calia | pdftotext | pypdf
├── llm/
│   ├── client.py           # OpenRouter + render_prompt
│   └── prompts/*.md        # 10 prompts, versionados como texto
├── schemas/
│   ├── paper.py            # PaperAnalysis
│   ├── components.py       # Hero, Categorias, Tabelas, Ensaio, Workshop…
│   └── package.py          # ArticlePackage, ManifestEntry
├── graph/
│   ├── build_graph.py      # topologia e interrupts
│   ├── state.py            # PipelineState
│   └── nodes/*.py          # 18 nós
├── render/
│   ├── build.py            # orquestra o Jinja2
│   └── templates/          # 3 páginas + 12 partials
├── manifest/
│   ├── articles_yaml.py    # load/save/upsert
│   ├── sitemap.py          # regenerado por inteiro, nunca remendado
│   ├── llms_txt.py
│   └── robots.py
└── media/notebooklm_client.py
```

---

## Saída de um run

```
articles/<tema>/<slug>/
├── index.html              # leitura guiada
├── blog.html               # post
├── workshop.html           # dinâmica
├── package.json            # ArticlePackage serializado
├── <slug>.pdf              # cópia do paper de origem
├── audio/<slug>.m4a        # Audio Overview
└── slides/
    ├── deck.pdf            # embutido na página
    └── deck.pptx           # download editável
```

Mais, na raiz: `pipeline/articles.yaml` recebe upsert, e `sitemap.xml`,
`llms.txt` e `robots.txt` são regenerados a partir dele.

`package.json` é o output completo do LLM para aquele artigo. Uma mudança de
template pode ser re-renderizada a partir dele, sem repagar o fan-out.

---

## Decisões de projeto

**Prompts substituídos à mão, não com `str.format`.** Os prompts são prosa em
português que usa chaves como notação (`lista de atributos {label, texto}`).
`str.format` lê isso como placeholder e morre com `KeyError`. `render_prompt()`
troca apenas os nomes declarados e levanta erro se uma variável passada não
tiver placeholder — input silenciosamente descartado produziria um prompt
sutilmente errado.

**`method="function_calling"` explícito.** Deixado no default, o
`langchain-openai` negocia o caminho nativo de structured outputs da OpenAI
(`response_format` + json_schema estrito), que a OpenRouter não impõe de forma
uniforme entre provedores: o modelo responde em Markdown e o parser estrito
morre. Tool-calling é suportado por toda família de modelo que este projeto usa.

**Deck auto-hospedado, sem Google Drive.** Navegador não renderiza `.pptx`
inline, então o mesmo artifact do NotebookLM é baixado duas vezes numa única
geração: PPTX para download, PDF para o `<iframe>`. Sem credencial, sem
compartilhamento manual, sem requisição externa. `slides_preview_url` continua
disponível como override para um deck que de fato viva no Google Slides.

**PDF copiado para a pasta do artigo.** Linkar o caminho local de onde o
operador guardou o arquivo gera um link que só funciona naquela máquina.

**Auth do NotebookLM em arquivo temporário 0600.** O `NOTEBOOKLM_AUTH_JSON` é
materializado num temp file removido no `finally`, nunca sobre o
`storage_state.json` do perfil real do desenvolvedor.

**Download em dois tempos.** Toda mídia baixa para um `.partial` ao lado do
destino e só então é renomeada. O staging precisa dividir filesystem com o
destino: `Path.replace` não cruza dispositivos, e no macOS o temp do sistema é
outro volume.

**Sinais de injeção são logados, não bloqueiam.** A Calia devolve uma varredura
heurística de prompt injection junto do texto. Como o `cleaned_text` entra
verbatim em todo prompt, risco `medium`/`high` gera aviso nomeando as regras —
mas não falha o build, porque paper acadêmico dispara as regras fracas com
frequência (títulos de referência em imperativo, por exemplo).

**Manifest regenera, nunca remenda.** `sitemap.xml` e `llms.txt` são reescritos
inteiros a partir do `articles.yaml` a cada publish. As entradas de raiz vêm de
uma lista fixa, e o publish nunca toca arquivos da raiz.

---

## Testes

```bash
.venv/bin/python -m pytest -q     # 64 testes
```

| Arquivo | Cobre |
|---|---|
| `test_extraction.py` | Backend Calia: formato do request, tratamento de erro, sinais de injeção |
| `test_notebooklm_client.py` | Ordem das chamadas, mapeamento de erro, staging atômico do PPTX |
| `test_prompt_rendering.py` | Substituição de placeholder; chaves em prosa preservadas |
| `test_render.py` | As três páginas; precedência do embed do deck |
| `test_css_integrity.py` | Todo `var(--x)` usado precisa estar declarado |
| `test_manifest_upsert.py` | Upsert, `package.json`, cópia do PDF, idempotência |
| `test_tracing_config.py` | Ponte de env do LangSmith |
| `test_schemas.py` | Validação dos modelos Pydantic |

`test_css_integrity.py` existe por um motivo concreto: uma custom property
indefinida invalida a declaração inteira **em silêncio**. Um
`padding: 46px var(--gut)` com `--gut` inexistente rendeu `padding: 0`, e nada
no pipeline percebeu — navegador descarta regra inválida sem erro algum.

---

## Problemas conhecidos

**`analyze_paper` devolve `categories: []` em surveys.** O nó `gen_categories`
então retorna zero cards, obedecendo seu próprio prompt ("se vazia, retorne
vazia — não invente"), e a seção de categorias some da página. Num run real
sobre um survey de CA-MAS, o `gen_tables` capturou as mesmas taxonomias como
tabelas, então a informação está no texto — o prompt de análise é que pede a
taxonomia numa subordinada longa entre dez outros pedidos.

**`assemble` / `render_html` / `publish` executam duas vezes.** O fan-out
ocupa um superstep e a branch de mídia (`audio` → `slides`) ocupa dois, então
`assemble` dispara em cada um. A primeira passada publica uma página **sem os
slides**, sobrescrita em seguida pela correta. O resultado final é certo, mas o
docstring do grafo afirma que `assemble` espera as duas branches — o LangGraph
não faz isso. Precisa de uma barreira de join de verdade.

**Sessão do NotebookLM expira.** Algumas semanas, e o `NOTEBOOKLM_AUTH_JSON`
precisa ser regerado à mão. A API por trás é revertida e não documentada; o
próprio notebooklm-py avisa que serve a protótipos, não a produção crítica.

**Custo e tempo.** Um run completo levou 25 min e ~13 chamadas de LLM sobre um
paper de 121k caracteres. A mídia domina; `--skip-content-review` não ajuda
nisso.
