"""Desenha og.png: a imagem que aparece na prévia do link (WhatsApp, Telegram, iMessage).

Roda só quando o texto ou o visual da prévia mudar, e a imagem gerada fica no git: o deploy pelo GitHub Actions
não tem Pillow nem as fontes do macOS, então publicar.py apenas copia o arquivo pronto para site/og.png.

Uso: data/.venv/bin/python data/build_og.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(D, 'og.png')
W, H, PAD = 1200, 630, 80   # 1200x630 é o tamanho que as prévias grandes pedem
S = 2                       # desenha no dobro e reduz: bordas e cantos saem lisos

BG, SURFACE, INK, MUTED, LINE, ACCENT = '#f5f4f0', '#ffffff', '#1b1b1f', '#55545c', '#e3e1db', '#3640a8'
FONTE = '/System/Library/Fonts/SFNS.ttf'   # a mesma fonte de sistema que o guia usa no Mac e no iPhone


def fonte(tamanho, peso):
    f = ImageFont.truetype(FONTE, tamanho * S)
    eixos = {a['name'] if isinstance(a['name'], str) else a['name'].decode(): a for a in f.get_variation_axes()}
    f.set_variation_by_axes([peso if n == 'Weight' else a['default'] for n, a in eixos.items()])
    return f


im = Image.new('RGB', (W * S, H * S), BG)
x = ImageDraw.Draw(im)
px = lambda *v: tuple(n * S for n in v)

# marca: o mesmo quadrado com o "confirma" do favicon
M = 76
x.rounded_rectangle(px(PAD, PAD, PAD + M, PAD + M), radius=17 * S, fill=INK)
x.line([px(PAD + 21, PAD + 39), px(PAD + 32, PAD + 50), px(PAD + 55, PAD + 25)], fill='#fff', width=8 * S, joint='curve')
for cx, cy in ((21, 39), (32, 50), (55, 25)):   # pontas e quina arredondadas, como no SVG
    x.ellipse(px(PAD + cx - 4, PAD + cy - 4, PAD + cx + 4, PAD + cy + 4), fill='#fff')
x.text(px(PAD + M + 22, PAD + M / 2), 'Eleições 2026 · 1º turno em 4 de outubro', font=fonte(30, 500), fill=MUTED, anchor='lm')

x.text(px(PAD - 4, 300), 'Meu voto 2026', font=fonte(112, 700), fill=INK, anchor='ls')
x.text(px(PAD, 368), 'Rio Grande do Sul', font=fonte(52, 600), fill=ACCENT, anchor='ls')
x.text(px(PAD, 436), 'Candidatos, propostas resumidas com fonte e cola para a urna', font=fonte(33, 400), fill=MUTED, anchor='ls')

# rodapé: o que tranquiliza quem recebe o link
y = H - PAD - 62
x.rounded_rectangle(px(PAD, y, W - PAD, y + 62), radius=16 * S, fill=SURFACE, outline=LINE, width=2 * S)
x.text(px(W / 2, y + 31), 'Dados oficiais do TSE  ·  Sem cadastro  ·  Sem anúncios', font=fonte(27, 500), fill=INK, anchor='mm')

im.resize((W, H), Image.LANCZOS).save(OUT, optimize=True)
print(OUT, round(os.path.getsize(OUT) / 1024), 'KB')
