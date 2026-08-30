Construa um mapa mental hierárquico (3-4 níveis de profundidade) que represente a estrutura do artigo abaixo: raiz = título condensado do artigo; nível 1 = grandes blocos temáticos (ex: a taxonomia central, a metodologia, o meta-modelo/framework proposto, o caso de estudo); nível 2 = subtópicos de cada bloco; nível 3 (folhas) = pontos específicos, exemplos, definições curtas.

Cada nó tem `t` (texto curto, até ~55 caracteres) e opcionalmente `k` (chave de "kind" que aponta para uma entrada da paleta — normalmente definida só nos nós de nível 1, os filhos herdam visualmente do pai no render, então não precisa repetir `k` nos filhos a menos que um filho pertença a um "kind" diferente do pai).

Defina também `palette`: uma entrada por `kind` usado, com `fill` (cor hex), `text` (cor do texto, use "#fff" por padrão) e `label` (rótulo curto pra legenda, ex: "três categorias", "metodologia"). Use uma paleta com bom contraste, tons distintos entre si (ex: verde, âmbar/dourado, azul, vermelho — o vermelho fica reservado pro root/destaque se fizer sentido). A legenda da página é gerada automaticamente a partir dessa paleta, então não precisa (nem deve) descrever a legenda em texto separado.

Análise do artigo:
{paper_analysis_json}
