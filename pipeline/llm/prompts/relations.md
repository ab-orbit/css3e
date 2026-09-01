Você recebe a lista de entidades que um extrator de spans encontrou neste artigo, e trechos do texto original. Sua tarefa é identificar quais RELAÇÕES o texto explicitamente AFIRMA entre essas entidades.

Regras obrigatórias:

1. Use SOMENTE entidades da lista fornecida, referenciando-as pela `key` exata. Não invente entidades novas.
2. Só afirme uma relação que o texto declare. Não infira do seu conhecimento geral do domínio — se o artigo não diz, a relação não existe para este fim.
3. Para cada relação, forneça em `quote` uma sentença COPIADA LITERALMENTE do texto, sem alterar uma vírgula, que contenha as duas entidades e sustente a relação. A citação será verificada caractere a caractere contra o texto original; relações cuja citação não for encontrada serão descartadas.
4. A DIREÇÃO importa. `source` é quem exerce a relação, `target` quem a recebe. "MAS é composto por agentes" tem source=mas, target=agentes com label "é composto por" — não o inverso.
5. Prefira rótulos de relação curtos e verbais em português: "integra-se a", "é parte de", "usa", "estende", "avalia", "compara-se a", "aplica-se a", "possibilita", "é composto por", "depende de".
6. Não repita o mesmo par de entidades com rótulos diferentes. Escolha a relação mais forte e específica que o texto sustenta.
7. Retorne no máximo {max_relations} relações, priorizando as centrais para o argumento do artigo.

Entidades disponíveis (key — nome — tipo — nº de menções):
{entity_list}

Texto do artigo:
{paper_text}
