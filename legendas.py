"""Legendas: blocos, .ass por template e .srt. Saiu do cortes.py na 3.10.

As configurações (largura, cores, formato da faixa...) continuam morando no cortes.py: aqui elas são
lidas como `cortes.NOME` na hora de usar, então trocar de perfil/config vale na mesma hora.
"""
import re
import sys
from pathlib import Path


class _Cortes:
    """Acesso tardio ao módulo cortes (evita importação circular)."""

    def __getattr__(self, nome):
        import importlib
        return getattr(sys.modules.get("cortes") or importlib.import_module("cortes"), nome)


cortes = _Cortes()


def tempo_ass(s):
    s = max(0, s)
    h, r = divmod(s, 3600)
    m, sg = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{sg:05.2f}"


def tempo_srt(s):
    ms = int(round(max(0, s) * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def blocos_legenda(palavras, textos, n=None):
    """Agrupa as palavras de N em N, quebrando também onde tiver 'quebra' (fim da prévia do
    gancho), uma pausa longa ou fim de frase — assim um bloco nunca mistura duas cenas/ideias."""
    n = max(1, int(n or cortes.PALAVRAS_POR_BLOCO))
    blocos, atual = [], []
    for i, p in enumerate(palavras):
        item = {"t": textos[i], "ini": p["ini"], "fim": p["fim"], "enfase": bool(p.get("enfase"))}
        pausa = atual and p["ini"] - atual[-1]["fim"] > 0.8
        fim_frase = atual and n > 2 and len(atual) >= 2 and re.search(r"[.!?…]$", atual[-1]["t"] or "")
        if atual and (len(atual) >= n or p.get("quebra") or pausa or fim_frase):
            blocos.append(atual)
            atual = []
        atual.append(item)
    if atual:
        blocos.append(atual)
    return blocos


COR_FALANTE_B = "#8FE3FF"        # podcast: a 2ª pessoa fala em azul-claro (a 1ª em branco)


def gerar_ass(palavras, textos, destino: Path, duracao=0.0, legenda=True, falantes=None, textos_extra=None,
              margem=None, template=None):
    """Legenda palavra a palavra no estilo do template de edição (templates_edicao.py).
    Animações: pop, salto, karaokê, marca-texto, neon, suave ou nenhuma. Com 'falantes'
    (podcast), cada pessoa tem uma cor. textos_extra = [(ini, fim, texto, estilo)]."""
    import templates_edicao as te
    tpl = template if isinstance(template, dict) else te.resolver(template or cortes.TEMPLATE_EDICAO)
    lg = tpl["legenda"]
    fonte_leg = lg.get("fonte") or cortes.FONTE_LEGENDA
    tam = te.tamanho_legenda(cortes.TAMANHO_LEGENDA, lg)
    contorno = int(lg.get("contorno", 7))
    sombra = int(lg.get("sombra", 3))
    cor_cont = cortes.cor_ass(lg.get("cor_contorno") or "#000000")
    animacao = lg.get("animacao") or "pop"
    if not cortes.LEGENDA_ANIMADA and animacao != "karaoke":
        animacao = "nenhuma"
    borda, cor_box, cor_back = 1, cor_cont, "&H80000000"
    if lg.get("caixa"):                             # estilo notícia: caixa atrás da linha
        c, a = te.cor_e_alpha(lg["caixa"])
        borda, cor_box = 3, te.cor_ass(c, a)
        cor_back = cor_box
    dest = cortes.cor_ass(lg.get("cor_destaque") or cortes.COR_LEGENDA_DESTAQUE)
    enf = cortes.cor_ass(lg["cor_enfase"]) if lg.get("cor_enfase") else None
    texto_cor = cortes.cor_ass(lg.get("cor_texto") or "#FFFFFF")
    esc = int(lg.get("escala_ativa") or 100) if animacao != "nenhuma" else 100
    alpha_inativo = max(0, min(255, int(lg.get("inativo_alpha") or 0)))
    blur = f"\\blur{int(lg['blur'])}" if lg.get("blur") else ""
    margem_leg = cortes.MARGEM_LEGENDA if margem is None else margem
    # legenda colada no rodapé: o @ vai pro canto de cima (senão os dois se encostam)
    marca_pos = "9,40,36,70" if margem_leg < 150 else "3,40,36,36"
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {cortes.LARGURA}
PlayResY: {cortes.ALTURA}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Leg,{fonte_leg},{tam},{texto_cor},{texto_cor},{cor_box},{cor_back},-1,0,0,0,100,100,0,0,{borda},{contorno},{sombra},2,60,60,{margem_leg},1
Style: Marca,{cortes.FONTE_LEGENDA},40,&H50FFFFFF,&H50FFFFFF,&H70000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,{marca_pos},1
Style: Aviso,{fonte_leg},64,&H0000E6FF,&H0000E6FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,6,3,5,60,60,0,1
Style: Gancho,{fonte_leg},88,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,8,4,8,70,70,250,1
Style: GanchoMeio,{fonte_leg},72,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,8,4,5,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    eventos = []
    if cortes.MARCA and duracao:
        marca = cortes.MARCA if cortes.MARCA.startswith("@") else "@" + cortes.MARCA
        eventos.append(f"Dialogue: 1,0:00:00.00,{tempo_ass(duracao + 1)},Marca,,0,0,0,,{marca}")
    for ini, fim, texto, estilo in textos_extra or []:
        eventos.append(f"Dialogue: 2,{tempo_ass(ini)},{tempo_ass(fim)},{estilo},,0,0,0,,"
                       "{\\fscx60\\fscy60\\t(0,150,\\fscx110\\fscy110)\\t(150,250,\\fscx100\\fscy100)}" + texto)

    def txt(x):
        t = (x["t"] or "").replace("{", "").replace("}", "").replace("\\", "")
        return t.upper() if lg.get("maiusculas", True) else t

    def cor_base(bloco):
        if falantes and __import__("efeitos").quem_fala(falantes, bloco[0]["ini"]) == "B":
            return cortes.cor_ass(COR_FALANTE_B)
        return texto_cor

    entrada = {"pop": "{\\fscx72\\fscy72\\t(0,90,\\fscx108\\fscy108)\\t(90,170,\\fscx100\\fscy100)}",
               "salto": "{\\fscx60\\fscy60\\t(0,80,\\fscx112\\fscy112)\\t(80,160,\\fscx100\\fscy100)}",
               "marca_texto": "{\\fscx80\\fscy80\\t(0,100,\\fscx100\\fscy100)}",
               "neon": "{\\fad(90,0)\\fscx85\\fscy85\\t(0,120,\\fscx100\\fscy100)}",
               "suave": "{\\fad(140,0)}"}.get(animacao, "")
    blocos = blocos_legenda(palavras, textos, lg.get("palavras")) if legenda else []
    for bi, bloco in enumerate(blocos):
        fim_b = bloco[-1]["fim"]
        prox = blocos[bi + 1][0]["ini"] if bi + 1 < len(blocos) else fim_b + 0.4
        base = cor_base(bloco)
        if animacao == "karaoke":                   # 1 evento por bloco: a cor "enche" cada palavra
            partes = []
            for j, w in enumerate(bloco):
                ate = bloco[j + 1]["ini"] if j + 1 < len(bloco) else w["fim"]
                cs = max(1, int(round((ate - w["ini"]) * 100)))
                partes.append("{\\kf" + str(cs) + "}" + txt(w))
            fim = max(min(prox, fim_b + 0.5), bloco[0]["ini"] + 0.2)
            eventos.append(f"Dialogue: 0,{tempo_ass(bloco[0]['ini'])},{tempo_ass(fim)},Leg,,0,0,0,,"
                           "{" + blur + "\\1c" + dest + "\\2c" + base + "}" + " ".join(partes))
            continue
        for i, w in enumerate(bloco):
            fim = bloco[i + 1]["ini"] if i + 1 < len(bloco) else min(prox, fim_b + 0.5)
            fim = max(fim, w["ini"] + 0.1)
            partes = []
            for j, x in enumerate(bloco):
                t = txt(x)
                if j == i:
                    if animacao == "marca_texto":     # fundo colorido = contorno grosso na cor do destaque
                        partes.append("{\\c&H101010&\\3c" + dest + "\\bord" + str(contorno + 10) +
                                      "\\shad0}" + t + "{\\c" + base + "\\3c" + cor_cont +
                                      "\\bord" + str(contorno) + "}")
                    elif animacao == "salto":
                        partes.append("{\\c" + dest + "\\t(0,80,\\fscx" + str(esc + 10) + "\\fscy" +
                                      str(esc + 10) + ")\\t(80,170,\\fscx" + str(esc) + "\\fscy" + str(esc) +
                                      ")}" + t + "{\\fscx100\\fscy100\\c" + base + "}")
                    else:
                        escala = f"\\fscx{esc}\\fscy{esc}" if esc != 100 else ""
                        partes.append("{\\c" + dest + escala + "}" + t +
                                      "{" + ("\\fscx100\\fscy100" if escala else "") + "\\c" + base + "}")
                elif alpha_inativo and j > i:          # palavras que ainda vão ser ditas: mais apagadas
                    cor = enf if (enf and x.get("enfase")) else base
                    partes.append("{\\alpha&H" + f"{alpha_inativo:02X}" + "&\\c" + cor + "}" + t +
                                  "{\\alpha&H00&\\c" + base + "}")
                elif enf and x.get("enfase"):          # palavra-chave marcada pela IA
                    partes.append("{\\c" + enf + "}" + t + "{\\c" + base + "}")
                else:
                    partes.append(t)
            efeito = entrada if i == 0 else ""
            eventos.append(f"Dialogue: 0,{tempo_ass(w['ini'])},{tempo_ass(fim)},Leg,,0,0,0,,"
                           + efeito + "{" + blur + "\\c" + base + "}" + " ".join(partes))
    destino.write_text(cab + "\n".join(eventos) + "\n", encoding="utf-8")
    return destino


def texto_gancho_ass(pergunta, destaque=None):
    """A pergunta como TEXTO (estilo clean): maiúsculas, palavras de destaque em amarelo."""
    alvo = {re.sub(r"\W", "", d.upper()) for d in (destaque or []) if isinstance(d, str)}
    cor = cortes.cor_ass(cortes.COR_LEGENDA_DESTAQUE)
    partes = []
    for w in (pergunta or "").upper().replace("{", "").replace("}", "").split():
        partes.append("{\\c" + cor + "}" + w + "{\\c&HFFFFFF&}" if re.sub(r"\W", "", w) in alvo else w)
    return " ".join(partes)


def gerar_srt(palavras, textos, destino: Path):
    linhas = []
    blocos = blocos_legenda(palavras, textos)
    for n, bloco in enumerate(blocos, 1):
        fim = bloco[-1]["fim"] + 0.2
        if n < len(blocos):
            fim = min(fim, blocos[n][0]["ini"])
        linhas += [str(n), f"{tempo_srt(bloco[0]['ini'])} --> {tempo_srt(fim)}",
                   " ".join(x["t"] for x in bloco), ""]
    destino.write_text("\n".join(linhas), encoding="utf-8")
    return destino
