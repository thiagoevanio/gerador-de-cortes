"""Gera a imagem de prévia (9:16) usada na aba Visual da interface."""
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

import cortes

_PASTA = Path(tempfile.gettempdir()) / "cortes_previa"
_PASTA.mkdir(exist_ok=True)
_FOTO = _PASTA / "foto_exemplo.png"


def _foto_exemplo():
    if _FOTO.exists():
        return _FOTO
    im = Image.new("RGB", (1280, 720))
    d = ImageDraw.Draw(im)
    for y in range(720):
        d.line([(0, y), (1280, y)], fill=(35 + y // 10, 45 + y // 14, 85 + y // 9))
    d.ellipse([520, 120, 760, 360], fill=(225, 185, 150))          # cabeça
    d.rounded_rectangle([430, 380, 850, 760], radius=120, fill=(30, 30, 38))   # corpo
    im.save(_FOTO)
    return _FOTO


def _margem(base):
    """A mesma margem do corte de verdade: a que a pessoa escolheu na barra."""
    return int(base)


def _y_marca():
    """O @ fica no canto de baixo; com a legenda colada no rodapé ele sobe pro canto de cima."""
    return 70 if cortes.MARGEM_LEGENDA < 150 else cortes.ALTURA - 90


def _zona_guia(tela):
    """Faixa tracejada mostrando onde os botões/legenda do app costumam cobrir o vídeo (só guia)."""
    import acabamento
    z = acabamento.zona_segura(cortes.PLATAFORMA_ALVO)["baixo"]
    if not z:
        return tela
    base = tela.convert("RGBA")
    camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    y = cortes.ALTURA - z
    d.rectangle([0, y, cortes.LARGURA, cortes.ALTURA], fill=(255, 60, 60, 38))
    for x in range(0, cortes.LARGURA, 40):
        d.line([(x, y), (x + 22, y)], fill=(255, 90, 90, 230), width=4)
    d.text((24, y + 10), "botões do app cobrem aqui", font=cortes.fonte(30), fill=(255, 150, 150, 235))
    base.alpha_composite(camada)
    return base.convert("RGB")


def _legenda_real(tela, margem):
    """Queima a legenda de exemplo com o MESMO gerador do vídeo final (libass via ffmpeg),
    então a prévia mostra fonte, cores, caixa e ênfase do template. None se não der."""
    import subprocess
    import templates_edicao
    try:
        tpl = templates_edicao.resolver(cortes.TEMPLATE_EDICAO, "humor")
        n = int(tpl["legenda"].get("palavras") or cortes.PALAVRAS_POR_BLOCO)
        textos = ["Ela", "não", "acreditou", "nisso,", "galera"][:max(1, min(5, n))]
        palavras = [{"t": t, "ini": 0.5 * i, "fim": 0.5 * i + 0.45, "enfase": t == "acreditou"}
                    for i, t in enumerate(textos)]
        # momento congelado: 2ª palavra sendo falada (as animações já terminaram)
        quadro = _PASTA / "previa_base.png"
        tela.convert("RGB").save(quadro)
        ass = _PASTA / "previa.ass"
        cortes.gerar_ass(palavras, textos, ass, duracao=0, legenda=True, margem=margem, template=tpl)
        for f in (cortes.PASTA_PROJETO / "fontes").glob("*.[ot]tf"):
            alvo = _PASTA / f.name
            if not alvo.exists():
                alvo.write_bytes(f.read_bytes())
        saida = _PASTA / "previa_leg.png"
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", quadro.name, "-vf",
                            "ass=previa.ass:fontsdir=.", "-ss", "0.85", "-frames:v", "1", saida.name],
                           cwd=_PASTA, capture_output=True, timeout=15, creationflags=cortes.SEM_JANELA)
        if r.returncode != 0 or not saida.exists():
            return None
        return Image.open(saida).convert("RGB")
    except Exception:
        return None


def _previa_clean(cfg, altura):
    """Clean: vídeo em tela cheia, a pergunta como texto em cima, legenda mais alta."""
    foto = Image.open(_foto_exemplo()).convert("RGB")
    k = cortes.ALTURA / foto.height
    foto = foto.resize((int(foto.width * k), cortes.ALTURA))
    x0 = (foto.width - cortes.LARGURA) // 2
    tela = foto.crop((x0, 0, x0 + cortes.LARGURA, cortes.ALTURA))
    d = ImageDraw.Draw(tela)
    cor_dest = cortes.COR_LEGENDA_DESTAQUE.lstrip("#")
    cor_dest = tuple(int(cor_dest[i:i + 2], 16) for i in (0, 2, 4))
    if cortes.TEXTO_GANCHO:
        fg = cortes.fonte(80)
        linhas = ["ELE FALOU ISSO", "MESMO NA LIVE??"]
        y = 250
        for ln in linhas:
            w = d.textlength(ln, font=fg)
            d.text(((cortes.LARGURA - w) / 2, y), ln, font=fg, fill=(255, 255, 255), stroke_width=8,
                   stroke_fill=(0, 0, 0))
            y += 96
        d.text((40, y + 10), "(texto nos primeiros 3s)", font=cortes.fonte(30), fill=(220, 220, 220))
    tela = _zona_guia(tela)
    real = _legenda_real(tela, _margem(cortes.MARGEM_LEGENDA))
    if real is not None:
        tela = real
        d = ImageDraw.Draw(tela)
    palavras = [] if real is not None else ["ELA", "NÃO", "ACREDITOU", "NISSO", "GALERA"][:cortes.PALAVRAS_POR_BLOCO]
    fnt = cortes.fonte(cortes.TAMANHO_LEGENDA)
    espaco = d.textlength(" ", font=fnt)
    larg = sum(d.textlength(p, font=fnt) for p in palavras) + espaco * (len(palavras) - 1)
    alt_txt = fnt.getbbox("ÁGjy")[3]
    y = cortes.ALTURA - _margem(cortes.MARGEM_LEGENDA) - alt_txt
    x = (cortes.LARGURA - larg) / 2
    for i, p in enumerate(palavras):
        d.text((x, y), p, font=fnt, fill=cor_dest if i == 1 else (255, 255, 255), stroke_width=7,
               stroke_fill=(0, 0, 0))
        x += d.textlength(p, font=fnt) + espaco
    if cortes.MARCA:
        marca = cortes.MARCA if cortes.MARCA.startswith("@") else "@" + cortes.MARCA
        fm = cortes.fonte(40)
        wm = d.textlength(marca, font=fm)
        d.text((cortes.LARGURA - wm - 40, _y_marca()), marca, font=fm, fill=(235, 235, 235),
               stroke_width=3, stroke_fill=(0, 0, 0))
    largura = int(altura * 9 / 16)
    return tela.resize((largura, altura), Image.LANCZOS)


def gerar_previa(cfg, altura=540):
    cortes.aplicar_config(cfg)
    if cortes.CLEAN:
        return _previa_clean(cfg, altura)
    topo_p, faixa_p, y_faixa = cortes.montar_topo(_foto_exemplo(), "ELE FALOU ISSO MESMO NA LIVE??",
                                                  ["ISSO"], "Nome do Canal", _PASTA)
    topo = Image.open(topo_p)
    tela = Image.new("RGB", (cortes.LARGURA, cortes.ALTURA), (0, 0, 0))
    tela.paste(topo, (0, 0))

    # área do vídeo (exemplo)
    y0 = cortes.ALTURA_FOTO + cortes.ALTURA_FAIXA
    d = ImageDraw.Draw(tela)
    for y in range(y0, cortes.ALTURA):
        k = (y - y0) / cortes.ALTURA_VIDEO
        d.line([(0, y), (cortes.LARGURA, y)], fill=(int(60 - 30 * k), int(70 - 30 * k), int(80 - 20 * k)))
    fnt_v = cortes.fonte(46)
    txt_v = "▶ SEU VÍDEO AQUI"
    w = d.textlength(txt_v, font=fnt_v)
    d.text(((cortes.LARGURA - w) / 2, y0 + 120), txt_v, font=fnt_v, fill=(120, 130, 140))

    if faixa_p:
        fx = Image.open(faixa_p).convert("RGBA")
        base = tela.convert("RGBA")
        base.alpha_composite(fx, (0, y_faixa))
        tela = base.convert("RGB")
        d = ImageDraw.Draw(tela)

    # legenda de exemplo (mesma posição/tamanho do vídeo final) — de verdade, pelo template
    tela = _zona_guia(tela)
    real = _legenda_real(tela, _margem(cortes.MARGEM_LEGENDA))
    if real is not None:
        tela = real
        d = ImageDraw.Draw(tela)
    palavras = [] if real is not None else ["ELA", "NÃO", "ACREDITOU", "NISSO", "GALERA"][:cortes.PALAVRAS_POR_BLOCO]
    destaque = 1 if len(palavras) > 1 else 0
    fnt = cortes.fonte(cortes.TAMANHO_LEGENDA)
    espaco = d.textlength(" ", font=fnt)
    larg = sum(d.textlength(p, font=fnt) for p in palavras) + espaco * (len(palavras) - 1)
    alt_txt = fnt.getbbox("ÁGjy")[3]
    y = cortes.ALTURA - _margem(cortes.MARGEM_LEGENDA) - alt_txt
    x = (cortes.LARGURA - larg) / 2
    cor_dest = cortes.COR_LEGENDA_DESTAQUE.lstrip("#")
    cor_dest = tuple(int(cor_dest[i:i + 2], 16) for i in (0, 2, 4))
    for i, p in enumerate(palavras):
        d.text((x + 4, y + 4), p, font=fnt, fill=(0, 0, 0), stroke_width=7, stroke_fill=(0, 0, 0))
        d.text((x, y), p, font=fnt, fill=cor_dest if i == destaque else (255, 255, 255),
               stroke_width=7, stroke_fill=(0, 0, 0))
        x += d.textlength(p, font=fnt) + espaco

    if cortes.MARCA:
        marca = cortes.MARCA if cortes.MARCA.startswith("@") else "@" + cortes.MARCA
        fm = cortes.fonte(40)
        base = tela.convert("RGBA")
        camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
        dm = ImageDraw.Draw(camada)
        wm = dm.textlength(marca, font=fm)
        dm.text((cortes.LARGURA - wm - 40, _y_marca()), marca, font=fm,
                fill=(255, 255, 255, 160), stroke_width=3, stroke_fill=(0, 0, 0, 110))
        base.alpha_composite(camada)
        tela = base.convert("RGB")

    largura = int(altura * 9 / 16)
    return tela.resize((largura, altura), Image.LANCZOS)
