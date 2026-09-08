# ab.rp.kids — extração dos serviços da PoC css3e

**Data:** 2026-09-08
**Status:** design aprovado, aguardando plano de implementação
**Escopo:** módulo KIDS (Knowledge Ingest, Digest and Sharing) da Aeon Bridge
Research Platform

---

## 1. Contexto

O repositório `css3e` contém uma prova de conceito funcionando: um pipeline que
converte um paper em PDF em um conjunto de artefatos publicáveis — páginas de
leitura, post, dinâmica de workshop, grafo de entidades, áudio comentado, áudio
em formato de aula e deck de apresentação. São 4.992 linhas de Python, 22 nós
de grafo LangGraph, 6 endpoints HTTP e 293 testes.

A PoC validou o que importa:

- **Uma extração cara alimenta muitos geradores baratos.** `PaperAnalysis` é
  produzida uma vez e serve os oito geradores de conteúdo.
- **O pacote é a fonte única.** Persistir `ArticlePackage` permitiu regerar um
  artefato isolado sem repetir 25 minutos de pipeline.
- **Prompt editável vale mais que prompt perfeito.** A regeneração com prompt
  aberto no console mudou a qualidade dos áudios em minutos, não em dias.
- **Todo serviço externo falha de um jeito que o cliente não previu.** Tool-call
  devolvendo JSON como string, geração de áudio que termina depois do timeout,
  notebook duplicado por artefato. Cada um custou uma execução inteira.

Este documento especifica a extração desses serviços para `ab.rp.backend.kids`,
projetado para ser consumido por `ab.rp.frontend.kids` e pelos demais módulos da
plataforma (definição de pergunta de pesquisa, refinamento de escopo, busca de
eventos e revistas).

### O que a PoC não é

Um único usuário, um único repositório, arquivos YAML como manifesto, estado em
memória do processo, saída acoplada a um site estático específico. Nada disso
sobrevive à extração.

---

## 2. Decisões

| Decisão | Escolha | Por quê |
|---|---|---|
| Runtime | FastAPI + LangGraph Platform + Postgres | O grafo já existe; o runtime gerenciado entrega checkpoint, retomada e human-in-the-loop sem reimplementá-los |
| Saída | API + storage; front consome JSON | Desacopla o conteúdo do design system, que ainda não existe |
| Autenticação | Fora do escopo desta fase | Serviço interno; auth virá de outro módulo da plataforma |
| Repositórios | Monorepo `ab.rp` | Contrato e módulos evoluem juntos |
| Observabilidade | Langfuse | Traço por execução, custo por nó, avaliação de prompt versionado |

---

## 3. Domínio

O vocabulário da PoC é específico demais para a plataforma. A tradução:

| PoC | Plataforma | Notas |
|---|---|---|
| tema (pasta) | `Collection` | Agrupa papers de um recorte de pesquisa; é a unidade do notebook no NotebookLM |
| slug (pasta) | `Paper` | PDF + metadados extraídos |
| `package.json` | `Digest` | Versionado: cada execução cria uma versão, nunca sobrescreve |
| áudio/deck/página | `Artifact` | Tipado, com proveniência |
| execução no console | `Run` + `RunEvent` | Persistidos, não em memória |
| arquivo `.md` de prompt | `PromptVersion` | Versão imutável; a edição cria uma nova |

### Modelo relacional

```
collection(id, slug, name, description, created_at)
paper(id, collection_id, slug, title, doi, authors jsonb, published_at,
      source_uri, checksum, page_count, created_at)
digest(id, paper_id, version, content jsonb, prompt_versions jsonb,
       created_at)                       -- content = ArticlePackage
artifact(id, paper_id, kind, storage_uri, bytes, mime, digest_version,
         prompt_version_id, source_hash, provider_ref jsonb, created_at)
run(id, paper_id, kind, status, phase, requested_by, params jsonb,
    started_at, finished_at, error)
run_event(id, run_id, seq, name, data jsonb, created_at)
prompt(name, version, body, created_at, created_by)  -- PK (name, version)
```

`artifact.kind` ∈ `audio_overview`, `audio_lecture`, `slide_deck`, `mind_map`,
`page_article`, `page_blog`, `page_workshop`, `jsonld`, `export_bundle`.

`artifact.provider_ref` guarda o que o provedor devolveu (id do notebook, id do
artefato, task id) — é o que torna possível recuperar uma geração que terminou
depois do cliente desistir.

`artifact.source_hash` é o hash das fontes que entraram na geração. Junto com
`prompt_version_id` e `digest_version`, forma a chave de idempotência: pedir o
mesmo artefato com as mesmas entradas devolve o existente em vez de gastar cota.

### Storage

Postgres não guarda binário. PDFs e mídia vão para S3/MinIO sob
`collections/{collection}/papers/{paper}/{kind}/{artifact_id}.{ext}`; o banco
guarda URI, tamanho, mime e checksum. O download passa por URL assinada de vida
curta — o backend nunca faz proxy de 50 MB de áudio.

---

## 4. Serviços

Cada serviço é um pacote Python com fronteira explícita, testável sem rede.

### 4.1 `ingestion`

Origem: `pipeline/extraction/pdf.py`.
PDF → texto + metadados. Três adapters atrás de uma interface (`calia`,
`pdftotext`, `pypdf`), escolhidos por configuração. Guarda `checksum` e
`page_count` no `Paper`; um PDF já ingerido com o mesmo checksum não é
reprocessado.

### 4.2 `analysis`

Origem: `pipeline/graph/nodes/analyze.py`, `pipeline/schemas/paper.py`.
Produz `PaperAnalysis` por tool-calling estruturado. É o ponto de maior alavanca
e o único checkpoint humano obrigatório do grafo: todo artefato herda os erros
daqui.

### 4.3 `synthesis`

Origem: os oito nós de fan-out.
Hero, categorias, mindmap interativo, tabelas, ensaio (condensado e completo),
workshop, SEO e downloads. Todos os schemas herdam de `CoercingModel` — a
coerção de campo JSON-string é requisito, não detalhe: dois provedores já
devolveram listas e objetos serializados como texto.

### 4.4 `knowledge`

Origem: `pipeline/extraction/entities.py`, `relations.py`.
Entidades via GLiNER e relações via GLiREL, com validação por citação: uma
relação só sobrevive se a citação existe no texto-fonte e menciona as duas
pontas. Na PoC essa validação descartou ~40% das relações propostas — é a
diferença entre um grafo confiável e um grafo plausível.

Roda em processo separado do web: o modelo ocupa memória e leva dezenas de
segundos.

### 4.5 `media`

Origem: `pipeline/media/notebooklm_client.py`.
Adaptador do NotebookLM. Regras validadas na PoC, que a extração preserva:

- **Um notebook por `Collection`**, não por paper nem por artefato. Cada paper
  entra como fonte, nomeada pelo slug; toda geração seleciona todas as fontes,
  de modo que um artefato posiciona o paper entre seus vizinhos.
- **Esperar a fila do notebook.** O provedor gera um áudio por vez; enfileirar
  atrás de um job travado é como se perde uma geração.
- **Recuperar do timeout.** Ao estourar o tempo, procurar um artefato que ficou
  pronto depois do início da execução e baixá-lo. Nunca reaproveitar artefato
  anterior ao início — pertence a outro paper.
- **pt-BR explícito**, no parâmetro de idioma e nas instruções.

Artefatos suportados: `audio_overview`, `audio_lecture`, `slide_deck` e — novo
nesta extração — `mind_map` (§6).

### 4.6 `packaging`

Origem: `pipeline/graph/nodes/assemble.py`, `schemas/package.py`.
Monta o `Digest` e grava uma nova versão. Versão imutável: regerar um artefato
cria versão nova, o que dá histórico e permite comparar duas gerações do mesmo
paper.

### 4.7 `export`

Origem: `pipeline/render/*` e `pipeline/manifest/*`.
Deixa de ser o caminho principal e passa a ser um serviço sob demanda: gera um
bundle estático (páginas, JSON-LD, sitemap, `llms.txt`) a partir de um `Digest`.
Serve arquivamento e publicação; o front normal consome JSON.

### 4.8 `prompts`

Origem: `pipeline/llm/prompt_store.py`.
Registry versionado em banco, com os arquivos `.md` atuais como seed. Toda
execução registra qual versão de prompt usou — sem isso, comparar duas gerações
é adivinhação. A API permite editar para uma execução (efêmero) ou publicar uma
nova versão.

---

## 5. Sessão do NotebookLM

O NotebookLM não tem API oficial nem chave: autentica por sessão de browser
(`storage_state.json` do Playwright), que expira em semanas. Na PoC isso vivia
em uma variável de ambiente em base64 — e a expiração aparecia como uma falha
opaca no meio de uma execução de 25 minutos.

Vira funcionalidade de primeira classe:

```
notebooklm_session(id, label, storage_state_encrypted, account_email,
                   status, last_checked_at, expires_hint, created_at)
```

- `POST /v1/integrations/notebooklm/session` — recebe o `storage_state.json`
  (upload ou base64), valida imediatamente fazendo uma chamada real de listagem,
  e só persiste se a validação passar. O segredo é cifrado em repouso e nunca
  volta em nenhuma resposta.
- `GET /v1/integrations/notebooklm/session` — estado: `valid`, `expiring`,
  `invalid`, quando foi checada, qual conta, quantos notebooks enxerga.
- `POST /v1/integrations/notebooklm/session/check` — revalida sob demanda.
- Verificação periódica em background; ao detectar expiração, marca `invalid`,
  emite evento e **rejeita antecipadamente** runs de mídia com uma mensagem
  acionável, em vez de deixá-las falhar no meio.
- Runs de mídia enfileirados quando a sessão está inválida ficam em `blocked`, e
  são retomados quando uma sessão válida entra — não são perdidos.

O front expõe isso como uma tela de integração: colar a sessão, ver o estado,
renovar. O `notebooklm login --browser chrome` continua sendo o modo de obter o
arquivo; a plataforma cuida do resto.

---

## 6. Mind map via NotebookLM

Hoje o mindmap é gerado por LLM (`MindMapSpec`) e renderizado em SVG próprio.
Passa a haver duas origens, e elas não competem:

- **`mind_map` (NotebookLM)** — novo artefato. `artifacts.generate_mind_map`
  produz o mapa a partir de todas as fontes da coleção; `mind_maps.get_tree`
  devolve a árvore estruturada e `download_mind_map` o arquivo. Persistimos os
  dois: a árvore em `artifact.provider_ref`/`content` (consultável, comparável) e
  o arquivo no storage.
- **`MindMapSpec` (LLM)** — segue existindo no `Digest`, porque é o que alimenta
  o SVG interativo com paleta e legenda derivadas.

A árvore do NotebookLM é normalizável para `MindMapSpec`, o que abre um terceiro
caminho — mapa do provedor renderizado com a identidade visual da plataforma.
A normalização entra como função pura testável; qual das duas origens vira o
padrão do front é decisão de produto, não desta spec.

Prompt próprio (`mindmap_instructions`), com a mesma regra dos demais:
referências, exemplos e casos exclusivamente do texto do artigo.

---

## 7. Observabilidade — Langfuse

Substitui o LangSmith da PoC (que estava ligado por variável de ambiente e não
era consultado por ninguém).

- **Trace por `Run`**, com o `run_id` da plataforma como `trace_id` — o mesmo
  identificador que o usuário vê no console. Um span por nó do grafo e um por
  chamada de provedor (LLM, NotebookLM, GLiNER).
- **Custo e latência por nó**, que é o dado que faltou para decidir onde a PoC
  gastava os 25 minutos (medição manual mostrou 87% em mídia).
- **Prompt versionado**: cada geração registra `prompt.name` e `prompt.version`.
  Com isso, comparar duas versões de prompt deixa de ser impressão.
- **Erros de provedor como eventos de trace**, não apenas linha de log: timeout
  recuperado, relação descartada por citação inválida, sessão expirada.
- **Avaliação**: scores manuais e automáticos por artefato, ancorados no par
  (paper, prompt_version), preparando o terreno para regressão de qualidade.

Integração via `langfuse.openai`/callback do LangChain no serviço, com
`LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`. Desligado por
configuração deixa o pipeline funcionando — observabilidade não é dependência
dura.

---

## 8. API

REST sob `/v1`, OpenAPI gerado, SSE para acompanhamento. Sem auth nesta fase; o
serviço escuta em rede interna.

```
POST   /v1/collections                      cria coleção
GET    /v1/collections                      lista
GET    /v1/collections/{id}                 detalhe + papers

POST   /v1/collections/{id}/papers          upload de PDF -> Paper + run de ingest
GET    /v1/papers/{id}                      metadados
GET    /v1/papers/{id}/digest               digest corrente (?version=N)
GET    /v1/papers/{id}/digests              histórico de versões
GET    /v1/papers/{id}/artifacts            artefatos + estado

POST   /v1/papers/{id}/runs                 {kind: full|digest|artifact,
                                             artifact?, prompt_override?,
                                             save_prompt?}
GET    /v1/runs/{id}                        estado + fases
GET    /v1/runs/{id}/events                 SSE
POST   /v1/runs/{id}/resume                 retoma checkpoint humano
POST   /v1/runs/{id}/cancel                 cancela

GET    /v1/artifacts/{id}                   metadados + proveniência
GET    /v1/artifacts/{id}/content           302 para URL assinada

GET    /v1/prompts                          registry
GET    /v1/prompts/{name}                   versão corrente + histórico
POST   /v1/prompts/{name}/versions          publica nova versão

POST   /v1/integrations/notebooklm/session  define a sessão (§5)
GET    /v1/integrations/notebooklm/session  estado
POST   /v1/integrations/notebooklm/session/check

POST   /v1/collections/{id}/exports         gera bundle estático
GET    /v1/exports/{id}                     estado + download
```

Erros seguem RFC 7807 (`application/problem+json`), com `type` estável por
classe de falha — o front precisa distinguir "sessão do NotebookLM expirada" de
"provedor indisponível" para dizer ao usuário o que fazer.

---

## 9. Orquestração

- **Grafo de digest** (LangGraph Platform, checkpointer Postgres):
  `ingest → analyze → [checkpoint humano] → fan-out (8 geradores + knowledge) →
  assemble → persist`. Sem mídia: o fan-out leva ~2 minutos e a mídia levava 20,
  travando o checkpoint de conteúdo atrás de trabalho que não o afeta.
- **Jobs de artefato**, um por artefato, disparáveis isoladamente. É o modelo do
  regen da PoC, que provou ser o caminho normal de trabalho, não a exceção.
- **Fila por recurso externo**: os jobs de NotebookLM de uma mesma coleção são
  serializados, porque o provedor serializa de qualquer forma e o paralelismo só
  produzia timeouts.
- **Idempotência** por `(paper_id, kind, digest_version, prompt_version,
  source_hash)`; repetir devolve o artefato existente salvo `force=true`.
- **Retomada**: `run` e `run_event` em banco, então um restart do servidor deixa
  de perder o acompanhamento — na PoC, uma queda do processo tornava a execução
  invisível mesmo quando o provedor terminava o trabalho.

---

## 10. Monorepo

```
ab.rp/
  packages/
    ab.rp.shared/            OpenAPI, JSON Schema, tipos Python e TypeScript
  services/
    ab.rp.backend.kids/
      src/abrp_kids/
        api/                 rotas FastAPI, schemas de request/response
        domain/              entidades e regras, sem IO
        services/            ingestion, analysis, synthesis, knowledge,
                             media, packaging, export, prompts
        orchestration/       grafos, jobs, filas
        adapters/            openrouter, notebooklm, gliner, s3, langfuse
        persistence/         modelos, migrações (alembic), repositórios
      tests/
  apps/
    ab.rp.frontend.kids/     consome JSON; sem design system nesta fase
  infra/
    compose.yaml             postgres, minio, langgraph, langfuse
```

`domain/` e `services/` não importam FastAPI nem SQLAlchemy: o pipeline precisa
rodar em worker, em teste e em CLI sem subir a aplicação web.

---

## 11. Migração da PoC

| PoC | Destino | Ação |
|---|---|---|
| `extraction/`, `schemas/`, `llm/`, `media/` | `services/`, `adapters/` | Porta quase direta, trocando IO de arquivo por repositório |
| `graph/nodes/*` | `services/synthesis`, `orchestration/` | Nós viram funções de serviço; o grafo passa a compor serviços |
| `render/`, `manifest/` | `services/export` | Vira caminho opcional; templates viajam junto |
| `server/runner.py` | `orchestration/` + `persistence/` | Estado em memória vira tabela |
| `manifest/*_yaml.py` | — | Descartado: YAML dá lugar a Postgres |
| `render/templates/partials/theme_console*` | `apps/ab.rp.frontend.kids` | Reescrito com o design system, quando existir |
| `tests/pipeline/*` (293) | `services/ab.rp.backend.kids/tests` | Portados; os de regressão de provedor são os mais valiosos |

Os testes que descrevem falhas reais de provedor — JSON-string em tool-call,
timeout com artefato pronto, notebook por tema, prompt com placeholder não
substituído — migram primeiro. São eles que impedem a nova base de repetir os
erros que a PoC já pagou.

---

## 12. Riscos

| Risco | Mitigação |
|---|---|
| NotebookLM sem API oficial; quebra sem aviso | Adaptador isolado, contrato próprio, testes com fake; falha é fail-soft e visível no trace |
| Sessão do NotebookLM expira | §5: validação ativa, estado exposto, runs bloqueados em vez de perdidos |
| Dependência do LangGraph Platform | Grafo continua sendo LangGraph puro; o Platform é runtime, não framework de domínio |
| GLiNER pesado | Worker dedicado; extração de conhecimento é opcional por configuração |
| Custo de LLM sem controle | Langfuse por nó e por prompt version; teto por execução |

---

## 13. Fora de escopo

Autenticação e autorização, design system, e os módulos irmãos (pergunta de
pesquisa, refinamento de escopo, busca de eventos e revistas). Todos consomem
`Collection` e `Paper` pela mesma API — o gancho é o contrato em
`ab.rp.shared`, não código compartilhado.
