"""Passo 2: atuação oficial dos deputados estaduais em exercício (ALRS) que concorrem em 2026.
Requer cache/deputados_match.json (gerado por 01_deputados.py).

Para cada deputado casado com uma candidatura, coleta só o que o portal da Assembleia publica:
  - comissões em funcionamento em que é Presidente, Vice-Presidente ou Titular (não conta Suplente);
  - frentes parlamentares da 56ª legislatura em que aparece como Presidente na tabela oficial
    (a tabela NÃO lista os demais integrantes);
  - projetos (PL, PLC, PEC) de 2023 a 2026 listados na página de proposições do parlamentar, isto é,
    aqueles em que ele é o primeiro signatário.
Nada aqui é interpretação: ementas e títulos são copiados como estão na fonte.
Saída: ../dep_estadual_atuacao.json
"""
import html
import json
import os
import re
import unicodedata

from alrs_http import get_json, get_text, FRENTES_URL, PORTAL, HERE

OUT = os.path.join(HERE, "..", "dep_estadual_atuacao.json")
COLETADO_EM = "2026-10-03"

TIPOS = ("PL", "PLC", "PEC")   # projeto de lei, projeto de lei complementar, proposta de emenda à Constituição
ANOS = range(2023, 2027)       # anos da 56ª legislatura cobertos pela lista
MAX_PROP = 30                  # teto de projetos por deputado no arquivo (os mais recentes); total real em n_proposicoes
MAX_EMENTA = 240
LIMITE_BYTES = 450_000


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", s)).strip()


def limpa(frag):
    """Texto de um fragmento HTML: sem tags, entidades resolvidas, espaços normalizados.
    O texto sai em Unicode NFC: a fonte traz, aqui e ali, letra + acento combinante (U+0301) no lugar da letra
    acentuada; o desenho na tela é o mesmo, mas uma busca por palavra-chave ("artifícios") não acharia o texto."""
    frag = re.sub(r"<br\s*/?>", " ", frag)
    t = html.unescape(re.sub(r"<[^>]+>", "", frag)).replace("\xa0", " ")
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", t).strip())


def dist1(a, b):
    """True se a e b diferem em no máximo um caractere (troca, inserção ou remoção)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i + 1:] == b[i + 1:] if len(a) == len(b) else a[i:] == b[i + 1:]


deps = json.load(open(os.path.join(HERE, "cache", "deputados_match.json"), encoding="utf-8"))
por_nome = {norm(d["nome_parlamentar"]): d["id_oficial"] for d in deps}   # toda a lista oficial, casados ou não
assert len(por_nome) == len(deps)

# ---------------------------------------------------------------------------------------------------------
# Comissões: /listarComissoes (as que estão em funcionamento) + página de composição de cada uma
# ---------------------------------------------------------------------------------------------------------
CARD = re.compile(r'<div class="card-composicao">.*?<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>', re.S)
comissoes_de = {}   # id_oficial -> [nome da comissão]
papeis, fora_da_lista = {}, set()
for c in get_json("/listarComissoes")["lista"]:
    nome_com = unicodedata.normalize("NFC", re.sub(r"\s+", " ", c["nomeComissao"]).strip())
    pagina = get_text(f"/comissoes-parlamentares/{c['idComissao']}/composicao")
    cards = CARD.findall(pagina)
    assert cards, f"composição vazia: {nome_com}"
    for nome, papel in cards:
        nome, papel = limpa(nome), limpa(papel)
        m = re.match(r"(.+?)\s*\(([^()]*)\)$", papel)   # "Titular (PT)"
        cargo = (m.group(1) if m else papel).strip()
        papeis[cargo] = papeis.get(cargo, 0) + 1
        dep_id = por_nome.get(norm(nome))
        if dep_id is None:
            fora_da_lista.add(nome)
            continue
        if cargo.lower() != "suplente":
            comissoes_de.setdefault(dep_id, []).append(nome_com)
    print("comissão", c["idComissao"], nome_com, "|", len(cards), "integrantes")
print("papéis encontrados:", papeis)
print("integrantes de comissão fora da lista de deputados em exercício:", sorted(fora_da_lista))

# ---------------------------------------------------------------------------------------------------------
# Frentes parlamentares: tabela HTML mantida à mão no site antigo (N., Nome, Data, Presidente, Requerimento)
# ---------------------------------------------------------------------------------------------------------
RISCADO = re.compile(r"<(span)[^>]*line-through[^>]*>.*?</\1>|<(s|strike|del)\b[^>]*>.*?</\2>", re.S | re.I)


def celula(td, sem_riscado=True):
    """Texto de uma célula, descartando trechos riscados (frente extinta / presidente substituído) e as
    chamadas de nota (¹ ² ³ ⁴, que na fonte aparecem como caractere, entidade HTML ou <sup>)."""
    if sem_riscado:
        td = RISCADO.sub(" ", td)
    td = re.sub(r"<sup>.*?</sup>", " ", td, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"[¹²³⁴]", " ", limpa(td))).strip()


pag = get_text(FRENTES_URL)
ini = pag.index("Frentes Parlamentares da 56")
fim = pag.index("Frentes Parlamentares da 55", ini)
frentes_titulo, frentes_de = {}, {}   # id -> título ; id_oficial -> [ids]
sem_dono, corrigidos, extintas, de_outros = [], [], 0, 0
for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", pag[ini:fim], re.S):
    tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
    if len(tds) != 5:
        continue
    num, titulo, presid = celula(tds[0]), celula(tds[1]), celula(tds[3])
    if not num.isdigit() or not titulo:
        if celula(tds[0], False).isdigit():
            extintas += 1      # número ou título riscado: requerimento cancelado ou frente extinta
        continue
    num = int(num)
    assert num not in frentes_titulo, f"frente repetida: {num}"
    frentes_titulo[num] = titulo
    alvo = norm(presid)
    dep_id = por_nome.get(alvo)
    if dep_id is None and alvo:
        # a tabela tem erros de digitação ("Capttão Martim"); aceita só diferença de UM caractere e alvo único
        perto = [n for n in por_nome if dist1(n, alvo)]
        if len(perto) == 1:
            dep_id = por_nome[perto[0]]
            corrigidos.append((num, presid, perto[0]))
    if dep_id is None:
        if any(n in alvo for n in por_nome):
            sem_dono.append((num, presid, titulo))   # cita deputado atual, mas a célula é ambígua (dois nomes)
        else:
            de_outros += 1                           # presidida por quem não está na lista de exercício
        continue
    frentes_de.setdefault(dep_id, []).append(num)
print("frentes da 56ª legislatura ativas na tabela:", len(frentes_titulo), "| riscadas (extintas/canceladas):", extintas,
      "| presididas por quem não está em exercício:", de_outros)
print("grafias corrigidas (1 caractere):", corrigidos)
print("células de presidente ambíguas, NÃO atribuídas:", sem_dono)

# ---------------------------------------------------------------------------------------------------------
# Proposições: tabela HTML de /deputados/{id}/proposicoes (todas as linhas vêm na página)
# ---------------------------------------------------------------------------------------------------------
LINHA = re.compile(r'<tr>\s*<td>\s*<a href="([^"]+)">\s*(.*?)\s*</a>\s*</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>'
                   r'\s*<td>(.*?)</td>\s*<td class="proposicao-ementa">(.*?)</td>\s*</tr>', re.S)


def projetos(dep):
    """Projetos (TIPOS, ANOS) em que o deputado é o primeiro signatário, do mais recente para o mais antigo."""
    pagina = get_text(f"/deputados/{dep['id_oficial']}/proposicoes")
    linhas = LINHA.findall(pagina)
    assert len(linhas) == pagina.count("<tr>") - 1, f"tabela irregular: {dep['nome_parlamentar']}"
    out = []
    for href, rotulo, proponente, _situacao, _tramitacao, ementa in linhas:
        tipo, nro, ano = limpa(rotulo).split()
        if tipo not in TIPOS or int(ano) not in ANOS:
            continue
        # a página só deve trazer proposições em que o próprio parlamentar encabeça a autoria
        m = re.match(r"Deputado\(a\) (.*?)(?: \+ \d+ Deputado\(s\))?$", limpa(proponente))
        assert m and norm(m.group(1)) == norm(dep["nome_parlamentar"]), (dep["nome_parlamentar"], proponente)
        # Algumas ementas vêm com entidade numérica duplamente escapada ("&amp;#8722;"); resolve só essas.
        e = limpa(re.sub(r"&#(?:\d+|x[0-9a-fA-F]+);", lambda m: html.unescape(m.group(0)), limpa(ementa)))
        if len(e) > MAX_EMENTA:
            e = e[:MAX_EMENTA].rstrip() + "…"
        out.append((int(ano), int(nro), {"t": f"{tipo} {nro}/{ano}", "e": e, "id": href.rsplit("/", 1)[-1],
                                         "u": PORTAL + href}))
    out.sort(key=lambda x: (-x[0], -x[1], x[2]["t"]))
    return [p for _, _, p in out]


def montar(dep):
    props = projetos(dep)
    fr = sorted(frentes_de.get(dep["id_oficial"], []))
    return {"id_oficial": dep["id_oficial"], "nome_parlamentar": dep["nome_parlamentar"],
            "frentes": fr, "frentes_coord": fr,   # a fonte só publica quem preside; ver notas
            "comissoes": comissoes_de.get(dep["id_oficial"], []),
            "temas": [],                           # o portal não classifica as proposições por tema
            "n_proposicoes": len(props), "proposicoes": props[:MAX_PROP]}


blocos = {"deputados": {}, "outros": {}, "vices": {}}
for d in deps:
    if d["destino"]:
        obj = montar(d)
        if d["destino"] == "vices":
            obj = {"cargo_2026": d["tse"]["DS_CARGO"], "nm_urna": d["tse"]["NM_URNA_CANDIDATO"], **obj}
        blocos[d["destino"]][d["chave"]] = obj

todos = [o for b in blocos.values() for o in b.values()]
usadas = sorted({f for o in todos for f in o["frentes"]})
n_tot = sum(o["n_proposicoes"] for o in todos)
n_arq = sum(len(o["proposicoes"]) for o in todos)
tokens = [d for d in deps if d["match_how"] == "tokens_civil"]

# As notas vão para a tela do eleitor ("Como estes dados foram coletados"): linguagem comum, sem nomes de
# campos do JSON. Detalhes de formato para quem mantém o arquivo:
#   - 'frentes' e 'frentes_coord' são sempre iguais (a fonte só publica quem PRESIDE cada frente);
#   - 'temas' é sempre [] (o portal não classifica as proposições por tema);
#   - 'n_proposicoes' é o total real e 'proposicoes' traz no máximo MAX_PROP itens;
#   - 'vices' (chave extra) guarda deputados em exercício que concorrem a vice-governador, indexados pelo id
#     da chapa em base.json; build_html.py não lê essa chave, e os dados nunca são do titular da chapa.
notas = [
    f"Cobre só os {len(deps)} deputados em exercício na lista oficial do portal na data da coleta. Quem exerceu "
    "mandato na 56ª legislatura (2023-2027) e não estava em exercício nessa data (licenciados, suplentes que já "
    "saíram) não aparece; a falta destes dados não indica que a pessoa nunca foi deputada estadual.",
    "Projetos: só projetos de lei (PL), projetos de lei complementar (PLC) e propostas de emenda à Constituição "
    "(PEC) de 2023 a 2026 listados na página de proposições do parlamentar, isto é, aqueles em que ele é o primeiro "
    "signatário (coautorias encabeçadas por outro deputado não entram). Entram projetos em qualquer situação (em "
    "tramitação, aprovados, retirados, arquivados): estar na lista não significa que o projeto foi aprovado. "
    "Requerimentos, pedidos de audiência pública e projetos de resolução ficaram de fora.",
    f"A lista traz no máximo {MAX_PROP} projetos por deputado, os mais recentes (ano e número maiores primeiro); o "
    f"total informado é o número real. No conjunto, estão listados {n_arq} de {n_tot} projetos: quem apresentou "
    f"mais de {MAX_PROP} tem projetos mais antigos que não aparecem aqui, nem numa busca por palavra-chave.",
    f"Ementas copiadas como estão na fonte, cortadas em {MAX_EMENTA} caracteres com '…' quando maiores.",
    "Frentes parlamentares: a tabela oficial só informa quem preside cada frente, não os demais integrantes. Por isso "
    "só aparecem as frentes da 56ª legislatura presididas pelo deputado; a ausência de uma frente NÃO indica que "
    "ele não a integra. Frentes riscadas na tabela (extintas ou com requerimento cancelado) foram desconsideradas; "
    "quando o nome do presidente está riscado e seguido de outro, vale o nome não riscado.",
    "Comissões: só as que o portal lista como em funcionamento, e só onde o deputado é Presidente, Vice-Presidente, "
    "Titular ou tem outra função de membro efetivo (suplências não entram).",
    "Não há resumo por tema: o portal não classifica as proposições por tema.",
    "Ligação com a candidatura no TSE feita pelo nome parlamentar (a fonte não publica nome civil), sempre com "
    "partido igual e resultado único em todo o RS: nome parlamentar igual ao nome civil ou ao nome de urna.",
    "Deputados em exercício que concorrem a vice-governador ficam registrados à parte: os dados são do vice, não do "
    "candidato a governador da chapa.",
]
if tokens:
    notas.append(f"Em {len(tokens)} casos o nome parlamentar difere do nome civil e do nome de urna; a ligação exigiu "
                 "todas as palavras do nome parlamentar no nome civil, partido igual e candidato único no RS: "
                 + "; ".join(f"{d['nome_parlamentar']} = {d['tse']['NM_CANDIDATO']}" for d in tokens) + ".")
if corrigidos:
    notas.append("Na tabela de frentes, nomes de presidente com um caractere de diferença foram atribuídos ao único "
                 "nome parlamentar compatível: "
                 + "; ".join(f"frente {n} ('{a}')" for n, a, _ in corrigidos) + ".")
if sem_dono:
    notas.append("Frentes cuja célula de presidente traz dois nomes não foram atribuídas a ninguém: "
                 + "; ".join(f"frente {n} ('{a}')" for n, a, _ in sem_dono) + ".")

out = {
    "fonte": "Assembleia Legislativa do Estado do Rio Grande do Sul, portal oficial (https://ww4.al.rs.gov.br): "
             "lista de deputados e de comissões (https://ww4.al.rs.gov.br:5000), páginas /deputados/{id}/proposicoes e "
             "/comissoes-parlamentares/{id}/composicao, e tabela de frentes parlamentares "
             "(https://ww3.al.rs.gov.br/deputados/FrentesParlamentares.aspx); candidaturas: TSE consulta_cand_2026_RS.",
    "coletado_em": COLETADO_EM,
    "notas": notas,
    "frentes": {str(f): frentes_titulo[f] for f in usadas},
    "deputados": dict(sorted(blocos["deputados"].items())),
    "outros": dict(sorted(blocos["outros"].items())),
    "vices": dict(sorted(blocos["vices"].items())),
}


def dump(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


# Uma chave de topo por linha e, dentro dos blocos de deputados, um deputado por linha (facilita o diff).
partes = []
for k, v in out.items():
    if k in blocos and v:
        corpo = ",\n".join(f"  {dump(kk)}:{dump(vv)}" for kk, vv in v.items())
        partes.append(f"{dump(k)}:{{\n{corpo}\n}}")
    else:
        partes.append(f"{dump(k)}:{dump(v)}")
texto = "{\n" + ",\n".join(partes) + "\n}\n"
assert json.loads(texto) == out


def confere_textos(o, onde=""):
    """Nenhum texto do arquivo pode sair com entidade HTML, tag, caractere de controle/invisível ou fora de NFC."""
    if isinstance(o, dict):
        for k, v in o.items():
            confere_textos(k, onde + "/" + str(k))
            confere_textos(v, onde + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            confere_textos(v, f"{onde}[{i}]")
    elif isinstance(o, str):
        assert o == unicodedata.normalize("NFC", o), f"fora de NFC: {onde}"
        assert not re.search(r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z]{2,8});|<[A-Za-z/][^>]*>", o), f"HTML em {onde}: {o[:80]}"
        assert not any(unicodedata.category(ch) in ("Cc", "Cf", "Co", "Cs", "Cn") for ch in o), f"controle em {onde}"
        assert o == o.strip() and "  " not in o and "�" not in o, f"espaço ou U+FFFD em {onde}"


confere_textos(out)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(texto)

tam = len(texto.encode("utf-8"))
print()
for bloco in blocos:
    for k, o in out[bloco].items():
        print(f"{bloco:<9} {k:<8} {o['nome_parlamentar']:<26} projetos {len(o['proposicoes']):>2}/{o['n_proposicoes']:<3} "
              f"frentes presididas {len(o['frentes']):>2} | comissões {len(o['comissoes'])}")
print()
print("deputados:", len(out["deputados"]), "| outros:", len(out["outros"]), "| vices:", len(out["vices"]),
      "| frentes citadas:", len(out["frentes"]), "| projetos no arquivo:", n_arq, "de", n_tot,
      "| bytes:", tam)
assert tam < LIMITE_BYTES, f"arquivo com {tam} bytes: reduza MAX_PROP"
