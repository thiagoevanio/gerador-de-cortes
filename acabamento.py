"""Acabamento do corte (3.10): zoom nas palavras-chave, zona segura por plataforma, abertura limpa,
final (chamada ou loop) e capa. Funções puras — quem decide ligar/desligar é o cortes.py."""
import subprocess
import unicodedata
from pathlib import Path

# ------------------------------------------------------------------ zona segura (1080x1920)
# Área que os botões/legenda de cada app cobrem. Valores aproximados (os apps mudam o layout de
# tempos em tempos) — "todas" usa o pior caso, que serve pra postar o mesmo arquivo em tudo.
ZONAS = {
    "tiktok": {"baixo": 480, "direita": 180, "topo": 160},
    "reels": {"baixo": 420, "direita": 130, "topo": 250},
    "shorts": {"baixo": 380, "direita": 190, "topo": 240},
    "nenhuma": {"baixo": 0, "direita": 0, "topo": 0},
}
ZONAS["todas"] = {k: max(z[k] for z in ZONAS.values()) for k in ("baixo", "direita", "topo")}
PLATAFORMAS = ["todas", "tiktok", "reels", "shorts", "nenhuma"]


def zona_segura(plataforma):
    return dict(ZONAS.get(str(plataforma or "todas").lower(), ZONAS["todas"]))


def y_acima_ou_abaixo(altura, margem_leg, tamanho_leg, altura_item, topo_livre, zona_baixo=0):
    """Y de um item (emoji) perto da legenda: logo acima dela; se não couber (a legenda subiu pra
    perto da faixa), vai pra logo abaixo — nunca em cima da faixa da pergunta."""
    acima = int(altura - margem_leg - tamanho_leg * 1.9 - altura_item)
    if acima >= topo_livre:
        return acima
    abaixo = int(altura - margem_leg + 40)
    return max(int(topo_livre), min(abaixo, int(altura - zona_baixo - altura_item - 20)))


# ------------------------------------------------------------------ zoom nas palavras-chave
def tempos_enfase(palavras, gancho_t=None, duracao=None, intervalo=1.8, maximo=6):
    """Instantes das palavras marcadas com 'enfase', espaçados e longe do soco do gancho."""
    tempos = []
    for p in palavras:
        if not p.get("enfase"):
            continue
        t = float(p["ini"])
        if t < 0.6 or (duracao and t > duracao - 0.8):
            continue
        if gancho_t is not None and abs(t - gancho_t) < 1.4:
            continue
        if tempos and t - tempos[-1] < intervalo:
            continue
        tempos.append(round(t, 2))
        if len(tempos) >= maximo:
            break
    return tempos


def expr_enfase(tempos, intensidade, subida=0.12, descida=0.42):
    """Expressão ffmpeg: 'soco' curto de zoom em cada instante (sobe rápido, volta devagar)."""
    partes = []
    for t0 in tempos:
        pico = t0 + subida
        partes.append(f"max(0,min((t-{t0:.2f})/{subida:.2f},1-(t-{pico:.2f})/{descida:.2f}))")
    if not partes:
        return "1"
    return f"(1+{float(intensidade):.3f}*min(1,{'+'.join(partes)}))"


# ------------------------------------------------------------------ abertura limpa
_ENROLACAO = {"entao", "bom", "bem", "tipo", "olha", "cara", "mano", "ne", "assim", "ah", "hum", "ahn", "eh",
              "enfim", "ta", "ok", "beleza", "po", "ai", "dai", "velho", "vei", "ee", "eee", "hm", "uh",
              "veja", "vamos", "la"}
_PONTUACAO = ",.…!?;:-"


def _norm(texto):
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if c.isalnum())


def abertura_limpa(palavras, textos, indice_ia=None, limite_s=4.5, minimo_resto=12.0):
    """Índice da palavra que deve abrir o corte (0 = começo já está bom).
    indice_ia: sugestão da IA (vale se estiver nos primeiros segundos). Sem ela, tira só enrolação
    óbvia e isolada por pontuação ("Então,", "Bom,", "Cara,") — nunca palavras que fazem parte da frase."""
    n = len(palavras)
    if n < 8:
        return 0
    fim_total = palavras[-1]["fim"]

    def serve(i):
        return (0 < i < n - 5 and palavras[i]["ini"] <= limite_s
                and fim_total - palavras[i]["ini"] >= minimo_resto
                and not any(p.get("gancho") or p.get("foco") for p in palavras[:i]))
    try:
        ia = int(indice_ia) if indice_ia is not None else 0
    except (TypeError, ValueError):
        ia = 0
    if serve(ia):
        return ia
    i = 0
    while i < n - 5:
        bruto = str(textos[i] if i < len(textos) else palavras[i].get("t", "")).strip()
        if _norm(bruto) in _ENROLACAO and bruto[-1:] in _PONTUACAO and palavras[i]["ini"] <= limite_s:
            i += 1
        else:
            break
    return i if serve(i) else 0


def aparar_pela_ia(palavras, par, dur_total, max_corte=25.0, fracao=0.4, minimo=15.0):
    """A IA devolve [1ª palavra, última palavra] do pedaço que deve ficar. Devolve (t0, t1) em segundos
    ou None se não há o que aparar. Travas: cada ponta perde no máximo 25s (ou 40% do trecho), sobra
    pelo menos 55% do trecho, e o gancho / o lance da live / a divisão da série nunca ficam de fora."""
    try:
        i0, i1 = int(par[0]), int(par[1])
    except (TypeError, ValueError, IndexError):
        return None
    n = len(palavras)
    if n < 8 or not (0 <= i0 < i1 < n):
        return None
    protegidas = [i for i, p in enumerate(palavras) if p.get("gancho") or p.get("foco") or p.get("serie")]
    if any(i < i0 for i in protegidas):
        i0 = 0
    if any(i > i1 for i in protegidas):
        i1 = n - 1
    limite = min(max_corte, dur_total * fracao)
    t0 = 0.0
    if i0 > 0:
        t0 = max(palavras[i0]["ini"] - 0.25, (palavras[i0 - 1]["fim"] + palavras[i0]["ini"]) / 2, 0.0)
    t1 = float(dur_total)
    if i1 < n - 1:
        t1 = min(palavras[i1]["fim"] + 0.45, (palavras[i1]["fim"] + palavras[i1 + 1]["ini"]) / 2, dur_total)
    # a sugestão vale inteira ou não vale: se tiraria demais de qualquer ponta (ou no total), fica tudo
    if t0 > limite or dur_total - t1 > limite or t1 - t0 < max(minimo, 0.55 * dur_total):
        return None
    if t0 < 0.4:
        t0 = 0.0
    if dur_total - t1 < 0.4:
        t1 = float(dur_total)
    if t0 == 0.0 and t1 >= dur_total:
        return None
    return round(t0, 2), round(t1, 2)


def destaque_auto(pergunta, maximo=2):
    """Sem IA: as palavras mais 'pesadas' da pergunta (nomes/palavras longas) pra ficarem coloridas."""
    comuns = {"VOCE", "ESSE", "ESSA", "ISSO", "PARA", "COMO", "QUANDO", "PORQUE", "MESMO", "SOBRE", "AINDA",
              "MUITO", "TINHA", "ESTAVA", "FALOU", "DISSE", "ENTAO", "DEPOIS", "ANTES", "AGORA"}
    vistas, cand = set(), []
    for bruta in str(pergunta).split():
        limpa = bruta.strip("?!.,;:\"'“”()")
        chave = _norm(limpa).upper()
        if len(chave) >= 5 and chave not in comuns and chave not in vistas:
            vistas.add(chave)
            cand.append(limpa)
    cand.sort(key=len, reverse=True)
    return cand[:maximo]


# ------------------------------------------------------------------ final em loop
def fim_para_loop(palavras, duracao, folga=0.28, minimo=0.35):
    """Novo fim do vídeo (colado na última palavra) pra emendar com o começo no replay, ou None."""
    if not palavras:
        return None
    fim = float(palavras[-1]["fim"]) + folga
    return fim if duracao - fim > minimo and fim > 8 else None


# ------------------------------------------------------------------ capa
def gerar_capa(video_final, destino, t=1.5, pergunta=None, fonte=None, largura=1080):
    """Salva um quadro do corte pronto como capa (.jpg). Com 'pergunta', escreve ela por cima
    (quando o quadro ainda não tem o texto na tela). Devolve o caminho ou None."""
    video_final, destino = Path(video_final), Path(destino)
    bruto = destino.with_suffix(".tmp.png")
    melhor = None
    for dt in (0.0, 0.4, 0.8):                    # entre 3 quadros vizinhos, fica o mais nítido
        tentativa = destino.with_name(destino.stem + f"_{int(dt * 10)}.tmp.png")
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, t + dt):.2f}", "-i", str(video_final),
                            "-frames:v", "1", str(tentativa)], capture_output=True)
        if r.returncode == 0 and tentativa.exists() and tentativa.stat().st_size > 1000:
            melhor = melhor or []
            melhor.append(tentativa)
    if not melhor:
        return None
    try:
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
        import numpy as np

        def nitidez(arq):
            g = np.asarray(Image.open(arq).convert("L").resize((270, 480)), dtype="float32")
            return float(np.abs(np.diff(g, axis=0)).mean() + np.abs(np.diff(g, axis=1)).mean())
        escolhido = max(melhor, key=nitidez)
        img = Image.open(escolhido).convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.08)
        img = ImageEnhance.Color(img).enhance(1.12)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=3))
        if pergunta and fonte:
            d = ImageDraw.Draw(img)
            W, H = img.size
            tam = 104
            while tam >= 56:
                fnt = fonte(tam)
                linhas, atual = [], ""
                for palavra in str(pergunta).split():
                    teste = (atual + " " + palavra).strip()
                    if d.textlength(teste, font=fnt) <= W - 140 or not atual:
                        atual = teste
                    else:
                        linhas.append(atual)
                        atual = palavra
                linhas.append(atual)
                if len(linhas) <= 4 and all(d.textlength(li, font=fnt) <= W - 100 for li in linhas):
                    break
                tam -= 8
            y = int(H * 0.16)
            for li in linhas:
                x = (W - d.textlength(li, font=fnt)) / 2
                d.text((x, y), li, font=fnt, fill=(255, 255, 255), stroke_width=max(6, tam // 11),
                       stroke_fill=(0, 0, 0))
                y += int(tam * 1.16)
        img.save(destino, quality=92)
    except Exception:
        return None
    finally:
        for arq in list(melhor) + [bruto]:
            try:
                arq.unlink()
            except OSError:
                pass
    return destino if destino.exists() else None
