# Meu voto 2026 · Porto Alegre/RS

Guia pessoal de voto: candidatos (dados do TSE), propostas resumidas, score de afinidade e cola para a urna.
No ar em https://meu-voto-2026-bs0.pages.dev (noindex: só abre quem tem o link).

## Pastas

- `guia-voto-2026.html`: o guia, um arquivo só, funciona offline.
- `publicar.py`: monta `site/` e sobe para o Cloudflare Pages.
- `data/`: dados do TSE, planos de governo (PDF e texto) e scripts de build.
  - `template.html`: a interface (CSS e JavaScript num arquivo só, sem bibliotecas nem pedidos externos).
  - `research/*.json`: resumo e posições de cada candidato majoritário (PRES_, GOV_, SEN_), mais `dep_federal_votos.json` (votos na Câmara).
  - `research/dep_federal_atuacao.json` e `dep_estadual_atuacao.json`: frentes parlamentares, comissões e projetos
    apresentados por quem já é deputado, tirados dos dados oficiais da Câmara (`research/camara_scripts/03_atuacao.py`)
    e da Assembleia Legislativa (`research/alrs_scripts/`). É o que alimenta a busca por palavra-chave e o selo
    "Histórico na Câmara/Assembleia". Se um dos arquivos faltar, o guia funciona sem ele.
  - `BRIEF.md`: temas, escala de posições e formato dos JSON.

## Atualizar e publicar

```bash
data/.venv/bin/python data/build_base.py   # só se baixar dados novos do TSE (candidatos, bens, fotos)
python3 data/build_html.py                 # junta base.json + research/ no guia
python3 publicar.py                        # monta site/, sobe e confere o que ficou no ar
python3 publicar.py --sem-deploy           # só monta site/, para conferir antes
```

## Privacidade: o que o guia promete e o que garante isso

A página "Início" diz que as respostas ficam só no navegador. Três coisas sustentam a frase:

- O guia não faz nenhum pedido de rede: fotos e ícones estão embutidos, e não há fontes, scripts ou contadores de fora.
- `build_html.py` grava no guia uma Content-Security-Policy (`connect-src 'none'`, `img-src data:`) com o hash do
  único script. O navegador bloqueia qualquer envio de dados e qualquer script que não seja exatamente aquele.
  Por isso todo ajuste no JavaScript exige rodar o build de novo, e o script não pode ter `onclick=` no HTML.
- `publicar.py` repete a política no cabeçalho (`site/_headers`), recusa publicar se o hash não bater e, depois do
  deploy, baixa a página e confere que ela é idêntica ao arquivo local.

O estado fica em `localStorage` (chave `meuvoto2026-poa-v1`). A busca e os filtros da lista de deputados não são guardados.

## Para assistentes de IA

A página só existe com JavaScript, então ChatGPT, Claude e afins não conseguem lê-la por URL. Três saídas:

- `ia/` (gerada por `build_html.py` via `data/build_ia.py`): os mesmos dados públicos em arquivos `.txt` pequenos, com
  índice em `llms.txt`. `publicar.py` copia para `site/ia/` e põe o índice em `/llms.txt`. É o que funciona hoje com
  qualquer assistente: a página "Início" copia as instruções com o endereço de cada arquivo (para uma pergunta livre ou
  como roteiro em que o assistente entrevista a pessoa), e cada página de candidatos tem um botão só com os arquivos
  daquele cargo.
  Os endereços vão por extenso porque o ChatGPT só abre endereço que a pessoa enviou na conversa (ou que já está no
  índice de busca dele, e o site é noindex): só com o `llms.txt` ele lê o índice e recusa os arquivos listados nele.
- WebMCP (`instalaWebMCP` no fim do script do template): seis ferramentas de leitura para agentes que estejam com a
  página aberta num navegador compatível. Hoje isso é quase só o navegador do app do ChatGPT no computador; nos demais
  o código não faz nada. As ferramentas leem só dados públicos, nunca as respostas de quem usa o guia.
- Servidor MCP remoto (conector do Claude ou do ChatGPT): não está no projeto; só existe um protótipo local.
  Atenção: o wrangler publica qualquer pasta `functions/` que estiver na raiz do projeto, em todo deploy; por isso
  `publicar.py` recusa publicar se ela existir.

O deploy precisa de `CLOUDFLARE_API_TOKEN` (e `CLOUDFLARE_ACCOUNT_ID`): no ambiente, num `.env` na raiz do projeto
(fora do git) ou no arquivo que `MEU_VOTO_ENV` apontar. O token nunca entra no repositório.

Para recriar o ambiente Python: `uv venv data/.venv && uv pip install --python data/.venv/bin/python pymupdf pillow`.
