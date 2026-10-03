"""Cliente mínimo (só stdlib) para o portal da Assembleia Legislativa do RS, com cache em disco e retry.

Fontes usadas (todas oficiais, sem autenticação):
  - https://ww4.al.rs.gov.br:5000/...            (JSON que alimenta o portal: lista de deputados e de comissões)
  - https://ww4.al.rs.gov.br/deputados/{id}/...  (HTML: proposições do parlamentar)
  - https://ww4.al.rs.gov.br/comissoes-parlamentares/{id}/composicao  (HTML: composição das comissões)
  - https://ww3.al.rs.gov.br/deputados/FrentesParlamentares.aspx      (HTML: tabela das frentes parlamentares)
"""
import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

PORTAL = "https://ww4.al.rs.gov.br"
API = "https://ww4.al.rs.gov.br:5000"
FRENTES_URL = "https://ww3.al.rs.gov.br/deputados/FrentesParlamentares.aspx"

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)

PAUSE = 0.5  # pausa entre requisições reais (o portal é pequeno; não há pressa)
UA = "Mozilla/5.0 (compatible; guia-voto-pesquisa/1.0)"


def _cache_path(url, ext):
    return os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ext)


def get_text(url, use_cache=True, tries=5):
    """Baixa uma URL como texto UTF-8 (HTML ou JSON cru), guardando a resposta em cache/."""
    if not url.startswith("http"):
        url = PORTAL + url
    ext = ".json" if url.startswith(API) else ".html"
    cp = _cache_path(url, ext)
    if use_cache and os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            return f.read()
    last = None
    for i in range(tries):
        try:
            # O site antigo (ww3, DotNetNuke) responde HTTP 500 a "Accept-Encoding: identity", que é o
            # padrão do urllib; por isso pedimos gzip explicitamente e descompactamos aqui.
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*",
                                                       "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=90) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding", "").lower() == "gzip":
                    raw = gzip.decompress(raw)
            data = raw.decode("utf-8", errors="replace")
            with open(cp, "w", encoding="utf-8") as f:
                f.write(data)
            time.sleep(PAUSE)
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                raise
        except Exception as e:  # timeouts, conexão recusada etc.
            last = e
        time.sleep(2 + 3 * i)
    raise RuntimeError(f"falhou {url}: {last}")


def get_json(path, use_cache=True):
    """Endpoint JSON do portal (porta 5000), p.ex. get_json('/listarDestaqueDeputados')."""
    return json.loads(get_text(API + path, use_cache=use_cache))
