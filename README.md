# CSS3E — As 3 Categorias de Sistemas Sensíveis ao Contexto

> **App ao vivo:** https://ab-orbit.github.io/css3e/
> **Tela de abertura:** https://ab-orbit.github.io/css3e/index_extended.html
> **Modo facilitador:** https://ab-orbit.github.io/css3e/?facilitador=1
> **Material de apoio:** [mapa de superfície contextual](https://ab-orbit.github.io/css3e/resources/) · [5 simuladores](https://ab-orbit.github.io/css3e/resources/cases/) · [relatório técnico (PDF)](https://ab-orbit.github.io/css3e/resources/relatorio_contexto_sem_consentimento.pdf)

Dinâmica interativa de sala de aula que **demonstra na prática** — no próprio
navegador do participante — as três categorias de sistemas sensíveis ao contexto
propostas por Shishkov, Larsen, Warnier e Janssen (2018): **SMCAS**, **UDCAS** e
**VSCAS**.

Em vez de explicar os conceitos em slides, a aplicação *se comporta* como cada
uma das três categorias enquanto a pessoa responde 3 perguntas — e só no final
revela o que fez, quando fez e por quê.

---

## Contexto acadêmico

| | |
|---|---|
| **Disciplina** | IN1133 — Contexto Computacional |
| **Instituição** | Centro de Informática (CIn) — UFPE |
| **Docente** | Patrícia Tedesco |
| **Apresentadores** | Bruna Juliana Melo da Costa · Jefferson Wellington da Cunha · Renata Stefany dos Santos Silva |
| **Artigo-base** | *Three Categories of Context-Aware Systems* — Shishkov, B.; Larsen, J. B.; Warnier, M.; Janssen, M. |
| **Publicação** | BMSD 2018 (8th Int. Symposium on Business Modeling and Software Design), LNBIP vol. 319, pp. 185–202, Springer |
| **DOI** | [10.1007/978-3-319-94214-8_12](https://doi.org/10.1007/978-3-319-94214-8_12) |

### O argumento do artigo, em uma frase

Sistemas sensíveis ao contexto sempre ajustam *alguma coisa* ao estado do
contexto — mas **o que** é ajustado difere, e a literatura não tinha termos
consolidados para essa distinção. Os autores propõem três categorias e derivam
uma conceituação/meta-modelo via a abordagem **SDBC** (Software Derived from
Business Components), alinhando-a à tecnologia de agentes pelo framework
**AORTA** (ciclo *Obligation Check* → *Option Generation* → *Action Execution*).
Ilustram tudo com um caso real de drones em segurança de fronteira terrestre.

### As três categorias

| | **SMCAS** | **UDCAS** | **VSCAS** |
|---|---|---|---|
| Nome | Self-Managing Context-Aware System | User-Driven Context-Aware System | Value-Sensitive Context-Aware System |
| Ajusta | Processos internos do próprio sistema | Variante de serviço entregue ao usuário | Conformidade com valores sociais |
| Objetivo | Eficiência / sobrevivência do sistema | Eficácia percebida pelo usuário | Conformidade ética e social |
| Gatilho | Estado interno (ex.: bateria baixa) | Mudança na situação do usuário | Conflito com o espaço civil |
| Exemplo | Termostato inteligente | Assistente de smartphone | Câmera com desfoque de rostos |

O caso do drone de fronteira usado no artigo divide seis comportamentos entre as
três lentes: consumo de energia e ajuste de câmera (SMCAS), ajuste de rota e
processamento de dados em relatório (UDCAS), evitar/borrar rostos e minimizar
ruído sobre área residencial (VSCAS).

**Challenge question levantada na apresentação:** os autores afirmam que um
sistema real deve exercer as três categorias simultaneamente via um "AORTA
Engine", mas nunca mostram **como o sistema decide qual categoria vence** quando
elas colidem — apenas dizem que é preciso um *prioritization scheme*, sem
detalhá-lo.

---

## O que a aplicação faz

A dinâmica tem 3 perguntas e cada uma encena uma categoria. O truque é que a
demonstração acontece **antes** da explicação.

**Tela 0 — Landing (SMCAS silencioso).** Antes de qualquer pergunta, o sistema
já informa o que sabe: sua ordem de chegada na sessão (contador atômico no
Firestore — reação ao estado interno do próprio sistema), tipo de aparelho, SO,
tipo de entrada (toque vs. mouse), tema claro/escuro, fuso, idiomas do
navegador, núcleos de CPU, RAM aproximada, qualidade da conexão, preferências de
acessibilidade e cidade aproximada por IP. Nada foi digitado, nada pediu
permissão de geolocalização.

**Pergunta 1 — slider (`Q_SM`).** "O quanto você confia no piloto automático?"
Enquanto responde, o sistema conta silenciosamente **quantas vezes** o slider foi
movido e **quantos segundos** levou para decidir.

**Pergunta 2 — slider (`Q_UD`, UDCAS).** O **enunciado é reescrito em tempo real**
a partir da resposta anterior *e* do comportamento observado: quem hesitou (≥6
ajustes) recebe um texto; quem puxou para automático (≥6), outro; quem puxou para
manual (≤4), outro; meio-termo, outro. Ou seja: variante de serviço conforme a
situação do usuário.

**Pergunta 3 — escolha binária (`Q_VS`, VSCAS).** "Personalização máxima" vs.
"Privacidade máxima", sem meio-termo — forçando o participante a declarar um
valor.

**Tela de mapa coletivo.** As três respostas viram **coordenadas baricêntricas**
normalizadas e o ponto da pessoa é plotado sobre a imagem do triângulo
SMCAS/UDCAS/VSCAS, ao vivo, junto com todos os outros participantes e o
**centroide do grupo** (círculo tracejado). Abaixo: mapa de proximidade
geográfica agrupado por cidade e barras de SO/dispositivo. Só então o *debrief*
explica retroativamente qual tela foi qual categoria.

**Dossiê individual (opcional).** Duas listas lado a lado: o que **foi**
coletado, e o que foi **deliberadamente não coletado** apesar de tecnicamente
possível (riscado na tela).

**"Até onde isso poderia ir?" (opcional).** Demonstração **isolada e 100% local**
de fingerprinting: hash de Canvas, vendor/renderer da GPU via
`WEBGL_debug_renderer_info`, propriedades do AudioContext e um identificador
combinado. Nada disso sai do navegador, não é salvo, não vira `participantId` e
não é comparado entre participantes. O ponto pedagógico é justamente esse: **a
diferença entre um sistema capaz e um sistema sensível a valores não é técnica, é
a decisão de não fazer.**

---

## Tela de abertura: `index_extended.html`

Painel de evidências para abrir a apresentação, antes da dinâmica. A tese é
mostrada em vez de explicada: a página lê o aparelho e exibe **70 dimensões de
adaptação**, cada uma como um par lado a lado — o que um sistema genérico
entregaria a todo mundo, e o que **este** entregou ao aparelho de quem está
olhando. Divididas em oito famílias:

| Família | Exemplos |
|---|---|
| Idioma, formato e lugar | locale, região, datas, números, hora, 12/24 h, timezone, conteúdo regional e temporal |
| Layout e interação | colunas, navegação, posição de menus, alvo de toque, densidade, touch vs. hover, orientação, foldables, PWA |
| Mídia, rede e peso | formato e densidade de imagem, resolução, bitrate, codecs, autoplay, prefetch, lazy loading |
| Movimento, cor e visão | animações, transições, transparência, contraste, dark/light |
| Energia e processamento | núcleos, memória, complexidade gráfica, polling, cache, tarefas de fundo, sincronização, bateria |
| Rede instável e continuidade | estado da conexão, comportamento offline, alertas, visita nº, retomada de tarefa |
| O que aparece primeiro | home contextual, onboarding, ordem de conteúdo, sugestões, CTA, nível de explicação, ajuda |
| Sinais que mandam parar | GPC, DNT, estado das permissões lido sem pedir, redução de movimento |

Três decisões de implementação que sustentam a honestidade da tela:

- **Zero requisições de rede.** Nenhum `fetch`, nenhuma fonte externa, nenhum
  Firebase. Funciona inteira numa rede institucional que bloqueie Google Cloud —
  o mesmo problema que a dinâmica principal já enfrentou.
- **Zero prompts.** Só APIs que nunca abrem caixa de permissão. `permissions.query()`
  aparece na tela justamente por ler o estado de uma permissão **sem** solicitá-la.
- **Um único armazenamento local**, o contador de visitas em `localStorage`, usado
  na célula "continuidade da sessão", declarado no rodapé e apagável em um clique.

Fecha com a lista do que ficou de fora — canvas, GPU, áudio, fontes, identificador
persistente — e o CTA para a dinâmica, preservando `?sessao=`.

---

## Arquitetura

Página única, sem build, sem dependências instaladas, sem backend próprio.

```
index.html            HTML + CSS + JS vanilla, imagem do triângulo embutida em base64
   ├─ <script type="module">   Firebase v10.12.2 via CDN gstatic  → window.__fb
   └─ <script>                 App (IIFE), espera o evento 'fb-ready'
Firestore             sessions/{sessionTag}          { count }
                      sessions/{sessionTag}/responses/{participantId}
                                                     { sm, ud, vs, device, os, locale, tz,
                                                       languages, city, region, country,
                                                       lat, lon, connType, saveData,
                                                       cpuCores, ramApprox, reducedMotion,
                                                       highContrast, smMoves, smSeconds, ts }
get.geojs.io          Geolocalização aproximada por IP (timeout de 4s via Promise.race)
```

**Pontos de implementação relevantes:**

- **Contador de chegada atômico** — `runTransaction` sobre `sessions/{tag}.count`,
  resolvendo a condição de corrida que a versão anterior (baseada em
  `window.storage`) tinha quando duas pessoas entravam no mesmo instante.
- **Tempo real** — `onSnapshot` na subcoleção `responses`; o mapa do facilitador e
  o de cada participante se atualizam sozinhos, sem polling.
- **Normalização baricêntrica** — `sm`, `ud` e `vs` são divididos pela soma; a
  escolha binária da Q3 entra com peso 9 (privacidade) ou 2 (personalização).
  As coordenadas dos vértices são ancoradas em espaço de imagem 1024×1024.
- **Debrief com os dados da própria pessoa** — os três passos que fecham a
  dinâmica não são texto genérico: cada cartão mostra o valor que aquela pessoa
  produziu na tela correspondente (ordem de chegada e aparelho no SMCAS, número
  de ajustes e qual das quatro versões do enunciado ela recebeu no UDCAS, a
  escolha binária no VSCAS). Quem está ao lado vê números diferentes.
- **Legenda desenhada, não nomeada** — os três marcadores do mapa (você, demais
  participantes, média do grupo) aparecem como SVG de verdade ao lado do rótulo.
  A versão anterior dizia “seu ponto: vermelho” para um ponto de miolo escuro com
  anel vermelho; nenhum marcador é mais descrito por cor.
- **Placa clara sob o diagrama** — o triângulo é desenhado sobre uma placa branca
  com grade, mesmo no cartão escuro, e a imagem fica a 65% de opacidade: legível o
  bastante para orientar, discreta o bastante para os pontos dominarem.
- **Fallback de rede (6s)** — redes institucionais frequentemente bloqueiam
  domínios do Google Cloud. Se o Firestore não responder, a pessoa vê uma tela de
  instruções (trocar para dados móveis, tentar de novo, avisar o facilitador) em
  vez de ficar presa em "carregando…".
- **Entrada manual no modo facilitador** — para quem não conseguiu conectar de
  jeito nenhum; grava com `device: 'manual'`.
- **Sem `AbortController` no fetch de geo** — de propósito: `AbortSignal` em
  `options` não atravessava o proxy do ambiente onde foi desenvolvido
  (`DataCloneError`). Timeout feito com `Promise.race`.

### Parâmetros de URL

| Parâmetro | Efeito |
|---|---|
| `?sessao=<slug>` | Isola a rodada. Sanitizado para `[a-zA-Z0-9_-]`, máx. 40 chars. Padrão: `geral` |
| `?facilitador=1` (ou `?facilitator=1`) | Abre a tela de projeção: mapa ao vivo, contagem, reset da rodada, entrada manual. Não faz perguntas |

---

## Como conduzir uma sessão

1. Abra a projeção: `https://ab-orbit.github.io/css3e/?facilitador=1&sessao=turma01`
2. Compartilhe com os participantes o link **sem** `facilitador=1`:
   `https://ab-orbit.github.io/css3e/?sessao=turma01`
3. Deixe todo mundo responder. O triângulo se preenche ao vivo na projeção.
4. Conduza o debrief pelo mapa: *o grupo está puxando para qual vértice? Isso diz
   algo sobre como esta organização projeta sistemas?*
5. Peça para abrirem "Revelar meu dossiê individual" e "Até onde isso poderia ir?".
6. Para rodar de novo com outra turma: **Reiniciar rodada** (apaga as respostas da
   sessão) ou simplesmente use outro `?sessao=`.

---

## Arquivos do repositório

| Arquivo | O que é |
|---|---|
| `index.html` | **Versão publicada.** Firebase/Firestore + fingerprint demo + dossiê + imagem embutida |
| `index_extended.html` | **Tela de abertura visual.** Painel de evidências com 70 dimensões de adaptação, sem rede e sem Firebase |
| `dinamica_meta_validacao.html` | Versão anterior, sobre `window.storage` (polling de 2,5s, sem transação atômica) |
| `dinamica_meta_validacao_firebase copy.html` | Passo intermediário da migração para Firestore, antes das telas de dossiê e fingerprint |
| `three-categories.png` | Imagem do triângulo das 3 categorias (também embutida em base64 no `index.html`) |
| `resources/index.html` | Material de apoio: mapa de superfície contextual, com matriz observar/inferir/fazer |
| `resources/relatorio_contexto_sem_consentimento.pdf` | Relatório técnico completo (fonte LaTeX ao lado, `.tex`) |
| `resources/cases/` | Cinco simuladores interativos de adaptação contextual, com folha de estilo compartilhada |
| `artigo_original.pdf` | Artigo de Shishkov et al. (2018), versão de repositório institucional |
| `apresentacao_artigo.pdf` | Slides da apresentação (28 páginas) |

---

## Material de apoio (`resources/`)

Três recursos aprofundam o que a dinâmica demonstra. Todos aparecem com
pré-visualização ao vivo no fim da tela de abertura — a página real embutida em
escala reduzida, não uma captura — e como links no fim das duas telas de mapa,
a do participante e a do facilitador.

| Recurso | O que traz |
|---|---|
| [**Mapa de superfície contextual**](https://ab-orbit.github.io/css3e/resources/) (`resources/index.html`) | Doze famílias de sinais, cada uma com um drawer técnico: o que dá para observar, o que dá para inferir, riscos e contraexemplos. Inclui a matriz “pode observar / pode inferir / deve fazer”, o pipeline `ObservedContext → DerivedContext → Policy → Adaptation` e uma leitura local do contexto de quem está acessando. |
| [**5 simuladores**](https://ab-orbit.github.io/css3e/resources/cases/) (`resources/cases/`) | Onde o material deixa de descrever e passa a deixar experimentar (detalhes abaixo). |
| [**Contexto sem consentimento**](https://ab-orbit.github.io/css3e/resources/relatorio_contexto_sem_consentimento.pdf) (PDF) | Relatório técnico: inventário dos sinais disponíveis sem prompt, separação entre contexto observado e inferido, e os deveres de finalidade que a disponibilidade técnica não dispensa. Fonte LaTeX em `resources/relatorio_contexto_sem_consentimento.tex`. |

### Os cinco simuladores (`resources/cases/`)

A tela de abertura mostra o que **o seu** aparelho recebeu. Os simuladores
invertem isso: você mexe nos sinais e acompanha a política e a interface se
reorganizarem ao vivo, com o rastro da decisão impresso embaixo de cada um no
formato `sinal → contexto → decisão → experiência`.

| Case | Sinais que você controla | O que muda na tela |
|---|---|---|
| 01 · Interação & viewport | viewport, pointer, hover, pontos de toque | Colunas, densidade, navegação, alvos de toque, e se as ações podem ou não se esconder atrás do hover |
| 02 · Orçamento de recursos | Save-Data, throughput, RTT, compute, bateria, carregando | Resolução de mídia, autoplay, prefetch, sincronização, complexidade do gráfico |
| 03 · Preferências de apresentação | tema, movimento, contraste, transparência | Aplicação direta da preferência, sem inferir condição pessoal a partir dela |
| 04 · Contexto regional & temporal | locale, timezone, região aproximada, hora local | Formatos por `Intl`, horário dos eventos, moeda, atalhos regionais e bloco temporal |
| 05 · Contexto composto | os quatro anteriores, combinados | Uma policy única, com precedência explícita entre preferência declarada, preferência de sistema, capacidade observada e região |

Dois princípios que o conjunto sustenta, e que valem para o código de vocês:

- **O quadro de preview assume a largura simulada.** Nos cases 01 e 05, escolher
  “390 px” estreita o quadro de verdade; quando a janela não comporta a largura
  pedida, a página diz isso em vez de fingir.
- **Idioma, fuso e região são sinais independentes.** O case 04 deixa os três
  controles livres justamente para você montar a combinação incoerente —
  `en-US` + `America/Recife` + Madrid — e ver de onde vêm os defaults errados de
  quem trata os três como uma coisa só.

A regra que os dois defendem, e que a dinâmica encena: **escolha o sinal menos
identificável capaz de resolver o problema.** Se media query resolve layout, não
colete modelo de aparelho. Se `MediaCapabilities` resolve vídeo, não identifique
a GPU.

O `resources/index.html` usa o mesmo tema visual do restante da aplicação — fundo
ink com papel milimetrado, painéis em papel, vermelho como único acento e valores
medidos em mono — e liga de volta para a tela de abertura e para a dinâmica.

---

## Rodando localmente

O `index.html` usa `<script type="module">`, então precisa ser servido por HTTP —
abrir por `file://` quebra o import do Firebase.

```bash
python3 -m http.server 8000
# http://localhost:8000/index.html?sessao=teste
# http://localhost:8000/index.html?facilitador=1&sessao=teste
```

## Deploy

GitHub Pages servindo a raiz da branch `main`. Não há build: `git push` e o
`index.html` já é o site em https://ab-orbit.github.io/css3e/.

---

## Privacidade, ética e segurança

Esta é uma peça didática sobre coleta de dados que, por necessidade, coleta
dados. As escolhas foram feitas de forma explícita:

- **O que é coletado** está integralmente listado na tela de dossiê, para a
  própria pessoa, durante a sessão.
- **Não há identificação.** `participantId` é um token aleatório
  (`Math.random()` + timestamp), sem relação com o dispositivo. Não há login, não
  há cookie, não há fingerprint persistido.
- **A demo de fingerprint nunca sai do navegador.** Não é enviada ao Firestore,
  não é usada como identificador e não é comparada entre participantes.
- **A geolocalização é por IP** (get.geojs.io), não GPS: erra por dezenas de km e
  aponta o servidor, não a pessoa, quando há VPN. O mapa é declaradamente
  ilustrativo, não cartográfico.

> ### ⚠️ Aviso de segurança sobre a configuração do Firestore
>
> As regras documentadas no `index.html` são `allow read, write: if true` para
> `sessions/{sessionId}` e sua subcoleção `responses`. Isso libera leitura e
> escrita para **qualquer pessoa com o link**, sem autenticação — inclusive
> apagar respostas de uma sessão. É uma escolha aceitável para um workshop
> pontual e dados não identificáveis, mas **não** para uso continuado.
>
> Depois da apresentação: aperte as regras ou **delete o projeto Firebase**. A
> `apiKey` presente no HTML é pública por design no Firebase Web (identifica o
> projeto, não autentica), mas com regras abertas ela é suficiente para escrever
> na base — a proteção real são as regras, e hoje não há nenhuma.

---

## Citação

```bibtex
@inproceedings{shishkov2018three,
  title     = {Three Categories of Context-Aware Systems},
  author    = {Shishkov, Boris and Larsen, John Bruntse and Warnier, Martijn and Janssen, Marijn},
  booktitle = {Business Modeling and Software Design (BMSD 2018)},
  series    = {Lecture Notes in Business Information Processing},
  volume    = {319},
  pages     = {185--202},
  year      = {2018},
  publisher = {Springer},
  doi       = {10.1007/978-3-319-94214-8_12}
}
```

Os PDFs incluídos aqui são cópias de repositório institucional (DTU Orbit / TU
Delft), redistribuídas para fins de estudo em sala de aula. Os direitos do artigo
permanecem com os autores e com a Springer.
