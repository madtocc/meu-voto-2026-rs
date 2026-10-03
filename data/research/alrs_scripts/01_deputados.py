"""Passo 1: deputados estaduais em exercício na Assembleia Legislativa do RS (56ª legislatura, 2023-2027),
segundo a lista oficial do portal, casados com as candidaturas de 2026 do TSE (RS).

A fonte oficial só publica o NOME PARLAMENTAR e o partido (não há nome civil nem CPF). Por isso o casamento
é feito em três regras, da mais forte para a mais fraca, sempre exigindo partido igual e resultado único
entre TODAS as candidaturas do RS (qualquer partido ou cargo):
  1. nome_civil  : nome parlamentar == nome civil do TSE (NM_CANDIDATO), normalizados;
  2. nome_urna   : nome parlamentar == nome de urna do TSE (NM_URNA_CANDIDATO), normalizados;
  3. tokens_civil: todas as palavras do nome parlamentar (sem tratamentos como DR./PROF.) aparecem no nome
                   civil do TSE; exige ao menos duas palavras, e um único candidato no RS inteiro.
Qualquer caso sem resultado ou com mais de um resultado fica SEM casamento e é listado no final.
Só contam candidatos presentes em data/base.json (titulares) ou, no caso de vice-governador, listados como
'companheiros' de uma chapa de base.json.
Saída: cache/deputados_match.json
"""
import csv
import json
import os
import re
import unicodedata

from alrs_http import get_json, HERE

DATA = os.path.abspath(os.path.join(HERE, "..", ".."))

CARGO_SIGLA = {"DEPUTADO ESTADUAL": "DE", "DEPUTADO FEDERAL": "DF", "SENADOR": "SEN", "GOVERNADOR": "GOV",
               "PRESIDENTE": "PRES"}
# Tratamentos que podem aparecer no nome parlamentar e não fazem parte do nome civil.
TRATAMENTOS = {"DR", "DRA", "PROF", "PROFA", "PROFESSOR", "PROFESSORA", "DEP", "DEPUTADO", "DEPUTADA"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", s)).strip()


# --- TSE (todas as candidaturas do RS, inclusive vices e suplentes, para detectar homônimos) ---
cand = list(csv.DictReader(open(os.path.join(DATA, "consulta_cand_2026_RS.csv"), encoding="latin1"), delimiter=";"))

# --- base.json: só id / nr / cargo / urna (arquivo grande, de uma linha só) ---
base = json.load(open(os.path.join(DATA, "base.json"), encoding="utf-8"))
ids_base = {c["id"] for c in base["candidatos"]}
vices_base = {}  # (nr da chapa, nome de urna normalizado) -> id da chapa em base.json
for c in base["candidatos"]:
    for comp in (c.get("companheiros") or []):
        if comp.get("cargo") == "VICE-GOVERNADOR":
            vices_base[(c["nr"], norm(comp["urna"]))] = c["id"]
del base


def casar(nome_parl, partido):
    """Devolve (regra, [linhas do TSE]) para um nome parlamentar e partido oficiais.
    Só é casamento quando a regra é uma das três acima e há exatamente uma linha."""
    n, p = norm(nome_parl), norm(partido)
    for regra, campo in (("nome_civil", "NM_CANDIDATO"), ("nome_urna", "NM_URNA_CANDIDATO")):
        rs = [r for r in cand if norm(r[campo]) == n]   # unicidade conferida no RS inteiro, qualquer partido/cargo
        if len(rs) == 1 and norm(rs[0]["SG_PARTIDO"]) == p:
            return regra, rs
        if rs:   # homônimo ou partido diferente: não casa, vai para revisão manual
            return ("ambiguo_" + regra if len(rs) > 1 else "partido_divergente"), rs
    toks = [t for t in n.split() if t not in TRATAMENTOS]
    if len(toks) >= 2:
        rs = [r for r in cand if set(toks) <= set(norm(r["NM_CANDIDATO"]).split())]
        if len(rs) == 1 and norm(rs[0]["SG_PARTIDO"]) == p:
            return "tokens_civil", rs
        if rs:
            return ("ambiguo_tokens" if len(rs) > 1 else "partido_divergente"), rs
    return None, []


lista = get_json("/listarDestaqueDeputados")["lista"]
out, pend = [], []
for d in sorted(lista, key=lambda x: norm(x["nomeDeputado"])):
    nome = re.sub(r"\s+", " ", d["nomeDeputado"]).strip()
    regra, rows = casar(nome, d["siglaPartido"])
    rec = {"id_oficial": d["idDeputado"], "codigo_pro": d.get("codigoPro"), "nome_parlamentar": nome,
           "partido_alrs": d["siglaPartido"], "match_how": None, "destino": None, "chave": None, "tse": None}
    ok = regra in ("nome_civil", "nome_urna", "tokens_civil") and len(rows) == 1
    if ok:
        r = rows[0]
        rec["tse"] = {k: r[k].strip() for k in ("DS_CARGO", "NR_CANDIDATO", "NM_URNA_CANDIDATO", "NM_CANDIDATO",
                                                 "SG_PARTIDO", "DS_OCUPACAO", "SQ_CANDIDATO")}
        rec["match_how"] = regra
        sig = CARGO_SIGLA.get(r["DS_CARGO"])
        id_base = f"{sig}_{r['NR_CANDIDATO']}" if sig else None
        if id_base in ids_base:
            rec["destino"] = "deputados" if sig == "DE" else "outros"
            rec["chave"] = r["NR_CANDIDATO"] if sig == "DE" else id_base
        elif r["DS_CARGO"] == "VICE-GOVERNADOR" and (r["NR_CANDIDATO"], norm(r["NM_URNA_CANDIDATO"])) in vices_base:
            rec["destino"] = "vices"
            rec["chave"] = vices_base[(r["NR_CANDIDATO"], norm(r["NM_URNA_CANDIDATO"]))]
        else:
            pend.append((nome, d["siglaPartido"], "candidatura do TSE fora de base.json",
                         [(r["DS_CARGO"], r["NR_CANDIDATO"], r["NM_URNA_CANDIDATO"])]))
    else:
        pend.append((nome, d["siglaPartido"], regra or "sem candidatura encontrada",
                     [(r["DS_CARGO"], r["NR_CANDIDATO"], r["NM_URNA_CANDIDATO"], r["NM_CANDIDATO"], r["SG_PARTIDO"])
                      for r in rows]))
    out.append(rec)
    t = rec["tse"]
    print(f"{d['idDeputado']:>5} {nome:<26} {d['siglaPartido']:<13}",
          f"-> {rec['destino']}:{rec['chave']} [{regra}] {t['NM_URNA_CANDIDATO']} | {t['NM_CANDIDATO']} | {t['DS_OCUPACAO']}"
          if rec["destino"] else f"-> SEM CASAMENTO ({regra})")

# duas pessoas da lista oficial nunca podem cair na mesma candidatura
chaves = [(r["destino"], r["chave"]) for r in out if r["destino"]]
assert len(chaves) == len(set(chaves)), "candidatura casada com mais de um deputado"

json.dump(out, open(os.path.join(HERE, "cache", "deputados_match.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print()
print("lista oficial:", len(out), "| casados:", len(chaves),
      "|", {k: sum(1 for r in out if r["match_how"] == k) for k in ("nome_civil", "nome_urna", "tokens_civil")},
      "|", {k: sum(1 for r in out if r["destino"] == k) for k in ("deputados", "outros", "vices")})
print("pendências (sem casamento ou ambíguas):", len(pend))
for p in pend:
    print("  ", p)
