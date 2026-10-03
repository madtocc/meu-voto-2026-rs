"""Passo 3: atuação legislativa registrada pela Câmara (frentes parlamentares, comissões permanentes,
proposições de autoria e seus temas) dos deputados do RS da 57ª legislatura que concorrem em 2026.
Requer ../dep_federal_votos.json (gerado por 02_votos.py).
Saída: ../dep_federal_atuacao.json

Só entra o que a API devolve: nada de busca na web, notícia ou interpretação sobre o que cada um "defende".
Pode ser rodado de novo: as respostas ficam em cache/ (para recoletar, apague o cache e atualize COLETADO_EM).
"""
import json
import os
import unicodedata
import urllib.error
from collections import Counter

from camara_api import get, get_all, HERE

IN = os.path.join(HERE, "..", "dep_federal_votos.json")
OUT = os.path.join(HERE, "..", "dep_federal_atuacao.json")

COLETADO_EM = "2026-10-03"      # data da coleta (o cache congela as respostas desse dia)
INICIO = "2023-02-01"           # início da 57ª legislatura
LEGISLATURA = 57
TIPOS = ("PL", "PLP", "PEC")    # projeto de lei, projeto de lei complementar, proposta de emenda à Constituição
EMENTA_MAX = 240                # corte da ementa (caracteres)
LIMITE_BYTES = 450_000          # tamanho máximo do arquivo de saída
COD_COMISSAO_PERMANENTE = 2     # codTipoOrgao em /orgaos/{id}
CARGO_ID = {"SENADOR": "SEN", "GOVERNADOR": "GOV"}  # mesmo mapeamento do build_html.py

nao_encontrados = []  # sub-recursos que responderam 404


def dados(path):
    """'dados' de um recurso sem paginação; 404 vira lista vazia (e fica anotado)."""
    try:
        r = get(path)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        nao_encontrados.append(path)
        return []
    assert not [l for l in r.get("links", []) if l.get("rel") == "next"], path
    return r.get("dados") or []


def limpa(s):
    """Texto oficial sem quebras de linha nem espaços repetidos (o conteúdo não muda)."""
    return " ".join((s or "").split())


def corta(s, n=EMENTA_MAX):
    s = limpa(s)
    return s if len(s) <= n else s[:n].rstrip() + "…"


def chave_ordem(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


# --- quem entra: candidatos a dep. federal + ex-deputados que concorrem a senador/governador ---
votos = json.load(open(IN))
alvos = [("deputados", str(d["nr_candidato"]), d["id_camara"], d["nome_parlamentar"]) for d in votos["deputados"]]
fora = []
for o in votos.get("outros_cargos_2026", []):
    if o["cargo_2026"] in CARGO_ID:
        alvos.append(("outros", f"{CARGO_ID[o['cargo_2026']]}_{o['nr_candidato']}", o["id_camara"], o["nome_parlamentar"]))
    else:  # suplente de senador: não é o candidato da chave SEN_<nr>
        fora.append(f"{o['nome_parlamentar']} ({o['cargo_2026']})")
assert len({a[1] for a in alvos}) == len(alvos), "chave repetida"

# --- frentes parlamentares da 57ª legislatura ---
titulo_frente = {}
frentes_dep = {}
for _, chave, dep_id, nome in alvos:
    fr = [f for f in dados(f"/deputados/{dep_id}/frentes") if f["idLegislatura"] == LEGISLATURA]
    for f in fr:
        titulo_frente[f["id"]] = limpa(f["titulo"])
    frentes_dep[dep_id] = sorted({f["id"] for f in fr}, key=lambda i: (chave_ordem(titulo_frente[i]), i))
print("frentes distintas:", len(titulo_frente))

# cargo em cada frente (/frentes/{id}/membros traz 'titulo': Coordenador, Presidente, Membro...)
ids_alvo = {a[2] for a in alvos}
cargo_frente = {}       # (id_frente, id_deputado) -> título diferente de "Membro"
fora_da_lista = []      # consta em /deputados/{id}/frentes mas não em /frentes/{id}/membros
for n, fid in enumerate(sorted(titulo_frente), 1):
    membros = dados(f"/frentes/{fid}/membros")
    presentes = set()
    for m in membros:
        if m.get("id") not in ids_alvo:
            continue
        presentes.add(m["id"])
        t = limpa(m.get("titulo"))
        if t and t.lower() != "membro":
            cargo_frente.setdefault((fid, m["id"]), t)
    fora_da_lista += [(fid, d) for d in ids_alvo if fid in frentes_dep[d] and d not in presentes]
    if n % 50 == 0:
        print("  membros de frentes:", n, "/", len(titulo_frente))
print("cargos em frentes:", Counter(cargo_frente.values()).most_common(), "| fora da lista de membros:", len(fora_da_lista))

# --- comissões permanentes em que é titular hoje ---
orgao = {}
comissoes_dep = {}
titulos_comissao = Counter()
for _, chave, dep_id, nome in alvos:
    nomes = []
    for o in get_all(f"/deputados/{dep_id}/orgaos", {"itens": 100, "ordem": "ASC", "ordenarPor": "dataInicio"}):
        if o.get("dataFim") or limpa(o.get("titulo")).lower() == "suplente":
            continue
        if o["idOrgao"] not in orgao:
            orgao[o["idOrgao"]] = get(f"/orgaos/{o['idOrgao']}")["dados"]
        og = orgao[o["idOrgao"]]
        if og.get("codTipoOrgao") != COD_COMISSAO_PERMANENTE or og.get("dataFim"):
            continue
        titulos_comissao[limpa(o.get("titulo"))] += 1
        nm = limpa(og.get("nome") or o.get("nomeOrgao"))
        if nm not in nomes:
            nomes.append(nm)
    comissoes_dep[dep_id] = sorted(nomes, key=chave_ordem)
print("títulos em comissões permanentes:", dict(titulos_comissao))

# --- proposições (PL, PLP, PEC) em que é o primeiro signatário ---
autores_cache = {}
varios_primeiros = set()   # proposições com mais de um autor marcado como 1ª assinatura
sem_autores = set()


def autores(pid):
    if pid not in autores_cache:
        a = dados(f"/proposicoes/{pid}/autores")
        autores_cache[pid] = a
        if not a:
            sem_autores.add(pid)
        if sum(1 for x in a if x.get("ordemAssinatura") == 1 and x.get("proponente") == 1) > 1:
            varios_primeiros.add(pid)
    return autores_cache[pid]


def primeiro_signatario(pid, dep_id):
    fim = f"/deputados/{dep_id}"
    return any((x.get("uri") or "").endswith(fim) and x.get("ordemAssinatura") == 1 and x.get("proponente") == 1
               for x in autores(pid))


props_dep, temas_dep, listadas_dep = {}, {}, {}
for n, (_, chave, dep_id, nome) in enumerate(alvos, 1):
    lista = get_all("/proposicoes", {"idDeputadoAutor": dep_id, "siglaTipo": ",".join(TIPOS),
                                     "dataApresentacaoInicio": INICIO, "ordem": "ASC", "ordenarPor": "id", "itens": 100})
    lista = list({p["id"]: p for p in lista}.values())
    assert all(p["siglaTipo"] in TIPOS and p["dataApresentacao"][:10] >= INICIO for p in lista), chave
    listadas_dep[dep_id] = len(lista)
    minhas = [p for p in lista if primeiro_signatario(p["id"], dep_id)]
    minhas.sort(key=lambda p: (p["dataApresentacao"], p["id"]), reverse=True)  # mais recentes primeiro
    temas = Counter()
    for p in minhas:
        for t in {limpa(t.get("tema")) for t in dados(f"/proposicoes/{p['id']}/temas")}:
            if t:
                temas[t] += 1
    props_dep[dep_id] = [{"t": f"{p['siglaTipo']} {p['numero']}/{p['ano']}", "e": corta(p.get("ementa")), "id": p["id"],
                          "u": f"https://www.camara.leg.br/propostas-legislativas/{p['id']}"} for p in minhas]
    temas_dep[dep_id] = sorted(([t, c] for t, c in temas.items()), key=lambda x: (-x[1], chave_ordem(x[0])))
    print(f"  [{n}/{len(alvos)}] {chave} {nome}: listadas {len(lista)}, 1ª assinatura {len(minhas)}, temas {len(temas)}")


# --- saída ---
def montar(teto):
    out = {"fonte": "API de Dados Abertos da Câmara dos Deputados (https://dadosabertos.camara.leg.br/api/v2)",
           "coletado_em": COLETADO_EM, "notas": [], "frentes": {}, "deputados": {}, "outros": {}}
    usadas = set()
    for grupo, chave, dep_id, nome in alvos:
        props = props_dep[dep_id]
        coord = [f for f in frentes_dep[dep_id] if (f, dep_id) in cargo_frente]
        usadas.update(frentes_dep[dep_id])
        out[grupo][chave] = {
            "id_oficial": dep_id,
            "nome_parlamentar": nome,
            "frentes": frentes_dep[dep_id],
            "frentes_coord": coord,
            "comissoes": comissoes_dep[dep_id],
            "temas": temas_dep[dep_id],
            "n_proposicoes": len(props),
            "proposicoes": props if teto is None else props[:teto],
        }
    out["frentes"] = {str(f): titulo_frente[f] for f in sorted(usadas, key=lambda i: (chave_ordem(titulo_frente[i]), i))}
    total = sum(len(p) for p in props_dep.values())
    listadas = sum(len(d["proposicoes"]) for g in ("deputados", "outros") for d in out[g].values())
    out["notas"] = [
        f"Cobre só quem exerceu mandato de deputado federal pelo RS na 57ª legislatura (2023-2026) e concorre em 2026: "
        f"{len(out['deputados'])} candidatos a deputado federal e {len(out['outros'])} a senador ou governador. "
        "Sobre quem não aparece aqui nada foi coletado: isso não diz nada sobre a atuação da pessoa em outros cargos nem em "
        "mandatos anteriores na própria Câmara (há candidatos de 2026 que foram deputados federais antes de 2023 e não estão "
        "neste arquivo).",
        f"'proposicoes' = PL, PLP e PEC apresentados de {INICIO} a {COLETADO_EM} em que o parlamentar é o primeiro "
        "signatário (ordemAssinatura = 1 e proponente = 1 em /proposicoes/{id}/autores, consultado proposição por "
        "proposição na API; os arquivos anuais não foram usados). Coautorias e apoiamentos não contam como autoria.",
        f"'e' é a ementa oficial, sem alteração de texto, cortada em {EMENTA_MAX} caracteres com '…' quando é maior. "
        "Apresentar uma proposição não significa que ela foi aprovada.",
        (f"Sem corte: todas as {total} proposições de primeira assinatura estão listadas." if teto is None else
         f"Teto de {teto} proposições listadas por parlamentar (as mais recentes); 'n_proposicoes' traz o total real. "
         f"Total real: {total}; listadas: {listadas}."),
        "'temas' = classificação temática oficial da Câmara (/proposicoes/{id}/temas) de todas as proposições de primeira "
        "assinatura (total real, não só as listadas). Uma proposição pode ter mais de um tema ou nenhum.",
        f"'frentes' = frentes parlamentares da {LEGISLATURA}ª legislatura em que o parlamentar consta em /deputados/{{id}}/frentes. "
        "Integrar uma frente é ter assinado a adesão a ela; o registro não mede participação nem votos. Na data da coleta, a "
        "página pública das frentes no portal da Câmara listava só os signatários em exercício do mandato; quem está fora do "
        "exercício consta apenas no registro da API.",
        "'frentes_coord' = frentes em que /frentes/{id}/membros registra título diferente de 'Membro'"
        + (f" (títulos encontrados: {', '.join(sorted(set(cargo_frente.values())))})." if cargo_frente else "."),
        "'comissoes' = comissões permanentes em que consta, na data da coleta, como titular ou em cargo da mesa da comissão "
        "(/deputados/{id}/orgaos sem data de fim). Suplências, comissões especiais, externas e mistas ficam de fora; "
        "quem não está em exercício do mandato fica com lista vazia.",
    ]
    if fora:
        out["notas"].append("Não incluído(s) por concorrer(em) como suplente de senador: " + "; ".join(fora) + ".")
    return out


def serializar(out):
    """JSON compacto, com uma chave de topo por linha e um parlamentar/frente por linha."""
    def c(v):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    partes = []
    for k, v in out.items():
        if isinstance(v, dict) and v:
            itens = ",\n".join(f"  {c(kk)}:{c(vv)}" for kk, vv in v.items())
            partes.append(f" {c(k)}:{{\n{itens}\n }}")
        else:
            partes.append(f" {c(k)}:{c(v)}")
    return "{\n" + ",\n".join(partes) + "\n}\n"


teto = None
texto = serializar(montar(teto))
if len(texto.encode("utf-8")) > LIMITE_BYTES:
    teto = max(len(p) for p in props_dep.values())
    while teto > 1 and len(texto.encode("utf-8")) > LIMITE_BYTES:
        teto -= 1
        texto = serializar(montar(teto))
with open(OUT, "w", encoding="utf-8") as f:
    f.write(texto)

# --- conferência: relê o arquivo e confere as chaves ---
final = json.load(open(OUT, encoding="utf-8"))
nrs = {str(d["nr_candidato"]) for d in votos["deputados"]}
assert set(final["deputados"]) <= nrs, set(final["deputados"]) - nrs
assert set(final["outros"]) <= {f"{CARGO_ID[o['cargo_2026']]}_{o['nr_candidato']}"
                                for o in votos.get("outros_cargos_2026", []) if o["cargo_2026"] in CARGO_ID}
print(f"\n{'chave':<8} {'nome':<28} {'frentes':>7} {'coord':>5} {'comis':>5} {'1ªass':>5} {'listad':>6} {'temas':>5}")
for grupo in ("deputados", "outros"):
    for chave, d in final[grupo].items():
        assert set(d["frentes_coord"]) <= set(d["frentes"]) and all(str(f) in final["frentes"] for f in d["frentes"])
        assert len(d["proposicoes"]) <= d["n_proposicoes"] and all(len(p["e"]) <= EMENTA_MAX + 1 for p in d["proposicoes"])
        print(f"{chave:<8} {d['nome_parlamentar'][:28]:<28} {len(d['frentes']):>7} {len(d['frentes_coord']):>5} "
              f"{len(d['comissoes']):>5} {d['n_proposicoes']:>5} {len(d['proposicoes']):>6} {len(d['temas']):>5}")
print("teto por parlamentar:", teto, "| listagens da API (com coautorias):", sum(listadas_dep.values()),
      "| proposições distintas consultadas:", len(autores_cache))
print("mais de um autor com 1ª assinatura:", len(varios_primeiros), sorted(varios_primeiros)[:10],
      "| sem autores:", len(sem_autores), "| 404:", len(nao_encontrados), nao_encontrados[:5])
print("frentes no arquivo:", len(final["frentes"]), "| fora da lista de membros:", fora_da_lista[:10])
print("fora (suplentes):", fora)
print("arquivo:", os.path.abspath(OUT), os.path.getsize(OUT), "bytes")
