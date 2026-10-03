"""Passo 2: votos dos deputados do RS (que concorrem em 2026) em votações nominais selecionadas.
Requer cache/deputados_match.json (gerado por 01_deputados.py).
Saída: ../dep_federal_votos.json
"""
import json
import os

from camara_api import get, HERE

OUT = os.path.join(HERE, "..", "dep_federal_votos.json")

# Votações escolhidas (ids conferidos via /proposicoes/{id}/votacoes e /votacoes/{id}).
VOTACOES = [
    {"key": "arcabouco_fiscal", "id_votacao": "2357053-47", "id_proposicao": 2357053,
     "titulo": "Arcabouço fiscal (PLP 93/2023)",
     "descricao": "Texto-base do novo regime fiscal que substituiu o teto de gastos, limitando o crescimento "
                  "da despesa federal a uma parte do crescimento da receita, com metas de resultado primário."},
    {"key": "reforma_tributaria", "id_votacao": "2196833-326", "id_proposicao": 2196833,
     "titulo": "Reforma tributária (PEC 45/2019, 1º turno)",
     "descricao": "Texto-base, em 1º turno, da reforma tributária sobre o consumo, que troca PIS, Cofins, IPI, "
                  "ICMS e ISS por um IVA dual (CBS federal e IBS de estados e municípios) e cria um imposto seletivo."},
    {"key": "numero_deputados", "id_votacao": "2383019-54", "id_proposicao": 2383019,
     "titulo": "Aumento do número de deputados (PLP 177/2023)",
     "descricao": "Projeto que aumenta de 513 para 531 o número de deputados federais, redistribuindo "
                  "vagas entre os estados com base no Censo 2022 sem reduzir a bancada de nenhum estado."},
    {"key": "licenciamento_ambiental", "id_votacao": "257161-454", "id_proposicao": 257161,
     "titulo": "Lei Geral do Licenciamento Ambiental (PL 2159/2021)",
     "descricao": "Emendas do Senado (aprovadas em bloco, ressalvados destaques) ao projeto que cria regras "
                  "nacionais de licenciamento ambiental e amplia modalidades simplificadas, como a licença por "
                  "adesão e compromisso (LAC)."},
    {"key": "pec_blindagem", "id_votacao": "2270800-135", "id_proposicao": 2270800,
     "titulo": "PEC da Blindagem / das Prerrogativas (PEC 3/2021, 1º turno)",
     "descricao": "Texto-base, em 1º turno, da PEC que exige autorização da Câmara ou do Senado para que o STF "
                  "processe criminalmente deputados e senadores e estende o foro no STF a presidentes de partidos."},
    {"key": "anistia_urgencia", "id_votacao": "2562149-7", "id_proposicao": 2358548,
     "titulo": "Urgência do PL da Anistia (PL 2162/2023)",
     "descricao": "Requerimento de urgência para o PL 2162/2023, que propunha anistia a participantes de "
                  "manifestações políticas a partir de 30/10/2022, incluindo os atos de 8 de janeiro de 2023."},
    {"key": "isencao_ir", "id_votacao": "2487436-169", "id_proposicao": 2487436,
     "titulo": "Isenção do IR até R$ 5 mil (PL 1087/2025)",
     "descricao": "Projeto que isenta do Imposto de Renda quem ganha até R$ 5 mil por mês, reduz o imposto até "
                  "R$ 7.350 e cria uma tributação mínima para rendas acima de R$ 600 mil por ano."},
    {"key": "antifaccao", "id_votacao": "2579832-62", "id_proposicao": 2579832,
     "titulo": "PL Antifacção (PL 5582/2025)",
     "descricao": "Texto-base do substitutivo do relator Guilherme Derrite ao Marco Legal de Combate ao Crime "
                  "Organizado, que aumenta penas para integrantes de facções e organizações criminosas e altera "
                  "regras penais e processuais."},
    {"key": "dosimetria_8j", "id_votacao": "2358548-89", "id_proposicao": 2358548,
     "titulo": "PL da Dosimetria (substitutivo ao PL 2162/2023)",
     "descricao": "Texto-base do substitutivo que reduz penas de condenados pelos atos de 8 de janeiro de 2023 e "
                  "pela tentativa de golpe de Estado, em vez de conceder anistia."},
    {"key": "escala_6x1", "id_votacao": "2233802-424", "id_proposicao": 2233802,
     "titulo": "Fim da escala 6x1 (PEC 221/2019, 1º turno)",
     "descricao": "PEC, em 1º turno, que fixa jornada máxima de 40 horas semanais com dois dias de descanso "
                  "remunerado (fim da escala 6x1), sem redução de salário e com regra de transição."},
]

VOTO_MAP = {"Sim": "Sim", "Não": "Não", "Abstenção": "Abstenção", "Obstrução": "Obstrução",
            "Artigo 17": "Art. 17 (presidente)"}


def situacao_em(hist, quando):
    """Situação do deputado (57ª legislatura) no instante 'quando' (ISO)."""
    sit = None
    for h in hist:
        if h["dataHora"] <= quando:
            sit = h["situacao"]
        else:
            break
    return sit


deps = json.load(open(os.path.join(HERE, "cache", "deputados_match.json")))
hist_by_id = {}
for d in deps:
    h = get(f"/deputados/{d['id_camara']}/historico")["dados"]
    hist_by_id[d["id_camara"]] = sorted([x for x in h if x["idLegislatura"] == 57 and x["situacao"]],
                                        key=lambda x: x["dataHora"])

votacoes_out = []
votos_por_vot = {}
for v in VOTACOES:
    det = get(f"/votacoes/{v['id_votacao']}")["dados"]
    assert det["siglaOrgao"] == "PLEN", v
    votos = get(f"/votacoes/{v['id_votacao']}/votos")["dados"]
    votos_por_vot[v["key"]] = {x["deputado_"]["id"]: x for x in votos}
    v["_quando"] = det["dataHoraRegistro"]
    votacoes_out.append({
        "key": v["key"],
        "titulo": v["titulo"],
        "data": det["data"],
        "descricao": v["descricao"],
        "url": f"https://www.camara.leg.br/propostas-legislativas/{v['id_proposicao']}",
        "url_api": f"https://dadosabertos.camara.leg.br/api/v2/votacoes/{v['id_votacao']}",
        "id_votacao": v["id_votacao"],
        "resultado_oficial": det["descricao"].replace("\n", " ").strip(),
        "n_votos_registrados": len(votos),
    })
    print(v["key"], det["data"], det["dataHoraRegistro"], len(votos), "|", det["descricao"][:120].replace("\n", " "))


def montar(d):
    votos, partidos = {}, {}
    for v in VOTACOES:
        reg = votos_por_vot[v["key"]].get(d["id_camara"])
        if reg:
            votos[v["key"]] = VOTO_MAP.get(reg["tipoVoto"], reg["tipoVoto"])
            partidos[v["key"]] = reg["deputado_"]["siglaPartido"]
        else:
            sit = situacao_em(hist_by_id[d["id_camara"]], v["_quando"])
            votos[v["key"]] = "Ausente" if sit == "Exercício" else "—"
            partidos[v["key"]] = None
    return votos, partidos


deputados, outros = [], []
for d in deps:
    votos, partidos = montar(d)
    base = {"id_camara": d["id_camara"], "nome_parlamentar": d["nome_parlamentar"],
            "condicao_57a_legislatura": d["condicao"], "votos": votos, "partido_na_votacao": partidos}
    tse_df = [t for t in d["tse"]]
    if tse_df:
        t = tse_df[0]
        deputados.append({"nr_candidato": t["NR_CANDIDATO"], "nm_urna": t["NM_URNA_CANDIDATO"].strip(),
                          "nm_candidato": t["NM_CANDIDATO"], "partido": t["SG_PARTIDO"],
                          "situacao_candidatura": t["SITUACAO_TOT"], **base})
    else:
        outros.append({"nm_candidato_civil": d["nome_civil"], **base})

deputados.sort(key=lambda x: x["nm_urna"])

# Ex-deputados do RS (57ª leg.) que concorrem em 2026 a outro cargo (não dep. federal) — referência extra.
OUTROS_CARGOS = {74400: ("SENADOR", "131"), 156190: ("SENADOR", "300"), 204416: ("SENADOR", "222"),
                 220552: ("GOVERNADOR", "22"), 235776: ("1º SUPLENTE DE SENADOR", "300")}
outros_cargos = []
for o in outros:
    if o["id_camara"] in OUTROS_CARGOS:
        cargo, nr = OUTROS_CARGOS[o["id_camara"]]
        outros_cargos.append({"cargo_2026": cargo, "nr_candidato": nr, **o})

out = {
    "fonte": "API de Dados Abertos da Câmara dos Deputados (https://dadosabertos.camara.leg.br/api/v2), "
             "consultada em 2026-10-02; candidaturas: TSE consulta_cand_2026_RS.",
    "notas": [
        "'Ausente' = estava no exercício do mandato na data, mas não registrou voto (inclui faltas, missões "
        "oficiais e licenças curtas não registradas como afastamento, p.ex. saúde/maternidade sem posse de suplente).",
        "'—' = não estava no exercício do mandato na data (suplente fora de exercício ou titular licenciado, "
        "segundo /deputados/{id}/historico).",
        "Partido em 'partido' é o da candidatura 2026 (TSE); 'partido_na_votacao' é o registrado pela Câmara no voto.",
    ],
    "votacoes": votacoes_out,
    "deputados": deputados,
    "outros_cargos_2026": outros_cargos,
}
json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=2)
print("deputados:", len(deputados), "| outros cargos:", len(outros_cargos),
      "| sem candidatura:", [o["nome_parlamentar"] for o in outros if o["id_camara"] not in OUTROS_CARGOS])
