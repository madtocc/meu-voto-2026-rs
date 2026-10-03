"""Monta base.json com os dados oficiais do TSE para o eleitor de Porto Alegre/RS."""
import base64
import csv
import io
import json
import os
from collections import defaultdict

from PIL import Image

D = os.path.dirname(os.path.abspath(__file__))
CARGOS = {
    'PRESIDENTE': 'PRES', 'GOVERNADOR': 'GOV', 'SENADOR': 'SEN',
    'DEPUTADO FEDERAL': 'DF', 'DEPUTADO ESTADUAL': 'DE',
}
COMPANHEIROS = {'VICE-PRESIDENTE': 'PRES', 'VICE-GOVERNADOR': 'GOV', '1º SUPLENTE': 'SEN', '2º SUPLENTE': 'SEN'}


def load(name):
    with open(os.path.join(D, name), encoding='latin1') as f:
        return list(csv.DictReader(f, delimiter=';'))


def clean(v):
    return None if v in ('#NULO', '#NE', '#NULO#', '', '-1', '-3') else v


def thumb(path, size):
    if not os.path.exists(path):
        return None
    im = Image.open(path).convert('RGB')
    w, h = im.size
    side = min(w, h)
    top = max(0, int((h - side) * 0.25))
    im = im.crop(((w - side) // 2, top, (w - side) // 2 + side, top + side)).resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=72 if size > 100 else 60, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


cands, extras = [], defaultdict(list)
for uf in ('BR', 'RS'):
    comp = {x['SQ_CANDIDATO']: x for x in load(f'compl/consulta_cand_complementar_2026_{uf}.csv')}
    bens = defaultdict(float)
    for b in load(f'bem_candidato_2026_{uf}.csv'):
        bens[b['SQ_CANDIDATO']] += float(b['VR_BEM_CANDIDATO'].replace('.', '').replace(',', '.') or 0)
    redes = defaultdict(list)
    for r in load(f'rede_social_candidato_2026_{uf}.csv'):
        redes[r['SQ_CANDIDATO']].append(r['DS_URL'].strip())
    for x in load(f'consulta_cand_2026_{uf}.csv'):
        sq, c = x['SQ_CANDIDATO'], comp[x['SQ_CANDIDATO']]
        cargo = x['DS_CARGO']
        base = {
            'sq': sq, 'nr': x['NR_CANDIDATO'], 'urna': x['NM_URNA_CANDIDATO'].strip(),
            'nome': x['NM_CANDIDATO'].strip(), 'partido': x['SG_PARTIDO'],
            'situacao': clean(c['DS_SITUACAO_CANDIDATO_TOT']) or 'SEM REGISTRO',
            'na_urna': c['ST_CANDIDATO_INSERIDO_URNA'] == 'SIM',
            'ocupacao': x['DS_OCUPACAO'],
        }
        if cargo in COMPANHEIROS:
            extras[(COMPANHEIROS[cargo], x['NR_CANDIDATO'])].append(dict(base, cargo=cargo))
            continue
        if cargo not in CARGOS:
            continue
        fed = clean(x['SG_FEDERACAO'])
        cands.append(dict(
            base,
            cargo=CARGOS[cargo],
            id=f"{CARGOS[cargo]}_{x['NR_CANDIDATO']}",
            federacao=fed and f"{x['NM_FEDERACAO']} ({x['DS_COMPOSICAO_FEDERACAO']})",
            coligacao=None if x['NM_COLIGACAO'] in ('PARTIDO ISOLADO', 'FEDERAÇÃO') else x['NM_COLIGACAO'],
            composicao=x['DS_COMPOSICAO_COLIGACAO'],
            idade=int(c['NR_IDADE_DATA_POSSE']) if clean(c['NR_IDADE_DATA_POSSE']) else None,
            genero=x['DS_GENERO'], raca=x['DS_COR_RACA'], instrucao=x['DS_GRAU_INSTRUCAO'],
            estado_civil=x['DS_ESTADO_CIVIL'],
            naturalidade=f"{c['NM_MUNICIPIO_NASCIMENTO'].title()}/{x['SG_UF_NASCIMENTO']}",
            reeleicao=c['ST_REELEICAO'] == 'S',
            patrimonio=round(bens.get(sq, 0), 2),
            redes=redes.get(sq, []),
            plano=(f'data/prop_br/BR/2026BR{sq}_01.pdf' if uf == 'BR' else f'data/prop_rs/RS/2026RS{sq}_01.pdf')
            if os.path.exists(os.path.join(D, f'prop_{uf.lower()}/{uf}/2026{uf}{sq}_01.pdf')) else None,
            foto=thumb(os.path.join(D, f'fotos/F{uf}{sq}_div.jpg'), 160 if CARGOS[cargo] in ('PRES', 'GOV', 'SEN') else 72),
        ))

# Só quem está na urna; para presidente, o PRTB trocou Marçal por Avalanche (mesmo número).
cands = [c for c in cands if c['na_urna']]
for c in cands:
    c['companheiros'] = [
        {'cargo': e['cargo'], 'urna': e['urna'], 'partido': e['partido'], 'ocupacao': e['ocupacao']}
        for e in sorted(extras.get((c['cargo'], c['nr']), []), key=lambda e: e['cargo'])
        if e['na_urna']
    ] if c['cargo'] in ('PRES', 'GOV', 'SEN') else []

# Legendas (voto no partido) para deputado
legendas = {}
for x in load('consulta_coligacao_2026_RS.csv'):
    if x['DS_CARGO'] in ('DEPUTADO FEDERAL', 'DEPUTADO ESTADUAL'):
        legendas[x['NR_PARTIDO']] = {
            'nr': x['NR_PARTIDO'], 'sigla': x['SG_PARTIDO'], 'nome': x['NM_PARTIDO'],
            'federacao': clean(x['NM_FEDERACAO']),
        }

out = {
    'gerado_em': load('consulta_cand_2026_BR.csv')[0]['DT_GERACAO'] + ' ' + load('consulta_cand_2026_BR.csv')[0]['HH_GERACAO'],
    'candidatos': cands,
    'legendas': sorted(legendas.values(), key=lambda l: int(l['nr'])),
}
with open(os.path.join(D, 'base.json'), 'w') as f:
    json.dump(out, f, ensure_ascii=False)

from collections import Counter
print(Counter(c['cargo'] for c in cands), len(legendas), 'legendas')
print(Counter((c['cargo'], c['situacao']) for c in cands))
print('sem foto:', sum(1 for c in cands if not c['foto']))
print(os.path.getsize(os.path.join(D, 'base.json')) / 1e6, 'MB')
