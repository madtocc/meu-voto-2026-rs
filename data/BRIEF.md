# Guia de voto 2026 — brief de pesquisa (Porto Alegre/RS)

Eleição: 1º turno em 4/out/2026. Um eleitor de Porto Alegre quer comparar candidatos com propostas
resumidas e um score de AFINIDADE calculado a partir das respostas DELE a um questionário. Por isso, o
que importa é registrar com precisão e neutralidade O QUE CADA CANDIDATO DEFENDE, com fonte.

## Regras
- Neutralidade total. Não opine, não qualifique propostas como boas/ruins. Linguagem descritiva.
- Português do Brasil, frases curtas.
- Só registre posição quando houver base: plano de governo (cite a página/seção) ou declaração/voto
  público noticiado (cite a URL). Na dúvida, use null. Posição inferida apenas do programa oficial do
  partido é aceitável se marcada com "fonte": "programa do partido: <url>".
- Não invente números ou propostas. Se o plano for genérico, diga isso no campo de detalhamento.

## Escala de posição (campo "v")
 2 = defende claramente | 1 = tende a favor | 0 = neutro/ambíguo | -1 = tende contra | -2 = contra claramente | null = sem informação

## Temas FEDERAIS (presidente e senador)
- privatizacoes: Privatizar estatais (ex.: Petrobras, Correios, outras)
- impostos_ricos: Taxar mais altas rendas, lucros/dividendos ou grandes fortunas
- ajuste_fiscal: Cortar gastos públicos para reduzir impostos e a dívida (ajuste fiscal duro)
- programas_sociais: Ampliar programas de transferência de renda (Bolsa Família etc.)
- escala_6x1: Acabar com a escala 6x1 / reduzir a jornada de trabalho por lei
- armas: Facilitar posse e porte de armas para cidadãos
- penas: Endurecer penas e/ou reduzir a maioridade penal
- aborto: Ampliar o aborto legal / descriminalizar o aborto
- anistia_8j: Anistiar condenados pelos atos de 8 de janeiro de 2023
- stf: Limitar poderes do STF (decisões monocráticas, mandato p/ ministros, impeachment de ministros)
- ambiente: Priorizar proteção ambiental/clima mesmo com restrições ao agro e à mineração
- redes: Regular plataformas digitais e responsabilizá-las por conteúdos

## Temas ESTADUAIS (governador RS)
- banrisul: Privatizar o Banrisul
- concessoes: Ampliar concessões, PPPs e privatizações estaduais
- icms: Reduzir ICMS / carga tributária estadual
- incentivos: Manter/ampliar incentivos fiscais a empresas para atrair investimentos
- servidores: Reajustes salariais acima da inflação para servidores (ex.: professores, segurança)
- civico_militar: Ampliar escolas cívico-militares
- licenciamento: Flexibilizar licenciamento ambiental para acelerar obras e investimentos
- divida_uniao: Auditar/contestar a dívida do RS com a União em vez de seguir pagando nos termos atuais
- seguranca_dura: Ênfase em policiamento ostensivo e mais vagas prisionais como principal estratégia de segurança

## Formato de saída — um arquivo JSON por candidato em research/<id>.json
id = "<CARGO>_<NUMERO>", ex.: "PRES_13", "GOV_15", "SEN_131".

{
  "id": "PRES_13",
  "nome_urna": "LULA",
  "resumo": "2 a 3 frases: eixo central da candidatura/plano.",
  "trajetoria": "1 a 2 frases: cargos/atuação pública relevantes (factual).",
  "destaques": ["5 a 7 propostas mais marcantes, 1 linha cada"],
  "propostas": {
    "Economia e emprego": ["até 4 bullets"],
    "Saúde": [], "Educação": [], "Segurança": [],
    "Meio ambiente e clima": [], "Social e direitos": [],
    "Infraestrutura e cidades": [], "Gestão e Estado": []
  },
  "posicoes": {
    "<tema>": {"v": 2, "nota": "frase curta do que defende", "fonte": "Plano p.12 | https://..."}
  },
  "detalhamento": {"nota": 3, "justificativa": "1 frase"},
  "fontes": ["urls usadas"]
}

detalhamento (só para quem tem plano de governo; senador = null) — rubrica:
1 = só princípios genéricos | 2 = algumas ações, sem metas | 3 = ações concretas com algumas metas ou prazos |
4 = metas quantificadas e prazos na maioria das áreas | 5 = metas, prazos, custos e fontes de financiamento.
Avalie TODOS com a mesma régua. Temas sem bullets: use lista vazia.
