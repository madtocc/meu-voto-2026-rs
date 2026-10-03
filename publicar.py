#!/usr/bin/env python3
"""
publicar.py — põe o guia de voto na web (Cloudflare Pages).

Monta um site/ estático e sobe com o wrangler pinado, autenticando com o
CLOUDFLARE_API_TOKEN do ambiente ou de um .env (o da raiz do projeto, ou o que
MEU_VOTO_ENV apontar). O token é lido na hora e passado só para o processo do
wrangler: não é copiado nem impresso.

O que vai para o ar:
  /                     o guia (guia-voto-2026.html)
  /data/prop_*/...pdf   os planos de governo oficiais (os links do guia apontam para cá)
  /llms.txt, /ia/*.txt  os mesmos dados públicos em texto, para assistentes de IA lerem por URL
  /robots.txt           libera a leitura (a prévia de link do WhatsApp precisa)
  /_headers             X-Robots-Tag: noindex (fora do Google; só quem tem o link) e a política de
                        segurança (CSP) que faz o navegador bloquear qualquer envio de dados pela página
  /og.png               a imagem da prévia do link (data/og.png, desenhada por data/build_og.py)
  /404.html, /favicon.svg

Uso:
  python3 publicar.py              # monta site/ e sobe
  python3 publicar.py --sem-deploy # só monta site/
"""

import argparse
import base64
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ENV_TOKEN = Path(os.environ.get('MEU_VOTO_ENV') or PASTA / '.env')   # fora do git
PROJETO = 'meu-voto-2026'
DOMINIO = 'https://meu-voto-2026-bs0.pages.dev'   # a URL que o Cloudflare deu (o nome tinha dono: ganhou sufixo)
BRANCH = 'main'
WRANGLER = 'wrangler@4.120.1'          # pinado: o deploy não muda sozinho com uma versão nova
LIMITE_ARQUIVO = 25 * 1024 * 1024      # teto por arquivo do Pages

FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#1b1b1f"/><path d="M18 33l9 9 19-21" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg>"""

PAGINA_404 = """<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Página não encontrada · Meu voto 2026</title>
<body style="font:16px/1.5 -apple-system,system-ui,sans-serif;background:#f5f4f0;color:#1b1b1f;display:grid;place-items:center;min-height:100vh;margin:0"><main style="text-align:center;padding:24px"><h1 style="font-size:22px">Essa página não existe</h1><p><a href="/" style="color:#3640a8">Voltar para o guia</a></p></main></body></html>"""


def log(msg):
    print(msg, flush=True)


def csp_do_guia(html):
    """Devolve a política de segurança que o build gravou no guia, conferindo que o hash bate com o script.

    A página promete que nada sai do navegador; quem garante é essa política, e o script entra nela por hash.
    Se o hash não bater, o navegador bloqueia o script e a página fica em branco: melhor parar aqui."""
    m = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html)
    if not m or '__CSP__' in m.group(1):
        sys.exit('O guia está sem a política de segurança: rode python3 data/build_html.py antes de publicar.')
    ini, fim = html.rindex('<script>') + len('<script>'), html.rindex('</script>')
    sha = base64.b64encode(hashlib.sha256(html[ini:fim].encode('utf-8')).digest()).decode()
    if f"'sha256-{sha}'" not in m.group(1):
        sys.exit('O hash do script não bate com a política de segurança do guia: rode python3 data/build_html.py de novo.')
    return m.group(1)


def monta_site(destino):
    guia = PASTA / 'guia-voto-2026.html'
    html = guia.read_text(encoding='utf-8')
    csp = csp_do_guia(html)
    parcial = destino.with_name(destino.name + '.novo')
    if parcial.exists():
        shutil.rmtree(parcial)
    parcial.mkdir(parents=True)

    (parcial / 'index.html').write_text(html, encoding='utf-8')
    planos = sorted(set(re.findall(r'"plano":\s*"(data/prop_[^"]+\.pdf)"', html)))
    for rel in planos:
        origem = PASTA / rel
        if origem.stat().st_size > LIMITE_ARQUIVO:
            log(f'   ↷ {rel} pulado: acima de 25 MB')
            continue
        alvo = parcial / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, alvo)
    ia = PASTA / 'ia'   # gerado por data/build_html.py; llms.txt é o último arquivo escrito, então marca uma exportação completa
    if (ia / 'llms.txt').is_file():
        shutil.copytree(ia, parcial / 'ia')
        (parcial / 'ia' / 'llms.txt').rename(parcial / 'llms.txt')
    else:
        log('ATENÇÃO: ia/ ausente ou incompleta: o guia sobe sem os arquivos para assistentes de IA.')
    (parcial / 'favicon.svg').write_text(FAVICON, encoding='utf-8')
    og = PASTA / 'data' / 'og.png'   # o guia aponta para ela em og:image; sem o arquivo a prévia do link sai sem imagem
    if og.is_file():
        shutil.copy2(og, parcial / 'og.png')
    else:
        log('ATENÇÃO: data/og.png ausente: a prévia do link (WhatsApp) sobe sem imagem. Rode data/.venv/bin/python data/build_og.py.')
    (parcial / '404.html').write_text(PAGINA_404, encoding='utf-8')
    (parcial / 'robots.txt').write_text('User-agent: *\nAllow: /\n', encoding='utf-8')
    # O guia fica 10 minutos no cache do navegador (antes era baixado inteiro a cada abertura): uma correção
    # publicada chega a todo mundo em até 10 minutos. A CSP vai também no cabeçalho, com frame-ancestors
    # (que não vale em <meta>), para ninguém embutir o guia dentro de outra página.
    (parcial / '_headers').write_text(
        '/*\n'
        '  X-Robots-Tag: noindex\n'
        '  Referrer-Policy: no-referrer\n'
        '  X-Content-Type-Options: nosniff\n'
        '  Cross-Origin-Opener-Policy: same-origin\n'
        '  X-DNS-Prefetch-Control: off\n'
        '  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=(), bluetooth=(), browsing-topics=(), web-share=(self)\n'
        '/\n'
        '  Cache-Control: public, max-age=600\n'
        '  X-Frame-Options: DENY\n'
        f"  Content-Security-Policy: {csp}; frame-ancestors 'none'\n"
        '/data/*\n'
        '  Cache-Control: public, max-age=604800\n', encoding='utf-8')

    if destino.exists():
        shutil.rmtree(destino)
    parcial.rename(destino)
    tamanho = sum(p.stat().st_size for p in destino.rglob('*') if p.is_file()) / 1024 / 1024
    log(f'📦 site/ montado: guia + {len(planos)} planos de governo, {tamanho:.1f} MB')


def confere_no_ar(html):
    """Baixa o que o Cloudflare está servindo e confere se é, byte a byte, o guia local.

    Se a hospedagem alterasse o HTML (minificação, script injetado), o hash da CSP deixaria de bater e a
    página abriria em branco. Aqui isso aparece na hora, e não no relato de alguém no dia da eleição."""
    esperado = hashlib.sha256(html.encode('utf-8')).hexdigest()
    for tentativa in range(6):
        try:
            req = urllib.request.Request(f'{DOMINIO}/?conferir={int(time.time())}', headers={'User-Agent': 'publicar.py'})
            with urllib.request.urlopen(req, timeout=30) as r:
                corpo, csp = r.read(), r.headers.get('Content-Security-Policy')
            if hashlib.sha256(corpo).hexdigest() == esperado:
                log(f'✅ no ar e idêntico ao arquivo local: {DOMINIO}')
                if not csp:
                    log('⚠️  a resposta veio sem o cabeçalho Content-Security-Policy (a do <meta> continua valendo).')
                return True
        except Exception as e:
            log(f'   conferência {tentativa + 1}: {e}')
        time.sleep(10)
    log('⚠️  o HTML servido NÃO é igual ao guia local. Abra o site e veja se ele carrega.')
    return False


def env_do_token():
    """Junta ao ambiente os CLOUDFLARE_* do .env, se houver, sem imprimir nada."""
    env = dict(os.environ)
    if ENV_TOKEN.exists():
        for linha in ENV_TOKEN.read_text().splitlines():
            m = re.match(r'\s*(CLOUDFLARE_[A-Z_]+)\s*=\s*(.*?)\s*$', linha)
            if m:
                env[m.group(1)] = m.group(2).strip('"\'')
    if 'CLOUDFLARE_API_TOKEN' not in env:
        sys.exit(f'Sem CLOUDFLARE_API_TOKEN: ponha no ambiente ou em {ENV_TOKEN}.')
    return env


def wrangler(args, env, cwd):
    cmd = ['npx', '--yes', WRANGLER, *args]
    log(f"☁️  {' '.join(cmd)}")
    return subprocess.run(cmd, env=env, cwd=cwd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sem-deploy', action='store_true')
    ap.add_argument('--criar-projeto', action='store_true', help='cria o projeto no Pages (só a 1ª vez)')
    a = ap.parse_args()

    # O wrangler publica qualquer pasta functions/ que achar na raiz, junto com o guia: nada de servidor entra por acidente.
    if (PASTA / 'functions').exists():
        sys.exit('Há uma pasta functions/ na raiz do projeto: o wrangler a publicaria junto com o guia. Tire-a daqui antes de publicar.')
    site = PASTA / 'site'
    monta_site(site)
    if a.sem_deploy:
        return
    env = env_do_token()
    if a.criar_projeto:
        r = wrangler(['pages', 'project', 'create', PROJETO, f'--production-branch={BRANCH}'], env, PASTA)
        if r.returncode != 0:
            log('(se o projeto já existe, tudo bem: seguindo para o deploy)')
    r = wrangler(['pages', 'deploy', str(site), f'--project-name={PROJETO}', f'--branch={BRANCH}',
                  '--commit-dirty=true'], env, PASTA)
    if r.returncode == 0 and not confere_no_ar((site / 'index.html').read_text(encoding='utf-8')):
        sys.exit(1)
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()
