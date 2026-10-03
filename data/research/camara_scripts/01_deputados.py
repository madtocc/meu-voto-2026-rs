"""Passo 1: deputados federais do RS na 57ª legislatura (titulares + suplentes que exerceram)
casados com candidatos a deputado federal 2026 (TSE) por nome civil normalizado.
Saída: cache/deputados_match.json
"""
import csv
import json
import os
import re
import unicodedata

from camara_api import get, get_all, HERE

DATA = os.path.abspath(os.path.join(HERE, "..", ".."))


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", s)).strip()


# --- TSE ---
cand = list(csv.DictReader(open(os.path.join(DATA, "consulta_cand_2026_RS.csv"), encoding="latin1"), delimiter=";"))
comp = {r["SQ_CANDIDATO"]: r for r in csv.DictReader(
    open(os.path.join(DATA, "compl", "consulta_cand_complementar_2026_RS.csv"), encoding="latin1"), delimiter=";")}
dfed = [r for r in cand if r["DS_CARGO"] == "DEPUTADO FEDERAL"]
for r in dfed:
    c = comp.get(r["SQ_CANDIDATO"], {})
    r["ST_REELEICAO"] = c.get("ST_REELEICAO")
    r["SITUACAO_TOT"] = c.get("DS_SITUACAO_CANDIDATO_TOT")
by_civil = {}
for r in dfed:
    by_civil.setdefault(norm(r["NM_CANDIDATO"]), []).append(r)

# --- Câmara ---
ids = {}
for d in get_all("/deputados", {"siglaUf": "RS", "idLegislatura": 57, "ordem": "ASC", "ordenarPor": "nome"}):
    ids[d["id"]] = d["nome"]
atuais = {d["id"] for d in get_all("/deputados", {"siglaUf": "RS", "ordem": "ASC", "ordenarPor": "nome"})}
for i in atuais:
    ids.setdefault(i, None)

out = []
for dep_id in sorted(ids):
    det = get(f"/deputados/{dep_id}")["dados"]
    hist = get(f"/deputados/{dep_id}/historico")["dados"]
    civil = det.get("nomeCivil")
    us = det.get("ultimoStatus", {})
    matches = by_civil.get(norm(civil), [])
    # fallback: nome eleitoral == nome de urna (só se único)
    how = "nome_civil"
    if not matches:
        how = "nome_urna"
        matches = [r for r in dfed if norm(r["NM_URNA_CANDIDATO"]) == norm(us.get("nomeEleitoral") or us.get("nome"))]
    rec = {
        "id_camara": dep_id,
        "nome_parlamentar": us.get("nome"),
        "nome_civil": civil,
        "partido_camara": us.get("siglaPartido"),
        "situacao_atual": us.get("situacao"),
        "condicao": us.get("condicaoEleitoral"),
        "em_exercicio_hoje": dep_id in atuais,
        "historico": [{"dataHora": h["dataHora"], "situacao": h["situacao"], "condicao": h["condicaoEleitoral"],
                       "status": h["descricaoStatus"], "partido": h["siglaPartido"]} for h in hist],
        "match_how": how if matches else None,
        "tse": [{k: m[k] for k in ("SQ_CANDIDATO", "NR_CANDIDATO", "NM_URNA_CANDIDATO", "NM_CANDIDATO", "SG_PARTIDO",
                                    "DS_SITUACAO_CANDIDATURA", "ST_REELEICAO", "SITUACAO_TOT")} for m in matches],
    }
    out.append(rec)
    print(dep_id, us.get("nome"), "|", civil, "|", us.get("situacao"), "| atual" if dep_id in atuais else "",
          "->", [(m["NR_CANDIDATO"], m["NM_URNA_CANDIDATO"], m["SG_PARTIDO"], m["SITUACAO_TOT"]) for m in matches], how if matches else "")

json.dump(out, open(os.path.join(HERE, "cache", "deputados_match.json"), "w"), ensure_ascii=False, indent=1)
print("casados:", sum(1 for r in out if r["tse"]), "de", len(out))
