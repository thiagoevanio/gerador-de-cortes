"""Templates de edição: o "jeito" do corte (legenda + efeitos de vídeo/áudio + cor).

Cada template junta num nome só:
  - legenda: fonte, cores, contorno, animação (pop, karaokê, marca-texto, neon...), palavras por vez;
  - efeitos: zoom de ritmo a cada frase (jump-cut), barra de progresso, flash no gancho,
    correção de cor, vinheta e "pop" sonoro quando o emoji aparece.

A faixa/foto (estilo "faixa" ou "clean") continua sendo escolha do perfil — o template muda
só a edição por cima. "Automático (IA escolhe)" usa o TOM que a IA já devolve na mesma
chamada (zero IA a mais) pra escolher o template que combina com o momento.
"""
from __future__ import annotations

import copy
import re

AUTOMATICO = "Automático (IA escolhe)"
PADRAO = "Clássico"

# valores-base: qualquer chave que o template não definir fica assim (= comportamento antigo)
_BASE = {
    "descricao": "",
    "legenda": {
        "fonte": None,              # None = fonte padrão do sistema (Arial Black)
        "tamanho_mult": 1.0,        # multiplica o "Tamanho da legenda" do perfil
        "tamanho_min": 62,          # piso de leitura no celular: o template não encolhe abaixo disso
        "maiusculas": True,
        "cor_texto": "#FFFFFF",
        "cor_destaque": None,       # None = "Cor da palavra" do perfil
        "cor_enfase": None,         # palavras-chave marcadas pela IA (None = sem ênfase)
        "contorno": 7,
        "cor_contorno": "#000000",
        "sombra": 3,
        "blur": 0,
        "animacao": "pop",          # pop | karaoke | marca_texto | neon | suave | salto | nenhuma
        "escala_ativa": 114,        # % da palavra falada
        "palavras": None,           # None = "Palavras por vez" do perfil
        "caixa": None,              # "#RRGGBB@alpha" = caixa atrás da linha (estilo notícia)
        "inativo_alpha": 0,         # 0-255: apaga um pouco as palavras que ainda não foram faladas
    },
    "efeitos": {
        "zoom_ritmo": 0.0,          # 0.04 = 4% de zoom alternado a cada frase (jump-cut)
        "barra_progresso": None,    # "#RRGGBB" = barrinha no topo que enche até o fim
        "flash_gancho": False,      # flash branco rápido no momento mais forte
        "cor": None,                # None | vivo | cinema | frio | quente
        "vinheta": False,
        "pop_emojis": False,        # "pop" sonoro quando o emoji aparece
        "zoom_lento": 0.0,          # 0.05 = zoom quase imperceptível do início ao fim (retenção)
        "nitidez": True,            # unsharp leve sempre que o vídeo é ampliado (3.29: medido com VMAF/SSIM)
    },
}

TEMPLATES = {
    "Clássico": {
        "descricao": "O estilo de sempre: amarelo na palavra falada, bloco que pula.",
    },
    "Viral Dinâmico": {
        "descricao": "Ritmo de TikTok: zoom a cada frase, palavras-chave em verde, barra de progresso, flash e pop.",
        "legenda": {"palavras": 2, "cor_enfase": "#39FF14", "escala_ativa": 120, "animacao": "salto"},
        "efeitos": {"zoom_ritmo": 0.06, "barra_progresso": "#FFE600", "flash_gancho": True,
                    "cor": "vivo", "pop_emojis": True},
    },
    "Hormozi": {
        "descricao": "Fonte grossa, 1-2 palavras gigantes, palavra-chave colorida e sombra forte.",
        "legenda": {"fonte": "Bangers", "tamanho_mult": 1.25, "palavras": 2, "contorno": 9, "sombra": 6,
                    "cor_enfase": "#39FF14", "escala_ativa": 125, "animacao": "salto"},
        "efeitos": {"zoom_ritmo": 0.05, "cor": "vivo", "pop_emojis": True},
    },
    "Karaokê": {
        "descricao": "A cor vai enchendo as palavras conforme a pessoa fala.",
        "legenda": {"palavras": 4, "animacao": "karaoke", "cor_enfase": None},
        "efeitos": {"barra_progresso": "#FFFFFF"},
    },
    "Marca-texto": {
        "descricao": "A palavra falada ganha um fundo colorido (tipo caneta marca-texto).",
        "legenda": {"palavras": 3, "animacao": "marca_texto", "cor_destaque": "#FFE600",
                    "cor_enfase": "#FF4FD8", "contorno": 6, "sombra": 0},
        "efeitos": {"zoom_ritmo": 0.035, "cor": "vivo"},
    },
    "Neon": {
        "descricao": "Brilho neon azul/rosa, cor fria e vinheta. Bom pra games e noite.",
        "legenda": {"cor_contorno": "#00E5FF", "contorno": 5, "blur": 3, "sombra": 0,
                    "cor_destaque": "#FF3FD2", "cor_enfase": "#B4FF00", "animacao": "neon"},
        "efeitos": {"cor": "frio", "vinheta": True, "flash_gancho": True, "zoom_ritmo": 0.04},
    },
    "Gamer": {
        "descricao": "Fonte de quadrinho, contorno roxo, verde neon e muito pop. Pra lives de jogo.",
        "legenda": {"fonte": "Bangers", "tamanho_mult": 1.15, "cor_contorno": "#2A0055", "contorno": 9,
                    "cor_destaque": "#39FF14", "cor_enfase": "#FFE600", "animacao": "salto",
                    "escala_ativa": 122},
        "efeitos": {"zoom_ritmo": 0.06, "barra_progresso": "#39FF14", "flash_gancho": True,
                    "cor": "vivo", "pop_emojis": True},
    },
    "Podcast Premium": {
        "descricao": "Elegante: palavras ainda não ditas mais apagadas, cor de cinema, zoom sutil.",
        "legenda": {"fonte": "Segoe UI Black", "tamanho_mult": 0.9, "tamanho_min": 66, "palavras": 4, "contorno": 4,
                    "sombra": 2, "cor_destaque": "#FFFFFF", "inativo_alpha": 120, "animacao": "suave",
                    "escala_ativa": 108, "cor_enfase": "#FFD166"},
        "efeitos": {"zoom_ritmo": 0.03, "cor": "cinema", "vinheta": True, "barra_progresso": "#FFFFFF",
                    "zoom_lento": 0.05},
    },
    "Minimalista": {
        "descricao": "Letra normal (sem caixa alta), menor, sem animação. Limpo e sério.",
        "legenda": {"fonte": "Segoe UI Semibold", "tamanho_mult": 0.78, "maiusculas": False, "palavras": 5,
                    "contorno": 3, "sombra": 2, "animacao": "nenhuma", "escala_ativa": 100},
        "efeitos": {},
    },
    "Notícia": {
        "descricao": "Legenda em caixa escura (estilo jornal), destaque amarelo e barra vermelha.",
        "legenda": {"fonte": "Arial Black", "tamanho_mult": 0.82, "tamanho_min": 66, "palavras": 4, "caixa": "#000000@90",
                    "contorno": 14, "sombra": 0, "animacao": "suave", "escala_ativa": 100,
                    "cor_enfase": "#FFE600"},
        "efeitos": {"barra_progresso": "#E3000F", "cor": "quente"},
    },
    "Documentário": {
        "descricao": "Serifada, letra normal, entrada suave, tom de cinema com vinheta.",
        "legenda": {"fonte": "Georgia", "tamanho_mult": 0.8, "maiusculas": False, "palavras": 5,
                    "contorno": 3, "sombra": 4, "animacao": "suave", "escala_ativa": 100,
                    "cor_destaque": "#F2C14E"},
        "efeitos": {"cor": "cinema", "vinheta": True, "zoom_ritmo": 0.02},
    },
}

# tom (vindo da IA) → template no modo Automático
TOM_PARA_TEMPLATE = {
    "humor": "Viral Dinâmico",
    "polemica": "Hormozi",
    "choque": "Viral Dinâmico",
    "emocao": "Podcast Premium",
    "informativo": "Notícia",
    "suspense": "Neon",
    "gameplay": "Gamer",
    "reflexao": "Documentário",
}
TONS = list(TOM_PARA_TEMPLATE)


def nomes():
    return [AUTOMATICO] + list(TEMPLATES)


def _mesclar(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def normalizar_tom(tom):
    t = re.sub(r"[^a-z]", "", str(tom or "").lower()
               .translate(str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")))
    sinonimos = {"engracado": "humor", "comedia": "humor", "polemico": "polemica", "treta": "polemica",
                 "emocionante": "emocao", "emotivo": "emocao", "triste": "emocao", "informacao": "informativo",
                 "educativo": "informativo", "noticia": "informativo", "chocante": "choque",
                 "jogo": "gameplay", "game": "gameplay", "misterio": "suspense", "reflexivo": "reflexao"}
    t = sinonimos.get(t, t)
    return t if t in TOM_PARA_TEMPLATE else None


def resolver(nome=None, tom=None, tipo=None):
    """Template final (dict completo) + nome. 'Automático' escolhe pelo tom da IA / layout."""
    nome = nome or PADRAO
    if nome == AUTOMATICO:
        t = normalizar_tom(tom)
        if t:
            nome = TOM_PARA_TEMPLATE[t]
        elif tipo == "jogo":
            nome = "Gamer"
        elif tipo == "podcast":
            nome = "Podcast Premium"
        else:
            nome = "Viral Dinâmico"
    if nome not in TEMPLATES:
        nome = PADRAO
    tpl = _mesclar(_BASE, TEMPLATES[nome])
    tpl["nome"] = nome
    return tpl


# ---------------------------------------------------------------- efeitos de vídeo (ffmpeg)
FILTROS_COR = {
    # só "eq" (rápido): colorbalance deixava o render ~3x mais lento
    "vivo": "eq=contrast=1.06:saturation=1.22:brightness=0.01",
    "cinema": "eq=contrast=1.08:saturation=0.9:gamma_r=1.03:gamma_b=0.97",
    "frio": "eq=contrast=1.05:saturation=1.08:gamma_r=0.96:gamma_b=1.06",
    "quente": "eq=contrast=1.04:saturation=1.1:gamma_r=1.05:gamma_b=0.95",
}


def filtro_cor(efeitos, altura_fonte=None, ampliacao=None):
    """Cadeia de filtros (começando com vírgula) pra cor/vinheta/nitidez do painel de vídeo.
    ampliacao = quanto o vídeo é esticado na tela final (1080p cortado pro 9:16 = 1,78x).
    Nitidez: medido em 3.29 com VMAF e SSIM contra o original — o unsharp 0,45 dá +6 de VMAF sem
    perder nada no SSIM (mais forte começa a estragar; o CAS e a limpeza de blocos deram nota menor).
    Antes só entrava com fonte < 1080p, e o caso mais comum (1080p cortado, 1,78x) ficava sem."""
    partes = []
    if ampliacao is not None:
        esticado = ampliacao >= 1.25
    else:
        esticado = bool(altura_fonte and altura_fonte < 1000)
    if efeitos.get("nitidez", True) and esticado:
        partes.append("unsharp=5:5:0.45:5:5:0.0")
    if efeitos.get("cor") in FILTROS_COR:
        partes.append(FILTROS_COR[efeitos["cor"]])
    if efeitos.get("vinheta"):
        partes.append("vignette=angle=PI/5")
    return ("," + ",".join(partes)) if partes else ""


FIM_FRASE = re.compile(r"[.!?…]\s*$")


def trechos_ritmo(palavras, textos=None, duracao=0.0, minimo=1.6, maximo=60):
    """Divide o vídeo em frases (pontuação ou pausa) e devolve os trechos que ficam com
    zoom — um sim, um não — dando o efeito de 'jump cut' dos cortes profissionais."""
    if not palavras:
        return []
    cortes_t = [0.0]
    for i, p in enumerate(palavras[:-1]):
        txt = (textos[i] if textos and i < len(textos) else p.get("t", "")) or ""
        pausa = palavras[i + 1]["ini"] - p["fim"]
        fim_frase = bool(FIM_FRASE.search(txt)) or pausa > 0.45 or palavras[i + 1].get("quebra")
        corte = round((p["fim"] + palavras[i + 1]["ini"]) / 2, 2)
        if fim_frase and corte - cortes_t[-1] >= minimo:
            cortes_t.append(corte)
    fim = max(duracao or 0, palavras[-1]["fim"] + 0.5)
    cortes_t.append(fim)
    segs = list(zip(cortes_t, cortes_t[1:]))
    return [(round(a, 2), round(b, 2)) for k, (a, b) in enumerate(segs) if k % 2 == 1][:maximo]


def expr_ritmo(trechos, intensidade):
    """Expressão ffmpeg (fator >=1) do zoom de ritmo."""
    if not trechos or not intensidade:
        return "1"
    soma = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in trechos)
    return f"(1+{intensidade:.3f}*min(1,{soma}))"


# ---------------------------------------------------------------- legenda (.ass)
# "soco" de zoom nas palavras-chave que a IA marcou (0 = desligado)
for _nome, _valor in {"Viral Dinâmico": 0.08, "Hormozi": 0.09, "Gamer": 0.08, "Neon": 0.06, "Karaokê": 0.05,
                      "Marca-texto": 0.05, "Notícia": 0.04, "Podcast Premium": 0.04,
                      "Documentário": 0.03}.items():
    if _nome in TEMPLATES:
        TEMPLATES[_nome].setdefault("efeitos", {}).setdefault("zoom_enfase", _valor)

# par de comparação do teste A/B de template (estilos bem diferentes entre si)
ALTERNATIVOS = {"Clássico": "Viral Dinâmico", "Viral Dinâmico": "Hormozi", "Hormozi": "Viral Dinâmico",
                "Karaokê": "Marca-texto", "Marca-texto": "Karaokê", "Neon": "Viral Dinâmico",
                "Gamer": "Viral Dinâmico", "Podcast Premium": "Karaokê", "Minimalista": "Podcast Premium",
                "Notícia": "Marca-texto", "Documentário": "Podcast Premium"}


def alternativo(nome, tom=None, tipo=None):
    """Template da versão B: outro estilo, diferente do usado na versão A."""
    outro = ALTERNATIVOS.get(nome) or "Viral Dinâmico"
    if outro == nome:
        outro = PADRAO if nome != PADRAO else "Viral Dinâmico"
    return resolver(outro, tom, tipo)


def escolher_aprendido(nome_padrao, desempenho, rng=None, minimo=4, explorar=0.25, vantagem=1.15):
    """Modo Automático que aprende: troca o template escolhido pelo tom pelo que mais rende no canal.
    desempenho = {template: {"n": cortes com views, "indice": views relativas (1.0 = mediana do canal)}}.
    Só troca com amostra suficiente e vantagem clara; em ~25% dos cortes mantém a escolha pelo tom
    (continua testando os outros estilos — senão o primeiro que der sorte ganharia pra sempre)."""
    import random
    rng = rng or random
    validos = {n: d for n, d in (desempenho or {}).items()
               if n in TEMPLATES and d.get("n", 0) >= minimo and d.get("indice")}
    if len(validos) < 2 or rng.random() < explorar:
        return nome_padrao
    melhor = max(validos, key=lambda n: validos[n]["indice"])
    base = validos.get(nome_padrao, {}).get("indice") or 1.0
    return melhor if melhor != nome_padrao and validos[melhor]["indice"] >= vantagem * base else nome_padrao


def tamanho_legenda(base, legenda):
    """Tamanho final da legenda: o do perfil × o multiplicador do template, sem deixar um template
    'pequeno' cair abaixo do piso de leitura (nem abaixo do tamanho do perfil, se este já for menor)."""
    base = int(base)
    tam = int(round(base * float(legenda.get("tamanho_mult") or 1)))
    piso = min(base, int(legenda.get("tamanho_min") or 0))
    return max(tam, piso)


def cor_ass(hex_cor, alpha=0):
    h = (hex_cor or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def cor_e_alpha(spec):
    """'#000000@90' -> ('#000000', alpha ass) — alpha ass 0 = opaco, 255 = invisível."""
    if not spec:
        return "#000000", 0
    cor, _, op = str(spec).partition("@")
    try:
        opacidade = max(0, min(100, int(op))) if op else 100
    except ValueError:
        opacidade = 100
    return cor, int(round(255 * (1 - opacidade / 100)))
