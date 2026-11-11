"""Faixa, foto do topo, selos e emojis em imagem (PIL). Saiu do cortes.py na 3.10.

As configurações (largura, cores, formato da faixa...) continuam morando no cortes.py: aqui elas são
lidas como `cortes.NOME` na hora de usar, então trocar de perfil/config vale na mesma hora.
"""
from pathlib import Path
import os
import re
import sys


class _Cortes:
    """Acesso tardio ao módulo cortes (evita importação circular)."""

    def __getattr__(self, nome):
        import importlib
        return getattr(sys.modules.get("cortes") or importlib.import_module("cortes"), nome)


cortes = _Cortes()


# ============================================================
# 4. Visual
# ============================================================
def fonte(tamanho):
    from PIL import ImageFont
    for f in cortes.FONTES:
        if Path(f).exists():
            return ImageFont.truetype(f, tamanho)
    return ImageFont.load_default(tamanho)


def quebrar_linhas(d, palavras, fnt, largura_max):
    linhas, atual = [], []
    for p in palavras:
        if d.textlength(" ".join(atual + [p]), font=fnt) <= largura_max:
            atual.append(p)
        else:
            if atual:
                linhas.append(atual)
            atual = [p]
    if atual:
        linhas.append(atual)
    if len(linhas) == 2:   # equilibra as duas linhas (fica mais bonito)
        todas = linhas[0] + linhas[1]
        melhor = min(range(1, len(todas)), key=lambda k: max(
            d.textlength(" ".join(todas[:k]), font=fnt), d.textlength(" ".join(todas[k:]), font=fnt)))
        if max(d.textlength(" ".join(todas[:melhor]), font=fnt),
               d.textlength(" ".join(todas[melhor:]), font=fnt)) <= largura_max:
            linhas = [todas[:melhor], todas[melhor:]]
    return linhas


def estilo_thumbnail(foto: Path, emoji: str, pasta: Path):
    """Deixa a foto com cara de thumbnail: zoom, cores fortes, vinheta e um emoji grande."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
    img = Image.open(foto).convert("RGB")
    w, h = img.size
    z = 0.82                                   # zoom de leve (rosto costuma ficar no meio/alto)
    cw, ch = int(w * z), int(h * z)
    x0, y0 = (w - cw) // 2, int((h - ch) * 0.35)
    img = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.LANCZOS)
    img = ImageEnhance.Color(img).enhance(1.4)
    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    # vinheta
    mascara = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mascara).ellipse([-w * 0.15, -h * 0.25, w * 1.15, h * 1.25], fill=255)
    mascara = mascara.filter(ImageFilter.GaussianBlur(min(w, h) // 6))
    img = Image.composite(img, Image.new("RGB", (w, h), (0, 0, 0)), mascara)
    # emoji grande no canto (fonte colorida do Windows)
    fonte_emoji = "C:/Windows/Fonts/seguiemj.ttf"
    if emoji and os.path.exists(fonte_emoji):
        try:
            tam = int(h * 0.28)
            f = ImageFont.truetype(fonte_emoji, tam)
            camada = Image.new("RGBA", (int(tam * 1.4), int(tam * 1.4)), (0, 0, 0, 0))
            ImageDraw.Draw(camada).text((tam * 0.1, tam * 0.1), emoji[:2], font=f, embedded_color=True)
            camada = camada.rotate(-12, resample=Image.BICUBIC)
            img.paste(camada, (int(w - camada.width - w * 0.03), int(h * 0.05)), camada)
        except Exception:
            pass
    destino = pasta / "foto_thumb.jpg"
    img.save(destino, quality=92)
    return destino


def _fonte_rasgada(tam):
    from PIL import ImageFont
    if cortes.FONTE_FAIXA_RASGADA.exists():
        return ImageFont.truetype(str(cortes.FONTE_FAIXA_RASGADA), tam)
    for f in ["C:/Windows/Fonts/impact.ttf"] + cortes.FONTES:
        if Path(f).exists():
            return ImageFont.truetype(f, tam)
    return ImageFont.load_default(tam)


def faixa_rasgada(pergunta: str, destaque, canal: str):
    """Faixa de 'papel rasgado' vermelha com textura, levemente torta, texto estilo HQ.
    Devolve uma imagem RGBA (com transparência) pra ir por cima do vídeo."""
    import random
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    rnd = random.Random(pergunta)                  # mesma pergunta = mesmo rasgado
    palavras = pergunta.upper().split()
    marcados = {re.sub(r"\W", "", w.upper()) for item in (destaque or []) for w in str(item).split()}
    medidor = ImageDraw.Draw(Image.new("L", (1, 1)))
    for tam in range(118, 44, -3):
        fnt = _fonte_rasgada(tam)
        linhas = quebrar_linhas(medidor, palavras, fnt, 860)
        if len(linhas) <= 2:
            break
    alt_linha = int(fnt.getbbox("ÁGjy")[3] * 0.98)
    larg_txt = max(medidor.textlength(" ".join(l), font=fnt) for l in linhas)

    fw = int(min(1050, max(780, larg_txt + 150)))      # tamanho do papel
    fh = int(alt_linha * len(linhas) + 70)
    W, H = cortes.LARGURA, fh + 140
    x0, y0 = (W - fw) // 2, 70
    x1, y1 = x0 + fw, y0 + fh

    # contorno rasgado: serrilhado fino + alguns rasgos maiores
    def rasgo(a, b):
        return rnd.randint(a * 3, b * 3) if rnd.random() < 0.12 else rnd.randint(a, b)
    pts = []
    x = x0
    while x < x1:
        pts.append((x, y0 + rasgo(-3, 6)))
        x += rnd.randint(5, 15)
    y = y0
    while y < y1:
        pts.append((x1 - rasgo(-2, 7), y))
        y += rnd.randint(6, 14)
    x = x1
    while x > x0:
        pts.append((x, y1 - rasgo(-3, 6)))
        x -= rnd.randint(5, 15)
    y = y1
    while y > y0:
        pts.append((x0 + rasgo(-2, 7), y))
        y -= rnd.randint(6, 14)

    mascara = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mascara).polygon(pts, fill=255)

    # papel: degradê + manchas + granulado
    papel = Image.new("RGB", (W, H))
    dp = ImageDraw.Draw(papel)
    for yy in range(H):
        k = min(1, max(0, (yy - y0) / max(1, fh)))
        dp.line([(0, yy), (W, yy)], fill=tuple(int(cortes.FAIXA_COR_CIMA[i] + (cortes.FAIXA_COR_BAIXO[i] -
                                                cortes.FAIXA_COR_CIMA[i]) * k * 0.8) for i in range(3)))
    manchas = Image.effect_noise((W // 24, H // 24), 60).resize((W, H), Image.BICUBIC)
    manchas = manchas.filter(ImageFilter.GaussianBlur(5)).point(lambda v: int(135 + v / 2.1))
    papel = ImageChops.multiply(papel, Image.merge("RGB", [manchas] * 3))
    grao = Image.effect_noise((W, H), 28).point(lambda v: 225 + v // 8)
    papel = ImageChops.multiply(papel, Image.merge("RGB", [grao] * 3))
    dp = ImageDraw.Draw(papel)
    for _ in range(14):                                   # riscos de desgaste
        yy = rnd.randint(y0, y1)
        xx = rnd.randint(x0, x1 - 120)
        dp.line([(xx, yy), (xx + rnd.randint(40, 200), yy + rnd.randint(-3, 3))],
                fill=tuple(int(c * 0.7) for c in cortes.FAIXA_COR_BAIXO), width=rnd.randint(1, 3))

    faixa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # sombra embaixo do papel
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sombra.putalpha(mascara.point(lambda v: int(v * 0.6)))
    sombra = sombra.filter(ImageFilter.GaussianBlur(12))
    faixa.alpha_composite(sombra, (7, 12))
    # borda queimada (mais escura) + papel por dentro
    borda = Image.new("RGBA", (W, H), tuple(int(c * 0.55) for c in cortes.FAIXA_COR_BAIXO) + (255,))
    faixa.paste(borda, (0, 0), mascara)
    miolo = mascara.filter(ImageFilter.MinFilter(9))
    faixa.paste(papel.convert("RGBA"), (0, 0), miolo)
    # fibras claras na borda rasgada
    fibras = ImageChops.subtract(mascara, mascara.filter(ImageFilter.MinFilter(5)))
    fibras = fibras.point(lambda v: 90 if v > 0 and rnd.random() < 0.35 else 0)
    faixa.paste(Image.new("RGBA", (W, H), (255, 230, 220, 255)), (0, 0), fibras)

    # texto estilo HQ: branco, contorno preto grosso e sombra
    d = ImageDraw.Draw(faixa)
    espaco = d.textlength(" ", font=fnt)
    yy = y0 + (fh - alt_linha * len(linhas)) // 2 - 4
    contorno = max(4, fnt.size // 16)
    for linha in linhas:
        xx = (W - d.textlength(" ".join(linha), font=fnt)) / 2
        for p in linha:
            cor = cortes.COR_DESTAQUE if re.sub(r"\W", "", p) in marcados else cortes.COR_TEXTO
            d.text((xx + 5, yy + 6), p, font=fnt, fill=(0, 0, 0, 200), stroke_width=contorno,
                   stroke_fill=(0, 0, 0, 200))
            d.text((xx, yy), p, font=fnt, fill=cor, stroke_width=contorno, stroke_fill=(15, 10, 10))
            xx += d.textlength(p, font=fnt) + espaco
        yy += alt_linha

    if cortes.MOSTRAR_SELO_CANAL and canal:
        fs = fonte(28)
        txt = canal.upper()[:28]
        w = d.textlength(txt, font=fs)
        bx, by = x0 + 20, y0 - 44
        d.rounded_rectangle([bx, by, bx + w + 74, by + 48], radius=12, fill=(15, 15, 15, 255),
                            outline=cortes.FAIXA_LINHA_COR, width=3)
        d.ellipse([bx + 18, by + 15, bx + 36, by + 33], fill=(255, 40, 40))
        d.text((bx + 48, by + 9), txt, font=fs, fill=(255, 255, 255))

    return faixa.rotate(-2.2, resample=Image.BICUBIC)


# ---------- outros formatos de faixa (todos vão por cima do vídeo) ----------
def _texto_layout(pergunta, largura_max=860, maior=118, menor=44):
    from PIL import Image, ImageDraw
    medidor = ImageDraw.Draw(Image.new("L", (1, 1)))
    palavras = pergunta.upper().split()
    for tam in range(maior, menor, -3):
        fnt = _fonte_rasgada(tam)
        linhas = quebrar_linhas(medidor, palavras, fnt, largura_max)
        if len(linhas) <= 2:
            break
    alt_linha = int(fnt.getbbox("ÁGjy")[3] * 0.98)
    larg = max(medidor.textlength(" ".join(l), font=fnt) for l in linhas)
    return fnt, linhas, alt_linha, larg


def _texto_desenhar(img, fnt, linhas, alt_linha, destaque, y_topo, sombra=True):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    marcados = {re.sub(r"\W", "", w.upper()) for item in (destaque or []) for w in str(item).split()}
    claro = sum(cortes.COR_TEXTO) > 380
    borda = (15, 10, 10) if claro else (255, 255, 255)
    contorno = max(4, fnt.size // 16)
    espaco = d.textlength(" ", font=fnt)
    y = y_topo
    for linha in linhas:
        x = (img.width - d.textlength(" ".join(linha), font=fnt)) / 2
        for p in linha:
            cor = cortes.COR_DESTAQUE if re.sub(r"\W", "", p) in marcados else cortes.COR_TEXTO
            if sombra:
                d.text((x + 5, y + 6), p, font=fnt, fill=(0, 0, 0, 170), stroke_width=contorno,
                       stroke_fill=(0, 0, 0, 170))
            d.text((x, y), p, font=fnt, fill=cor, stroke_width=contorno, stroke_fill=borda)
            x += d.textlength(p, font=fnt) + espaco
        y += alt_linha


def _selo(img, canal, x, y):
    if not (cortes.MOSTRAR_SELO_CANAL and canal):
        return
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    fs = fonte(28)
    txt = canal.upper()[:28]
    w = d.textlength(txt, font=fs)
    d.rounded_rectangle([x, y, x + w + 74, y + 48], radius=12, fill=(15, 15, 15, 255),
                        outline=cortes.FAIXA_LINHA_COR, width=3)
    d.ellipse([x + 18, y + 15, x + 36, y + 33], fill=(255, 40, 40))
    d.text((x + 48, y + 9), txt, font=fs, fill=(255, 255, 255))


def _sombra_de(mascara, deslocar=(7, 12), forca=0.6, blur=12):
    from PIL import Image, ImageFilter
    sombra = Image.new("RGBA", mascara.size, (0, 0, 0, 0))
    sombra.putalpha(mascara.point(lambda v: int(v * forca)))
    sombra = sombra.filter(ImageFilter.GaussianBlur(blur))
    camada = Image.new("RGBA", mascara.size, (0, 0, 0, 0))
    camada.alpha_composite(sombra, deslocar)
    return camada


def _papel_colorido(W, H, y0, fh, granulado=28):
    """Fundo na cor do estilo, com degradê e granulado leve."""
    from PIL import Image, ImageChops, ImageDraw
    papel = Image.new("RGB", (W, H))
    dp = ImageDraw.Draw(papel)
    for yy in range(H):
        k = min(1, max(0, (yy - y0) / max(1, fh)))
        dp.line([(0, yy), (W, yy)], fill=tuple(int(cortes.FAIXA_COR_CIMA[i] + (cortes.FAIXA_COR_BAIXO[i] -
                                                cortes.FAIXA_COR_CIMA[i]) * k * 0.8) for i in range(3)))
    grao = Image.effect_noise((W, H), granulado).point(lambda v: 225 + v // 8)
    return ImageChops.multiply(papel, Image.merge("RGB", [grao] * 3))


def faixa_pincelada(pergunta, destaque, canal):
    """Pincelada de tinta: pontas irregulares e marcas de cerdas secas."""
    import random
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random("pincel" + pergunta)
    fnt, linhas, alt_linha, larg = _texto_layout(pergunta)
    fw, fh = int(min(1060, max(800, larg + 190))), int(alt_linha * len(linhas) + 80)
    W, H = cortes.LARGURA, fh + 150
    x0, y0 = (W - fw) // 2, 75
    mascara = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(mascara)
    y = y0
    while y < y0 + fh:                               # várias passadas do pincel
        ini = x0 + rnd.randint(-10, 60)
        fim = x0 + fw - rnd.randint(-10, 60)
        dm.line([(ini, y), (fim, y + rnd.randint(-4, 4))], fill=255, width=rnd.randint(9, 15))
        for _ in range(3):                           # cerdas soltas nas pontas
            yy = y + rnd.randint(-5, 5)
            dm.line([(ini - rnd.randint(10, 70), yy), (ini + 20, yy)], fill=rnd.randint(120, 255), width=2)
            dm.line([(fim - 20, yy), (fim + rnd.randint(10, 70), yy)], fill=rnd.randint(120, 255), width=2)
        y += rnd.randint(5, 9)
    mascara = mascara.filter(ImageFilter.GaussianBlur(1.2))
    tinta = _papel_colorido(W, H, y0, fh, granulado=40)
    d = ImageDraw.Draw(tinta)
    for _ in range(90):                              # marcas das cerdas (claras e escuras)
        yy = rnd.randint(y0, y0 + fh)
        xx = rnd.randint(x0, x0 + fw - 150)
        tom = 1.25 if rnd.random() < 0.5 else 0.65
        cor = tuple(min(255, int(c * tom)) for c in cortes.FAIXA_COR_CIMA)
        d.line([(xx, yy), (xx + rnd.randint(80, 400), yy + rnd.randint(-2, 2))], fill=cor, width=rnd.randint(1, 3))
    faixa = _sombra_de(mascara, (6, 10), 0.55, 10)
    faixa.paste(tinta.convert("RGBA"), (0, 0), mascara)
    _texto_desenhar(faixa, fnt, linhas, alt_linha, destaque, y0 + (fh - alt_linha * len(linhas)) // 2 - 4)
    _selo(faixa, canal, x0 + 30, y0 - 48)
    return faixa.rotate(-3, resample=Image.BICUBIC)


def faixa_fita(pergunta, destaque, canal):
    """Papel colado com dois pedaços de fita adesiva nas pontas."""
    import random
    from PIL import Image, ImageDraw
    rnd = random.Random("fita" + pergunta)
    fnt, linhas, alt_linha, larg = _texto_layout(pergunta, 840)
    fw, fh = int(min(1000, max(760, larg + 140))), int(alt_linha * len(linhas) + 70)
    W, H = cortes.LARGURA, fh + 180
    x0, y0 = (W - fw) // 2, 90
    x1, y1 = x0 + fw, y0 + fh
    mascara = Image.new("L", (W, H), 0)
    pts = [(x0 + rnd.randint(-2, 2), y0), (x1, y0 + rnd.randint(-3, 3)),
           (x1 + rnd.randint(-3, 3), y1), (x0, y1 + rnd.randint(-3, 3))]
    ImageDraw.Draw(mascara).polygon(pts, fill=255)
    faixa = _sombra_de(mascara, (8, 14), 0.55, 14)
    faixa.paste(_papel_colorido(W, H, y0, fh).convert("RGBA"), (0, 0), mascara)
    _texto_desenhar(faixa, fnt, linhas, alt_linha, destaque, y0 + (fh - alt_linha * len(linhas)) // 2 - 4)
    # fitas adesivas (meio transparentes, pontas serrilhadas)
    for cx, ang in [(x0 + 30, 38), (x1 - 30, -38)]:
        tw, th = 190, 54
        fita = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        df = ImageDraw.Draw(fita)
        borda_e = [(rnd.randint(0, 6), yy) for yy in range(0, th + 1, 6)]
        borda_d = [(tw - rnd.randint(0, 6), yy) for yy in range(th, -1, -6)]
        df.polygon(borda_e + borda_d, fill=(248, 240, 214, 215))
        df.line([(8, 8), (tw - 8, 8)], fill=(255, 255, 255, 90), width=3)
        fita = fita.rotate(ang, expand=True, resample=Image.BICUBIC)
        faixa.alpha_composite(fita, (int(cx - fita.width / 2), int(y0 - fita.height / 2 + 6)))
    _selo(faixa, canal, x0 + 150, y1 - 6)
    return faixa.rotate(-1.5, resample=Image.BICUBIC)


def faixa_adesivo(pergunta, destaque, canal):
    """Adesivo (sticker): cantos arredondados, borda branca grossa, brilho e sombra."""
    from PIL import Image, ImageDraw, ImageFilter
    fnt, linhas, alt_linha, larg = _texto_layout(pergunta, 820, 110)
    fw, fh = int(min(1000, max(720, larg + 130))), int(alt_linha * len(linhas) + 70)
    W, H = cortes.LARGURA, fh + 170
    x0, y0 = (W - fw) // 2, 80
    x1, y1 = x0 + fw, y0 + fh
    borda = 16
    externo = Image.new("L", (W, H), 0)
    ImageDraw.Draw(externo).rounded_rectangle([x0 - borda, y0 - borda, x1 + borda, y1 + borda],
                                              radius=48, fill=255)
    interno = Image.new("L", (W, H), 0)
    ImageDraw.Draw(interno).rounded_rectangle([x0, y0, x1, y1], radius=36, fill=255)
    faixa = _sombra_de(externo, (6, 12), 0.6, 14)
    faixa.paste(Image.new("RGBA", (W, H), (255, 255, 255, 255)), (0, 0), externo)
    faixa.paste(_papel_colorido(W, H, y0, fh, 18).convert("RGBA"), (0, 0), interno)
    brilho = Image.new("L", (W, H), 0)                    # reflexo na metade de cima
    ImageDraw.Draw(brilho).rounded_rectangle([x0 + 14, y0 + 10, x1 - 14, y0 + fh * 0.42],
                                             radius=30, fill=55)
    brilho = Image.composite(brilho, Image.new("L", (W, H), 0), interno).filter(ImageFilter.GaussianBlur(4))
    faixa.paste(Image.new("RGBA", (W, H), (255, 255, 255, 255)), (0, 0), brilho)
    _texto_desenhar(faixa, fnt, linhas, alt_linha, destaque, y0 + (fh - alt_linha * len(linhas)) // 2 - 4)
    _selo(faixa, canal, x0 + 24, y0 - borda - 46)
    return faixa.rotate(-4, resample=Image.BICUBIC)


FORMATOS_FAIXA = {"Rasgada": "faixa_rasgada", "Pincelada": "faixa_pincelada",
                  "Fita": "faixa_fita", "Adesivo": "faixa_adesivo"}


def encaixar_inteira(foto: Path, largura, altura, base_y):
    """Mostra a imagem INTEIRA (sem cortar o texto da thumbnail) sobre um fundo desfocado dela mesma.
    base_y = até onde a imagem pode descer (pra não ficar escondida atrás da faixa)."""
    from PIL import Image, ImageFilter, ImageOps
    img = Image.open(foto).convert("RGB")
    fundo = ImageOps.fit(img, (largura, altura), method=Image.LANCZOS)
    fundo = fundo.filter(ImageFilter.GaussianBlur(28)).point(lambda v: int(v * 0.55))
    escala = largura / img.width
    w, h = largura, int(img.height * escala)
    if h > base_y:                                   # imagem alta: reduz pra caber
        escala = base_y / img.height
        w, h = int(img.width * escala), base_y
    frente = img.resize((w, h), Image.LANCZOS)
    y = max(0, base_y - h)
    fundo.paste(frente, ((largura - w) // 2, y))
    return fundo


FONTES_EMOJI = ["C:/Windows/Fonts/seguiemj.ttf", "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
                "/System/Library/Fonts/Apple Color Emoji.ttc"]


def emoji_png(emoji, destino: Path, tamanho=170):
    """Emoji COLORIDO em PNG transparente (a legenda do ffmpeg não sabe desenhar emoji colorido)."""
    from PIL import Image, ImageDraw, ImageFont
    for f in FONTES_EMOJI:
        if not os.path.exists(f):
            continue
        try:
            fixo = "NotoColorEmoji" in f or f.endswith(".ttc")
            fnt = ImageFont.truetype(f, 109 if fixo else tamanho)
            lado = int((109 if fixo else tamanho) * 1.5)
            img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
            ImageDraw.Draw(img).text((lado * 0.12, lado * 0.08), emoji, font=fnt, embedded_color=True)
            caixa = img.getbbox()
            if not caixa:
                continue
            img = img.crop(caixa)
            img = img.resize((tamanho, int(tamanho * img.height / img.width)), Image.LANCZOS)
            img.save(destino)
            return destino
        except Exception:
            continue
    return None


def selo_png(texto, destino: Path, cor=(255, 214, 0), cor_texto=(20, 20, 20)):
    from PIL import Image, ImageDraw
    fnt = _fonte_rasgada(62)
    medida = ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(texto, font=fnt)
    img = Image.new("RGBA", (int(medida + 60), 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 6, img.width - 4, 90], radius=18, fill=(0, 0, 0, 150))
    d.rounded_rectangle([0, 0, img.width - 8, 84], radius=18, fill=cor + (255,))
    d.text((26, 6), texto, font=fnt, fill=cor_texto)
    img.save(destino)
    return destino


def faixa_reta_png(pergunta, destaque, canal):
    """A faixa reta clássica como camada por cima (pros layouts sem foto: podcast / jogo)."""
    from PIL import Image, ImageDraw
    fnt, linhas, alt_linha, larg = _texto_layout(pergunta, 960, 96)
    h = int(alt_linha * len(linhas) + 50)
    W, H = cortes.LARGURA, h + 100
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y0 = 60
    for y in range(y0, y0 + h):
        k = (y - y0) / h
        d.line([(0, y), (W, y)], fill=tuple(int(cortes.FAIXA_COR_CIMA[i] + (cortes.FAIXA_COR_BAIXO[i] - cortes.FAIXA_COR_CIMA[i]) * k)
                                            for i in range(3)) + (255,))
    d.rectangle([0, y0, W, y0 + cortes.FAIXA_LINHA_ALTURA], fill=cortes.FAIXA_LINHA_COR)
    d.rectangle([0, y0 + h - cortes.FAIXA_LINHA_ALTURA, W, y0 + h], fill=cortes.FAIXA_LINHA_COR)
    _texto_desenhar(img, fnt, linhas, alt_linha, destaque, y0 + (h - alt_linha * len(linhas)) // 2 - 4)
    _selo(img, canal, 30, y0 - 46)
    return img


def montar_topo(foto: Path, pergunta: str, destaque, canal: str, pasta: Path, inteira=False, so_faixa=False):
    """Devolve (imagem do topo, imagem da faixa por cima ou None, posição y da faixa).
    so_faixa=True (podcast / jogo): o topo vira vídeo, então só a faixa importa (sempre por cima)."""
    from PIL import Image, ImageDraw, ImageOps

    if so_faixa:
        alt = cortes.ALTURA_FOTO + cortes.ALTURA_FAIXA
        faixa = (globals()[FORMATOS_FAIXA[cortes.FAIXA_FORMATO]](pergunta, destaque, canal)
                 if cortes.FAIXA_FORMATO in FORMATOS_FAIXA else faixa_reta_png(pergunta, destaque, canal))
        faixa_path = pasta / "faixa.png"
        faixa.save(faixa_path)
        return None, faixa_path, int(alt - faixa.height / 2 - 10)

    if cortes.FAIXA_FORMATO in FORMATOS_FAIXA:
        alt = cortes.ALTURA_FOTO + cortes.ALTURA_FAIXA
        if inteira:            # thumbnail: mostra inteira, acima da faixa, sem cortar o texto dela
            img = encaixar_inteira(foto, cortes.LARGURA, alt, base_y=alt - 215)
        else:
            img = ImageOps.fit(Image.open(foto).convert("RGB"), (cortes.LARGURA, alt),
                               method=Image.LANCZOS, centering=(0.5, 0.3))
        sombra = Image.new("L", (1, alt))
        for yy in range(alt):
            sombra.putpixel((0, yy), int(max(0, (yy - alt * 0.6) / (alt * 0.4)) * 170))
        img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0), sombra.resize(img.size))
        topo_path = pasta / "topo.png"
        img.save(topo_path)
        faixa = globals()[FORMATOS_FAIXA[cortes.FAIXA_FORMATO]](pergunta, destaque, canal)
        faixa_path = pasta / "faixa.png"
        faixa.save(faixa_path)
        y_faixa = int(alt - faixa.height / 2 - 40)       # em cima da emenda foto/vídeo
        return topo_path, faixa_path, y_faixa

    topo = Image.new("RGB", (cortes.LARGURA, cortes.ALTURA_FOTO + cortes.ALTURA_FAIXA), (0, 0, 0))
    if inteira:
        img = encaixar_inteira(foto, cortes.LARGURA, cortes.ALTURA_FOTO, base_y=cortes.ALTURA_FOTO - 30)
    else:
        img = ImageOps.fit(Image.open(foto).convert("RGB"), (cortes.LARGURA, cortes.ALTURA_FOTO),
                           method=Image.LANCZOS, centering=(0.5, 0.35))
    # escurece levemente a parte de baixo da foto (dá profundidade)
    sombra = Image.new("L", (1, cortes.ALTURA_FOTO))
    for y in range(cortes.ALTURA_FOTO):
        sombra.putpixel((0, y), int(max(0, (y - cortes.ALTURA_FOTO * 0.7) / (cortes.ALTURA_FOTO * 0.3)) * 120))
    img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0), sombra.resize(img.size))
    topo.paste(img, (0, 0))

    d = ImageDraw.Draw(topo)
    y0, y1 = cortes.ALTURA_FOTO, cortes.ALTURA_FOTO + cortes.ALTURA_FAIXA
    for y in range(y0, y1):     # degradê
        k = (y - y0) / cortes.ALTURA_FAIXA
        cor = tuple(int(cortes.FAIXA_COR_CIMA[i] + (cortes.FAIXA_COR_BAIXO[i] - cortes.FAIXA_COR_CIMA[i]) * k)
                    for i in range(3))
        d.line([(0, y), (cortes.LARGURA, y)], fill=cor)
    d.rectangle([0, y0, cortes.LARGURA, y0 + cortes.FAIXA_LINHA_ALTURA], fill=cortes.FAIXA_LINHA_COR)
    d.rectangle([0, y1 - cortes.FAIXA_LINHA_ALTURA, cortes.LARGURA, y1], fill=cortes.FAIXA_LINHA_COR)

    # texto com palavra destaque em amarelo
    palavras = pergunta.upper().split()
    marcados = {re.sub(r"\W", "", w.upper()) for item in (destaque or []) for w in str(item).split()}
    area_h = cortes.ALTURA_FAIXA - 2 * cortes.FAIXA_LINHA_ALTURA - 30
    for tam in range(96, 30, -2):
        fnt = fonte(tam)
        linhas = quebrar_linhas(d, palavras, fnt, cortes.LARGURA - 100)
        alt_linha = fnt.getbbox("ÁGjy")[3] + 6
        if len(linhas) <= 2 and alt_linha * len(linhas) <= area_h:
            break
    espaco = d.textlength(" ", font=fnt)
    y = y0 + (cortes.ALTURA_FAIXA - alt_linha * len(linhas)) // 2
    for linha in linhas:
        x = (cortes.LARGURA - d.textlength(" ".join(linha), font=fnt)) // 2
        for p in linha:
            cor = cortes.COR_DESTAQUE if re.sub(r"\W", "", p) in marcados else cortes.COR_TEXTO
            escuro = tuple(int(c * 0.45) for c in cortes.FAIXA_COR_BAIXO)
            if cortes.COR_TEXTO != (255, 255, 255):          # faixa clara: sombra suave
                escuro = tuple(int(c * 0.8) for c in cortes.FAIXA_COR_BAIXO)
            d.text((x + 4, y + 5), p, font=fnt, fill=escuro)
            d.text((x, y), p, font=fnt, fill=cor, stroke_width=2, stroke_fill=escuro)
            x += d.textlength(p, font=fnt) + espaco
        y += alt_linha

    # selo do canal em cima da faixa
    if cortes.MOSTRAR_SELO_CANAL and canal:
        fs = fonte(30)
        txt = canal.upper()[:28]
        w = d.textlength(txt, font=fs)
        bx, bh = 30, 54
        by = y0 - bh // 2
        d.rounded_rectangle([bx, by, bx + w + 80, by + bh], radius=14, fill=(15, 15, 15),
                            outline=cortes.FAIXA_LINHA_COR, width=3)
        d.ellipse([bx + 20, by + 18, bx + 38, by + 36], fill=(255, 40, 40))
        d.text((bx + 52, by + 10), txt, font=fs, fill=(255, 255, 255))

    destino = pasta / "topo.png"
    topo.save(destino)
    return destino, None, 0
