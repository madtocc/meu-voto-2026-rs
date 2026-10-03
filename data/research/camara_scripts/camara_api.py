"""Cliente mínimo (só stdlib) para a API de dados abertos da Câmara, com cache em disco e retry."""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://dadosabertos.camara.leg.br/api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)

PAUSE = 0.4  # pausa entre requisições reais


def _cache_path(url):
    return os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")


def get(path, params=None, use_cache=True, tries=6):
    url = path if path.startswith("http") else BASE + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    cp = _cache_path(url)
    if use_cache and os.path.exists(cp):
        with open(cp) as f:
            return json.load(f)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "guia-voto-pesquisa/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8"))
            with open(cp, "w") as f:
                json.dump(data, f, ensure_ascii=False)
            time.sleep(PAUSE)
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                raise
        except Exception as e:  # timeouts, 504 com corpo não-JSON etc.
            last = e
        time.sleep(2 + 3 * i)
    raise RuntimeError(f"falhou {url}: {last}")


def get_all(path, params=None, use_cache=True):
    """Segue os links 'next' da paginação."""
    params = dict(params or {})
    params.setdefault("itens", 100)
    data = get(path, params, use_cache=use_cache)
    out = list(data.get("dados", []))
    nxt = [l["href"] for l in data.get("links", []) if l.get("rel") == "next"]
    while nxt:
        data = get(nxt[0], use_cache=use_cache)
        out.extend(data.get("dados", []))
        nxt = [l["href"] for l in data.get("links", []) if l.get("rel") == "next"]
    return out
