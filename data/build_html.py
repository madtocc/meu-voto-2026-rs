"""Junta base.json + research/*.json no guia HTML autocontido."""
import base64
import glob
import hashlib
import json
import os
import re
from collections import defaultdict

from build_ia import exporta

D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(D), 'guia-voto-2026.html')
SITE = 'https://meu-voto-2026-bs0.pages.dev'  # o mesmo DOMINIO de publicar.py; a cópia baixada usa para abrir os PDFs

# A página promete que nada sai do navegador; esta política faz o próprio navegador garantir isso.
# O script entra por hash: nada injetado depois do build (nem por dado malformado) consegue rodar.
CSP = ("default-src 'none'; script-src '{script}'; style-src 'unsafe-inline'; img-src data:; "
       "connect-src 'none'; form-action 'none'; base-uri 'none'")

TEMAS = {
    'federal': [
        ('privatizacoes', 'Privatizar estatais (ex.: Petrobras, Correios)', 'Vender ou transferir empresas públicas federais para a iniciativa privada.'),
        ('impostos_ricos', 'Taxar mais altas rendas, lucros/dividendos ou grandes fortunas', 'Aumentar a tributação de quem ganha ou tem mais.'),
        ('ajuste_fiscal', 'Cortar gastos públicos para reduzir impostos e a dívida', 'Ajuste fiscal mais duro, com redução de despesas do governo.'),
        ('programas_sociais', 'Ampliar programas de transferência de renda', 'Ex.: Bolsa Família, auxílios e benefícios sociais.'),
        ('escala_6x1', 'Acabar com a escala 6x1 / reduzir a jornada de trabalho por lei', 'Mudar a lei para reduzir dias ou horas da jornada semanal.'),
        ('armas', 'Facilitar a posse e o porte de armas para cidadãos', 'Regras mais flexíveis para comprar e carregar armas.'),
        ('penas', 'Endurecer penas e/ou reduzir a maioridade penal', 'Punições mais longas, menos benefícios penais, julgar menores como adultos.'),
        ('aborto', 'Ampliar o aborto legal / descriminalizar o aborto', 'Hoje é permitido só em estupro, risco à vida da gestante e anencefalia.'),
        ('anistia_8j', 'Anistiar os condenados pelos atos de 8 de janeiro de 2023', 'Perdão aos condenados pela invasão das sedes dos Três Poderes.'),
        ('stf', 'Limitar os poderes do STF', 'Ex.: restringir decisões individuais, mandato para ministros, impeachment de ministros.'),
        ('ambiente', 'Priorizar proteção ambiental e clima, mesmo com restrições ao agro e à mineração', 'Mais fiscalização, metas climáticas e limites a desmatamento e exploração.'),
        ('redes', 'Regular as plataformas digitais e responsabilizá-las por conteúdos', 'Obrigações para redes sociais sobre desinformação e conteúdo ilegal.'),
    ],
    'estadual': [
        ('banrisul', 'Privatizar o Banrisul', 'O banco estadual hoje é controlado pelo governo do RS.'),
        ('concessoes', 'Ampliar concessões, PPPs e privatizações no estado', 'Passar estradas, serviços e empresas estaduais para gestão privada.'),
        ('icms', 'Reduzir o ICMS e a carga tributária estadual', 'O ICMS é o principal imposto do estado.'),
        ('incentivos', 'Manter ou ampliar incentivos fiscais a empresas', 'Benefícios tributários para atrair ou manter investimentos.'),
        ('servidores', 'Reajustes acima da inflação para servidores', 'Ex.: professores, policiais, saúde.'),
        ('civico_militar', 'Ampliar escolas cívico-militares', 'Escolas com gestão disciplinar feita por militares.'),
        ('licenciamento', 'Flexibilizar o licenciamento ambiental para acelerar obras e investimentos', 'Regras e prazos mais simples para aprovar empreendimentos.'),
        ('divida_uniao', 'Auditar ou contestar a dívida do RS com a União', 'Em vez de seguir pagando nos termos atuais (renegociados via Propag).'),
        ('seguranca_dura', 'Policiamento ostensivo e mais presídios como principal estratégia de segurança', 'Em vez de priorizar prevenção social e inteligência.'),
    ],
}


def norm(s):
    return re.sub(r'\s+', '', s).upper()


def siglas(composicao):
    """'PSB / FEDERAÇÃO X (13-PT / 65-PC do B)' -> {'PSB','PT','PCDOB'}"""
    out = set()
    for tok in re.split(r'[/()]', composicao or ''):
        tok = tok.strip()
        if not tok or tok.startswith('FEDERAÇÃO'):
            continue
        out.add(norm(re.sub(r'^\d+-', '', tok)))
    return out


base = json.load(open(os.path.join(D, 'base.json'), encoding='utf-8'))
# Mesmo cargo e número duas vezes é candidatura substituída (ex.: falecimento): o número passa a ser de quem entrou.
# Sem isto os dois teriam o mesmo id, e escolher um na lista marcaria o outro.
ANULADA = ('FALECIMENTO', 'RENÚNCIA', 'INDEFERIDO')
por_id = {}
for c in base['candidatos']:
    antes = por_id.get(c['id'])
    if antes is None or antes['situacao'] in ANULADA or c['situacao'] not in ANULADA:
        if antes is not None:
            print(f"{c['id']}: {antes['urna']} ({antes['situacao'].lower()}) deu lugar a {c['urna']}")
        por_id[c['id']] = c
base['candidatos'] = [c for c in base['candidatos'] if por_id[c['id']] is c]

research = {}
for p in glob.glob(os.path.join(D, 'research', '*_*.json')):
    if os.path.basename(p).startswith('dep_'):
        continue
    try:
        r = json.load(open(p, encoding='utf-8'))
    except json.JSONDecodeError as e:
        print('JSON inválido:', p, e)
        continue
    research[r['id']] = r

# Posição copiada do programa do partido não é posição do candidato: fica marcada para o guia avisar
for r in research.values():
    for v in (r.get('posicoes') or {}).values():
        if isinstance(v, dict) and ((v.get('nota') or '').lower().startswith('posição do partido')
                                    or (v.get('fonte') or '').lower().startswith('programa do partido')):
            v['proxy'] = True

# Perfis de partido: média das posições dos majoritários que o partido lança ou apoia
maj = [c for c in base['candidatos'] if c['cargo'] in ('PRES', 'GOV', 'SEN') and c['id'] in research]
partidos = {c['partido'] for c in base['candidatos'] if c['cargo'] in ('DF', 'DE')}
perfis = {}
for p in partidos:
    perfil = {'base': {}}
    for escopo, cargos in (('federal', ('PRES', 'SEN')), ('estadual', ('GOV',))):
        refs = [c for c in maj if c['cargo'] in cargos and norm(p) in siglas(c['composicao'] or c['partido'])]
        # o candidato do próprio partido representa o partido melhor do que o de um aliado de coligação
        refs = [c for c in refs if norm(c['partido']) == norm(p)] or refs
        vals = defaultdict(list)
        for c in refs:
            for k, v in (research[c['id']].get('posicoes') or {}).items():
                v = v.get('v') if isinstance(v, dict) else v
                if v is not None:
                    vals[k].append(v)
        # quando as referências divergem muito num tema (2 pontos ou mais), a média não é posição de ninguém: fica sem
        perfil[escopo] = {k: round(sum(v) / len(v), 2) for k, v in vals.items() if max(v) - min(v) < 2}
        # a base é por âmbito: deputado estadual usa só o candidato a governador; federal, presidente e senador
        perfil['base'][escopo] = [f"{c['urna'].title()} ({c['cargo'].replace('PRES', 'Pres.').replace('SEN', 'Sen.').replace('GOV', 'Gov.')})" for c in refs]
    perfis[p] = perfil

votos_df = None
vp = os.path.join(D, 'research', 'dep_federal_votos.json')
if os.path.exists(vp):
    v = json.load(open(vp, encoding='utf-8'))
    cargo_id = {'SENADOR': 'SEN', 'GOVERNADOR': 'GOV'}
    votos_df = {
        'votacoes': v['votacoes'],
        'deputados': {str(d['nr_candidato']): d for d in v['deputados'] if d.get('nr_candidato')},
        'outros': {f"{cargo_id[o['cargo_2026']]}_{o['nr_candidato']}": o for o in v.get('outros_cargos_2026', []) if o['cargo_2026'] in cargo_id},
    }

# Atuação parlamentar (frentes, temas e projetos de autoria) de quem já tem mandato, por casa legislativa
atuacao = {}
for casa, arquivo in (('camara', 'dep_federal_atuacao.json'), ('alrs', 'dep_estadual_atuacao.json')):
    ap = os.path.join(D, 'research', arquivo)
    if os.path.exists(ap):
        a = json.load(open(ap, encoding='utf-8'))
        # só o que o guia mostra ou busca: sem ids internos nem notas de método (essas ficam no arquivo de origem)
        enxuga = lambda d: dict({k: d.get(k) or [] for k in ('frentes', 'frentes_coord', 'comissoes', 'temas')},
                                n_proposicoes=d.get('n_proposicoes', len(d.get('proposicoes') or [])),
                                proposicoes=[{k: pr.get(k) for k in ('t', 'e', 'u')} for pr in d.get('proposicoes') or []])
        atuacao[casa] = {'coletado_em': a.get('coletado_em'), 'frentes': a.get('frentes') or {},
                         'deputados': {k: enxuga(d) for k, d in (a.get('deputados') or {}).items()},
                         'outros': {k: enxuga(d) for k, d in (a.get('outros') or {}).items()}}


def limpa_rede(u):
    """Só links de redes/sites. E-mail e WhatsApp (telefone) ficam de fora da página pública."""
    u = (u or '').strip()
    if not u or ' ' in u or '@' in u.split('/')[0] and '.' in u.split('@')[-1] and '/' not in u:
        return None
    low = u.lower()
    if re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', low) or 'wa.me' in low or 'whatsapp' in low or low.startswith('@'):
        return None
    if u.isupper() or low.startswith('http'):
        u = low if u.isupper() else u
    if not re.match(r'https?://', u, re.I):
        # precisa parecer endereço de verdade (domínio terminado em letras): "fulano.123" é só nome de usuário
        if not re.match(r'(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}(/|$)', u, re.I):
            return None
        u = 'https://' + u
    # as grandes redes atendem em https: não deixa o clique sair em texto aberto
    return re.sub(r'^http://(?=(www\.)?(facebook|instagram|tiktok|youtube|x|twitter|linkedin|threads)\.)', 'https://', u, flags=re.I)


for c in base['candidatos']:
    c['redes'] = list(dict.fromkeys(r for r in map(limpa_rede, c.get('redes') or []) if r))

MANDATOS = {'DEPUTADO': 'deputado(a)', 'VEREADOR': 'vereador(a)', 'SENADOR': 'senador(a)', 'PREFEITO': 'prefeito(a)', 'GOVERNADOR': 'governador(a)'}
for c in base['candidatos']:
    c['mandato'] = MANDATOS.get(c['ocupacao'])
    if votos_df and c['cargo'] == 'DF' and c['nr'] in votos_df['deputados']:
        c['mandato'] = 'deputado(a) federal'
    for casa, cargo, rotulo in (('camara', 'DF', 'deputado(a) federal'), ('alrs', 'DE', 'deputado(a) estadual')):
        a = atuacao.get(casa)
        if a and ((c['cargo'] == cargo and c['nr'] in a['deputados']) or c['id'] in a['outros']):
            c['mandato'] = rotulo

# Formas que o template pressupõe. Se o dado vier diferente, o build para aqui em vez de publicar algo quebrado.
assert len({c['id'] for c in base['candidatos']}) == len(base['candidatos']), 'há candidatos com o mesmo id'
for c in base['candidatos']:
    assert re.fullmatch(r'(PRES|GOV|SEN|DF|DE)_\d+', c['id']), c['id']
    assert re.fullmatch(r'\d{2,5}', c['nr']), c['id']
    assert not c['foto'] or re.fullmatch(r'data:image/jpeg;base64,[A-Za-z0-9+/=]+', c['foto']), c['id']
    assert not c.get('plano') or re.fullmatch(r'data/prop_\w+/\w+/[\w.-]+\.pdf', c['plano']), c['id']
    assert all(re.match(r'https?://', u, re.I) for u in c['redes']), c['id']
    assert type(c.get('patrimonio') or 0) in (int, float) and type(c.get('idade') or 0) is int, c['id']
for r in research.values():
    assert (r.get('detalhamento') or {}).get('nota') in (None, 1, 2, 3, 4, 5), r['id']
    for k, v in (r.get('posicoes') or {}).items():
        assert (v.get('v') if isinstance(v, dict) else v) in (None, -2, -1, 0, 1, 2), (r['id'], k)
for vt in (votos_df or {}).get('votacoes', []):
    assert not vt.get('url') or vt['url'].startswith('https://'), vt
for a in atuacao.values():
    for d in list(a['deputados'].values()) + list(a['outros'].values()):
        assert all(pr['u'].startswith('https://') for pr in d['proposicoes']), d
        assert type(d['n_proposicoes']) is int, d

data = dict(
    base,
    temas={k: [{'key': a, 'label': b, 'ctx': c} for a, b, c in v] for k, v in TEMAS.items()},
    research=research,
    perfis_partido=perfis,
    votos_df=votos_df,
    atuacao=atuacao,
    site=SITE,
)

# Os mesmos dados públicos em texto simples, para assistentes de IA lerem por URL (a página em si só existe com JavaScript).
# Vem antes do guia porque a lista de arquivos entra nas instruções que o guia copia: o ChatGPT só abre endereço que a
# própria pessoa enviou na conversa (ou que já esteja no índice de busca dele, e o site é noindex), então o índice não basta.
try:
    ia_bytes, ia_arquivos, ia_dep, data['ia'] = exporta(data, os.path.join(os.path.dirname(D), 'ia'), SITE)
    print(f'ia/: {ia_arquivos} arquivos + {ia_dep} de histórico parlamentar, {ia_bytes / 1e6:.2f} MB')
except Exception as e:  # um problema aqui não pode travar uma correção urgente: o guia sai apontando só para o índice
    data['ia'] = []
    print('ATENÇÃO: ia/ não foi gerada:', repr(e))


def ilha(d):
    """JSON seguro para ficar dentro de <script type="application/json">."""
    return json.dumps(d, ensure_ascii=False).replace('<', '\\u003c')


tpl = open(os.path.join(D, 'template.html'), encoding='utf-8').read().replace('__SITE__', SITE)
# hash do único <script> executável (o último do arquivo; o primeiro é a ilha de dados)
ini, fim = tpl.rindex('<script>') + len('<script>'), tpl.rindex('</script>')
sha = base64.b64encode(hashlib.sha256(tpl[ini:fim].encode()).digest()).decode()
tpl = tpl.replace('__CSP__', CSP.format(script=f'sha256-{sha}'))
data['tamanho_mb'] = round(len((tpl + ilha(data)).encode()) / 1e6, 1)
html = tpl.replace('__DATA__', ilha(data))
open(OUT, 'w', encoding='utf-8', newline='\n').write(html)

faltam = [c['id'] for c in base['candidatos'] if c['cargo'] in ('PRES', 'GOV', 'SEN') and c['id'] not in research]
print(f'{len(research)} perfis pesquisados; faltam: {faltam}')
print('votos DF:', len(votos_df['deputados']) if votos_df else 0)
print('atuação:', {k: len(v['deputados']) + len(v['outros']) for k, v in atuacao.items()} or 'sem dados')
print(OUT, round(os.path.getsize(OUT) / 1e6, 2), 'MB')
