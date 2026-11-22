"""
CORTES 9:16 - gerador de cortes estilo "corte de live" brasileiro
------------------------------------------------------------------
Layout final (1080x1920):
    [ FOTO no topo  (thumbnail ou melhor frame)   ]
    [ FAIXA VERMELHA com a pergunta + selo canal  ]
    [ VIDEO embaixo (+ legenda, se quiser)        ]

Uso direto:
  python cortes.py "https://www.youtube.com/watch?v=XXXX" --inicio 12:30 --fim 13:20
  python cortes.py meu_video.mp4 --inicio 0:45 --fim 1:40 --foto foto.jpg
  python cortes.py URL --inicio 1:02:10 --fim 1:03:00 --sem-legenda

O monitor.py usa a função gerar_corte() daqui pra fazer tudo sozinho.
"""
from __future__ import annotations

import argparse
from contextvars import ContextVar
from contextlib import contextmanager
import threading
import json
import os
import re
import shutil
import subprocess
import textwrap
import tempfile
import math
from infraestrutura import exclusividade, salvar_json
import time
import ia_motor
import sys
# rodando como "python cortes.py", os outros módulos fazem "import cortes": tem que ser ESTE módulo
# (senão existiriam duas cópias, cada uma com a sua configuração)
sys.modules.setdefault("cortes", sys.modules[__name__])

for _fluxo in (sys.stdout, sys.stderr):      # emoji no log nunca derruba o corte (console cp1252)
    try:
        _fluxo.reconfigure(errors="replace")
    except Exception:
        pass
import urllib.request
from pathlib import Path

import doutor as _doutor
_doutor.path_do_processo()        # ffmpeg baixado pelo instalador vale na hora, sem reiniciar o PC

# ============================================================
# CONFIGURAÇÕES VISUAIS (pode mexer aqui)
# ============================================================
LARGURA, ALTURA = 1080, 1920
ALTURA_FOTO = 760
ALTURA_FAIXA = 210
ALTURA_VIDEO = ALTURA - ALTURA_FOTO - ALTURA_FAIXA   # 950

FAIXA_COR_CIMA = (235, 25, 25)      # degradê da faixa (vermelho claro → escuro)
FAIXA_COR_BAIXO = (165, 0, 0)
FAIXA_LINHA_COR = (255, 214, 0)     # linhas amarelas em cima e embaixo da faixa
FAIXA_LINHA_ALTURA = 8
COR_TEXTO = (255, 255, 255)
COR_DESTAQUE = (255, 230, 0)        # palavra-chave da pergunta fica amarela
MOSTRAR_SELO_CANAL = True           # selinho preto "● NOME DO CANAL" em cima da faixa

PALAVRAS_POR_BLOCO = 3
TAMANHO_LEGENDA = 80
MODELO_WHISPER = "auto"             # "auto" = base na busca de momentos + whisper_final no corte

FONTES = [
    "C:/Windows/Fonts/ariblk.ttf",          # Arial Black (Windows)
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
]
FONTE_LEGENDA = "Arial Black" if os.name == "nt" else "DejaVu Sans"

PASTA_SAIDA = Path("cortes_prontos")

# no Windows, evita abrir janelas pretas quando roda pela interface
SEM_JANELA = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

MARGEM_LEGENDA = 170                 # distância da legenda até a borda de baixo (menor = mais baixo)
COR_LEGENDA_DESTAQUE = "#FFE600"     # cor da palavra falada na legenda
IA_PRINCIPAL = "claude"              # "claude", "codex", "gemini", "local" ou "nenhuma"
IA_RESERVA = True                    # se a principal falhar, tenta a outra
ECONOMICO = True
IA_QUALIDADE = "equilibrado"
MODELO_LOCAL = "qwen2.5:3b"
GEMINI_API_KEY = ""
FAIXA_FORMATO = "Rasgada"
SEGUIR_ROSTO = True
TIRAR_SILENCIOS = True
EFEITO_GANCHO = True
GANCHO_INICIO = True
GANCHO_DISTANCIA_MIN = 10.0
NOTA_MINIMA_AUTO = 6.0
MUSICA_FUNDO = True
MUSICA_VOLUME = 0.16
FINAL_CORTE = "cta"
CTA_TEXTO = "SEGUE PRA MAIS CORTES"
PLATAFORMA_ALVO = "todas"
LIMPAR_ABERTURA = True
AB_VARIAR = "alternar"
GERAR_CAPA = True
CHECAR_MUSICA = True
APARAR_IA = True
TEMPLATE_APRENDE = True
TIRAR_VICIOS = True
AUDIO_PADRAO = True
BAIXAR_1080 = True
MODO_PC_FRACO = False         # Whisper base, 720p e rostos a cada 1 s (desempenho.py recomenda)
AB_TESTE = False
ESPANHOL = False
CHECAR_INEDITO = True
USAR_APRENDIZADO = True
USAR_ASSUNTOS = True
PERFIL_EM_USO = "Padrão"
LAYOUT = "auto"
TEMPLATE_EDICAO = "Clássico"         # templates_edicao.py
CLEAN = False                        # estilo clean: sem foto e sem faixa, vídeo em tela cheia
TEXTO_GANCHO = True
LEGENDA_ANIMADA = True
EMOJIS_LEGENDA = True
REVISOR = True
REVISAO_IA = False
SERIE = True
SERIE_MIN = 95                 # segundos: trechos maiores que isso podem virar parte 1/2
MARCA = ""
NOTA_MINIMA = 0
PASTA_PROJETO = Path(__file__).resolve().parent
FONTE_FAIXA_RASGADA = PASTA_PROJETO / "fontes" / "Bangers-Regular.ttf"
GEMINI_MODELO = "gemini-flash-latest"

# Estilos prontos da faixa: (cor de cima, cor de baixo, linhas, palavra destaque, texto)
ESTILOS_FAIXA = {
    "Vermelho clássico": ((235, 25, 25), (165, 0, 0), (255, 214, 0), (255, 230, 0), (255, 255, 255)),
    "Preto e amarelo":   ((40, 40, 40), (10, 10, 10), (255, 214, 0), (255, 214, 0), (255, 255, 255)),
    "Amarelo":           ((255, 225, 20), (245, 185, 0), (20, 20, 20), (200, 0, 0), (20, 20, 20)),
    "Azul":              ((30, 110, 255), (10, 50, 170), (255, 255, 255), (255, 230, 0), (255, 255, 255)),
    "Roxo":              ((150, 50, 255), (80, 10, 170), (255, 214, 0), (255, 230, 0), (255, 255, 255)),
    "Verde":             ((20, 190, 90), (0, 110, 50), (255, 255, 255), (255, 240, 0), (255, 255, 255)),
}

# ============================================================
# Configuração salva (config.json) — editada pela interface
# ============================================================
ARQ_CONFIG = Path(__file__).resolve().parent / "config.json"
CONFIG_PADRAO = {
    "legenda_margem": 170,
    "legenda_tamanho": 80,
    "legenda_palavras": 3,
    "legenda_cor": "#FFE600",
    "faixa_estilo": "Vermelho clássico",
    "faixa_formato": "Rasgada",    # "Rasgada", "Pincelada", "Fita", "Adesivo", "Balão", "Neon", "Plantão", "Explosão", "Diagonal" ou "Reta"
    "seguir_rosto": True,          # câmera acompanha o rosto de quem fala
    "tirar_silencios": True,       # corta as pausas longas
    "efeito_gancho": True,         # zoom rápido + "boom" no momento mais forte
    "gancho_inicio": True,         # mostra ~2s do momento mais forte logo no começo
    "gancho_distancia_min": 10,    # só antecipa o gancho se ele estiver a 10s+ do início
    "tirar_vicios": True,          # corta "é…", "tipo,", "né?", "hum"
    "audio_padrao": True,          # volume no padrão das plataformas + voz mais clara
    "baixar_1080": True,           # baixa em 1080p (mais nítido) em vez de 720p
    "fps_auto": True,              # fonte em 60 fps sai em 60 fps (gameplay fluido; 30 no Modo PC fraco)
    "marca": "",                   # seu @ no canto do vídeo (marca d'água)
    "nota_minima": 0,              # 0 = não descarta; ex: 6 descarta cortes com nota abaixo de 6
    "nota_minima_automatico": 6,   # cortes que o robô faz sozinho (sem você pedir): descarta abaixo disso
    "musica_fundo": True,          # música da pasta musicas/ por baixo da fala (abaixa quando alguém fala)
    "musica_volume": 0.16,         # volume da música (0.05 = quase nada, 0.3 = bem presente)
    "final_corte": "cta",          # fim do corte: "cta" (cartaz de chamada), "loop" (emenda no replay) ou "nada"
    "cta_texto": "SEGUE PRA MAIS CORTES",
    "plataforma_alvo": "todas",    # zona segura da legenda: todas / tiktok / reels / shorts / nenhuma
    "limpar_abertura": True,       # tira a enrolação ("Então,", "Bom,") dos primeiros segundos
    "ab_variar": "alternar",       # teste A/B: "pergunta", "template", "ambos" ou "alternar" (um de cada vez)
    "capa": True,                  # salva uma capa .jpg (quadro + pergunta) ao lado do corte
    "checar_musica": True,         # avisa se o trecho parece ter música de fundo (risco de direitos autorais)
    "aparar_ia": True,             # a IA pode aparar o começo/fim fracos do trecho (até ~12s de cada ponta)
    "template_aprende": True,      # modo Automático prefere os templates que mais rendem no seu canal
    "horarios_postagem": ["12:00", "18:00", "21:00"],
    "mostrar_selo": True,
    "ia_principal": "claude",
    "ia_reserva": True,
    "economico": True,             # (antigo) virou "ia_qualidade"
    "ia_qualidade": "equilibrado",  # economico (Haiku em tudo) / equilibrado (Sonnet nos cortes) / maximo (Opus)
    "claude_modelo_leve": "haiku",
    "claude_modelo_medio": "sonnet",
    "claude_modelo_forte": "opus",
    "modelo_local": "qwen2.5:3b",  # modelo do Ollama (IA local, grátis, roda no PC)
    "gemini_api_key": "",          # chave da API do Google AI Studio (fica só no seu PC)
    "gemini_modelo": "gemini-flash-latest",
    "layout": "auto",              # auto / normal / podcast / jogo
    "estilo_corte": "faixa",       # "faixa" (foto + faixa vermelha) ou "clean" (vídeo em tela cheia, sem faixa)
    "texto_gancho": True,          # clean: a pergunta aparece como texto nos primeiros segundos
    "legenda_animada": True,       # cada bloco "pula" quando aparece + cor por pessoa
    "emojis_legenda": True,        # emoji colorido nas palavras mais fortes
    "revisor": True,               # revisor sem IA: frase completa, legenda/faixa longe dos rostos
    "revisao_ia": False,           # revisão final por IA (gasta 1 imagem por corte)
    "serie": True,                 # trecho longo vira PARTE 1 / PARTE 2
    "horario_inteligente": False,  # usa os horários que mais dão views (aba Resultados)
    "ab_teste": False,             # gera também uma versão B com outra pergunta
    "espanhol": False,             # gera também uma versão em espanhol (2º canal)
    "checar_inedito": True,        # procura no YouTube se já tem cortes parecidos
    "usar_aprendizado": True,      # a IA usa o que funcionou no seu canal
    "usar_assuntos": True,         # a IA sabe os assuntos em alta no Brasil
    "canais": [],                  # (perfis) canais de origem que usam este perfil
    "perfis": {},                  # outros perfis: {"Nome": {chaves visuais...}}
    "perfil_ativo": "Padrão",
    "vocabulario": "", "retranscrever_incertos": False, "revisao_tecnica": False,
    # economia: tudo que gasta IA/CPU a mais começa DESLIGADO (liga em "Qualidade")
    "avaliacao_editorial": False,  # IA dá 4 notas com citações (gancho/contexto/desenv./conclusão)
    "whisper_preciso": False,      # beam 3 em vez de 1 (mais preciso, ~2x mais lento no seu PC)
    "analise_heatmap_ia": False,   # vídeo com gráfico "mais repetidos": False = usa o gráfico sem IA
    "guardar_projeto_edicao": True,  # guarda a receita pra corrigir legenda sem IA (ocupa disco)
    "atualizar_numeros_auto": True,
    "usar_chat_vod": True,          # live antiga: baixa o chat e usa os picos como candidatos (sem IA)
    "ia_lote": True,                # vários cortes do mesmo vídeo = 1 chamada de IA só
    "whisper_final": "small",
    "formato_corte": "curto",       # robô: "curto" (9:16), "longo" (16:9) ou "ambos"
    "duracao_longo_seg": 240,       # tamanho alvo do corte longo (3 a 8 min = horas assistidas)
    "compilacao_minutos": 8,        # compilação: vai somando cortes até chegar nisso
    "compilacao_deitada": True,     # usa o trecho original horizontal (tela cheia) quando dá       # transcrição do CORTE escolhido: "base", "small" ou "turbo"  # o robô atualiza as views do YouTube sozinho a cada 3h
    "usar_gpu_encoder": True,
    "limpar_voz_ia": True,          # RNNoise (IA) limpa a voz antes da música/efeitos; sem ele, o afftdn
    "tirar_musica_fonte": False,    # Demucs: tira a música de fundo da fonte (pesado; ⚙ Qualidade)
    "reduzir_chiado": True,         # filtro de chiado (afftdn); desligue se a live tiver música/jogo alto
    "correcoes_delta": True,        # IA manda só as palavras corrigidas (economiza ~75% dos tokens de saída)
    "cpu_threads": max(2, min(8, os.cpu_count() or 4)),
    "min_disco_gb": 2, "max_chamadas_ia_dia": 0, "timeout_ffmpeg_seg": 3600,
    "template_edicao": "Clássico",  # templates_edicao.py: legenda + efeitos (ou "Automático (IA escolhe)")
    "claude_modelo": "",            # "" = haiku no modo econômico; "sonnet" = perguntas/ganchos melhores
    "hipotese_ab": "", "agrupamento_semantico_ia": False, "autonomia_confianca": 0, "max_tarefas_pendentes": 100, "retencao_gravacoes_dias": 0, "gravacao_segmentada": False,
}

# chaves que cada perfil pode ter diferente (o resto, como a IA, é global)
CHAVES_PERFIL = ["legenda_margem", "legenda_tamanho", "legenda_palavras", "legenda_cor",
                 "faixa_estilo", "faixa_formato", "seguir_rosto", "tirar_silencios", "efeito_gancho",
                 "gancho_inicio", "tirar_vicios", "audio_padrao", "baixar_1080", "marca",
                 "nota_minima", "nota_minima_automatico", "musica_fundo", "musica_volume",
                 "gancho_distancia_min", "final_corte", "cta_texto", "plataforma_alvo", "limpar_abertura",
                 "ab_variar", "capa", "aparar_ia", "template_aprende", "horarios_postagem", "mostrar_selo", "ab_teste", "espanhol",
                 "checar_inedito", "canais", "layout", "legenda_animada", "emojis_legenda",
                 "revisor", "revisao_ia", "serie", "horario_inteligente", "estilo_corte", "texto_gancho", "vocabulario", "retranscrever_incertos", "autonomia_confianca", "hipotese_ab",
                 "template_edicao"]


_avisou_chave = False


def carregar_config(perfil=None):
    """Config completa. Com 'perfil', as chaves daquele perfil substituem as do Padrão."""
    cfg = dict(CONFIG_PADRAO)
    try:
        cfg.update(json.loads(ARQ_CONFIG.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        pass
    if cfg.get("gemini_api_key"):             # no arquivo ela fica criptografada (cofre.py)
        import cofre
        protegida = cofre.protegido(cfg["gemini_api_key"])
        cfg["gemini_api_key"] = cofre.revelar(cfg["gemini_api_key"])
        global _avisou_chave
        if protegida and not cfg["gemini_api_key"] and not _avisou_chave:
            _avisou_chave = True
            print("   ⚠ a chave do Gemini foi protegida por outra conta do Windows (ou outro PC) e não abre "
                  "aqui — cole a chave de novo em IA > Chave do Gemini.")
    if perfil and perfil != "Padrão" and perfil in cfg.get("perfis", {}):
        cfg.update({k: v for k, v in cfg["perfis"][perfil].items() if k in CHAVES_PERFIL})
        cfg["perfil_em_uso"] = perfil
    else:
        cfg["perfil_em_uso"] = "Padrão"
    return cfg


def salvar_perfil(cfg_editado, nome):
    """Grava as chaves de perfil: no Padrão ficam no topo do config.json; os outros em 'perfis'."""
    base = carregar_config()
    base.pop("perfil_em_uso", None)
    if nome == "Padrão":
        base.update({k: cfg_editado[k] for k in CHAVES_PERFIL if k in cfg_editado})
    else:
        base.setdefault("perfis", {})[nome] = {k: cfg_editado[k] for k in CHAVES_PERFIL if k in cfg_editado}
    salvar_config(base)


def nomes_perfis():
    return ["Padrão"] + sorted(carregar_config().get("perfis", {}))


def perfil_do_canal(*nomes):
    """Qual perfil usar pra um canal de origem (pela lista 'canais' de cada perfil)."""
    cfg = carregar_config()
    alvos = [re.sub(r"\W", "", str(n).lower()) for n in nomes if n]
    for nome, p in cfg.get("perfis", {}).items():
        for c in p.get("canais", []):
            c = re.sub(r"\W", "", str(c).lower())
            if c and any(c == a or (len(c) > 3 and c in a) for a in alvos):
                return nome
    return "Padrão"


def salvar_config(cfg):
    cfg = {k: v for k, v in cfg.items() if k != "perfil_em_uso"}
    if cfg.get("gemini_api_key"):             # nunca grava a chave em texto aberto
        import cofre
        cfg["gemini_api_key"] = cofre.proteger(cfg["gemini_api_key"])
    salvar_json(ARQ_CONFIG, cfg)


_dono_render = None
_cfg_em_uso = {}


@contextmanager
def contexto_render():
    global _dono_render
    with exclusividade(Path(__file__).resolve().parent / '.render.lock'):
        anterior = _dono_render
        _dono_render = threading.get_ident()
        try:
            yield
        finally:
            _dono_render = anterior


def _numero(valor, padrao, minimo, maximo):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return padrao
    return max(minimo, min(maximo, v)) if math.isfinite(v) else padrao


def aplicar_config(cfg=None):
    global _cfg_em_uso
    if _dono_render is not None and _dono_render != threading.get_ident():
        return False  # A prévia não pode alterar o estilo de um corte em andamento.
    global MARGEM_LEGENDA, TAMANHO_LEGENDA, PALAVRAS_POR_BLOCO, COR_LEGENDA_DESTAQUE
    global FAIXA_COR_CIMA, FAIXA_COR_BAIXO, FAIXA_LINHA_COR, COR_DESTAQUE, COR_TEXTO
    global MOSTRAR_SELO_CANAL, IA_PRINCIPAL, IA_RESERVA, ECONOMICO, MODELO_LOCAL, IA_QUALIDADE
    global GEMINI_API_KEY, GEMINI_MODELO, FAIXA_FORMATO
    global SEGUIR_ROSTO, TIRAR_SILENCIOS, EFEITO_GANCHO, MARCA, NOTA_MINIMA
    global GANCHO_INICIO, TIRAR_VICIOS, AUDIO_PADRAO, BAIXAR_1080
    global AB_TESTE, ESPANHOL, CHECAR_INEDITO, USAR_APRENDIZADO, USAR_ASSUNTOS, PERFIL_EM_USO
    global LAYOUT, LEGENDA_ANIMADA, EMOJIS_LEGENDA, REVISOR, REVISAO_IA, SERIE
    cfg = cfg or carregar_config()
    _cfg_em_uso = dict(cfg)
    MARGEM_LEGENDA = int(cfg["legenda_margem"])
    TAMANHO_LEGENDA = int(cfg["legenda_tamanho"])
    PALAVRAS_POR_BLOCO = max(1, int(cfg["legenda_palavras"]))
    COR_LEGENDA_DESTAQUE = cfg["legenda_cor"]
    estilo = ESTILOS_FAIXA.get(cfg["faixa_estilo"], ESTILOS_FAIXA["Vermelho clássico"])
    FAIXA_COR_CIMA, FAIXA_COR_BAIXO, FAIXA_LINHA_COR, COR_DESTAQUE, COR_TEXTO = estilo
    MOSTRAR_SELO_CANAL = bool(cfg["mostrar_selo"])
    IA_PRINCIPAL = cfg["ia_principal"]
    IA_RESERVA = bool(cfg["ia_reserva"])
    IA_QUALIDADE = ia_motor.nivel_qualidade(cfg)
    ECONOMICO = IA_QUALIDADE == "economico"
    MODELO_LOCAL = cfg.get("modelo_local") or "qwen2.5:3b"
    GEMINI_API_KEY = (cfg.get("gemini_api_key") or "").strip()
    FAIXA_FORMATO = cfg.get("faixa_formato") or "Rasgada"
    SEGUIR_ROSTO = bool(cfg.get("seguir_rosto", True))
    TIRAR_SILENCIOS = bool(cfg.get("tirar_silencios", True))
    EFEITO_GANCHO = bool(cfg.get("efeito_gancho", True))
    GANCHO_INICIO = bool(cfg.get("gancho_inicio", True))
    global GANCHO_DISTANCIA_MIN, NOTA_MINIMA_AUTO, MUSICA_FUNDO, MUSICA_VOLUME
    GANCHO_DISTANCIA_MIN = _numero(cfg.get("gancho_distancia_min"), 10.0, 0, 120)
    NOTA_MINIMA_AUTO = _numero(cfg.get("nota_minima_automatico"), 6.0, 0, 10)
    MUSICA_FUNDO = bool(cfg.get("musica_fundo", True))
    MUSICA_VOLUME = _numero(cfg.get("musica_volume"), 0.16, 0.0, 0.6)
    global FINAL_CORTE, CTA_TEXTO, PLATAFORMA_ALVO, LIMPAR_ABERTURA, AB_VARIAR, GERAR_CAPA
    FINAL_CORTE = cfg.get("final_corte") if cfg.get("final_corte") in ("cta", "loop", "nada") else "cta"
    CTA_TEXTO = str(cfg.get("cta_texto") or "").strip()[:26].upper()
    import acabamento
    PLATAFORMA_ALVO = (cfg.get("plataforma_alvo") if cfg.get("plataforma_alvo") in acabamento.PLATAFORMAS
                       else "todas")
    LIMPAR_ABERTURA = bool(cfg.get("limpar_abertura", True))
    AB_VARIAR = (cfg.get("ab_variar") if cfg.get("ab_variar") in ("pergunta", "template", "ambos", "alternar")
                 else "alternar")
    GERAR_CAPA = bool(cfg.get("capa", True))
    global CHECAR_MUSICA
    CHECAR_MUSICA = bool(cfg.get("checar_musica", True))
    global APARAR_IA, TEMPLATE_APRENDE
    APARAR_IA = bool(cfg.get("aparar_ia", True))
    TEMPLATE_APRENDE = bool(cfg.get("template_aprende", True))
    TIRAR_VICIOS = bool(cfg.get("tirar_vicios", True))
    AUDIO_PADRAO = bool(cfg.get("audio_padrao", True))
    BAIXAR_1080 = bool(cfg.get("baixar_1080", True))
    global MODO_PC_FRACO
    MODO_PC_FRACO = bool(cfg.get("modo_pc_fraco", False))
    if MODO_PC_FRACO:                      # PC fraco: baixa em 720p (decodificar 1080p pesa em 2 núcleos)
        BAIXAR_1080 = False
    AB_TESTE = bool(cfg.get("ab_teste", False))
    ESPANHOL = bool(cfg.get("espanhol", False))
    CHECAR_INEDITO = bool(cfg.get("checar_inedito", True))
    USAR_APRENDIZADO = bool(cfg.get("usar_aprendizado", True))
    USAR_ASSUNTOS = bool(cfg.get("usar_assuntos", True))
    PERFIL_EM_USO = cfg.get("perfil_em_uso", "Padrão")
    LAYOUT = cfg.get("layout") if cfg.get("layout") in ("auto", "normal", "podcast", "jogo") else "auto"
    global CLEAN, TEXTO_GANCHO, TEMPLATE_EDICAO
    TEMPLATE_EDICAO = cfg.get("template_edicao") or "Clássico"
    CLEAN = cfg.get("estilo_corte") == "clean"
    TEXTO_GANCHO = bool(cfg.get("texto_gancho", True))
    LEGENDA_ANIMADA = bool(cfg.get("legenda_animada", True))
    EMOJIS_LEGENDA = bool(cfg.get("emojis_legenda", True))
    REVISOR = bool(cfg.get("revisor", True))
    REVISAO_IA = bool(cfg.get("revisao_ia", False))
    SERIE = bool(cfg.get("serie", True))
    MARCA = (cfg.get("marca") or "").strip()
    try:
        NOTA_MINIMA = float(cfg.get("nota_minima") or 0)
    except (TypeError, ValueError):
        NOTA_MINIMA = 0
    GEMINI_MODELO = cfg.get("gemini_modelo") or "gemini-flash-latest"
    if GEMINI_MODELO in ("gemini-2.5-flash", "gemini-2.0-flash"):     # modelos aposentados
        GEMINI_MODELO = "gemini-flash-latest"


def cor_ass(hex_cor):
    """'#RRGGBB' -> '&H00BBGGRR&' (formato de cor da legenda .ass)"""
    h = hex_cor.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


aplicar_config()


# ============================================================
# Utilidades
# ============================================================
_callback_progresso = ContextVar("progresso", default=None)
_job_atual = ContextVar("job", default=None)
_voz_limpa = ContextVar("voz_limpa", default=False)    # a voz deste corte já passou pelo RNNoise
_supercut = ContextVar("supercut", default=None)       # {'marcas', 'total'} enquanto monta um supercut
_cronometro = ContextVar("cronometro", default=None)    # [(hora, mensagem)] do corte em andamento

def log(msg):
    marcas = _cronometro.get()
    if marcas is not None:
        marcas.append((time.time(), str(msg)))
    callback = _callback_progresso.get()
    if callback:
        callback(msg)
    print(f"\n>>> {msg}", flush=True)


from desempenho import etapas_do_log, registrar_tempos as _registrar_tempos  # noqa: E402
from baixador import baixar_trecho  # noqa: E402 - mudou pro baixador.py na 3.21


def registrar_tempos(marcas, saida=None, duracao=None, arquivo=None):
    return _registrar_tempos(marcas, saida, duracao, arquivo, encoder=_encoder_h264_cache or "")


def parse_tempo(t) -> float:
    partes = [float(p) for p in str(t).strip().split(":")]
    seg = 0.0
    for p in partes:
        seg = seg * 60 + p
    return seg


def fmt_tempo(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def nome_seguro(texto: str, limite=50) -> str:
    texto = re.sub(r"[^\w\s-]", "", texto, flags=re.UNICODE).strip()
    texto = re.sub(r"\s+", "_", texto)
    return texto[:limite] or "corte"


# decodificação pelo chip de vídeo: o mesmo que codifica (Intel decodifica 3x mais rápido que 2 núcleos)
_DECODER_HW = {"h264_qsv": "qsv", "h264_nvenc": "cuda", "h264_amf": "d3d11va"}
_EXT_VIDEO = {".mp4", ".mkv", ".ts", ".flv", ".webm", ".mov", ".m4v", ".avi", ".m3u8"}
_decodificar_hw = True
_falhas_hw_decod = [0]


def _com_decodificador_hw(cmd):
    """Põe '-hwaccel' antes de cada vídeo de entrada quando a saída usa o encoder de hardware.
    Os quadros voltam pra memória normal, então todos os filtros continuam funcionando."""
    if not _decodificar_hw or "-hwaccel" in cmd or not carregar_config().get("usar_gpu_decoder", True):
        return cmd
    enc = next((cmd[i + 1] for i, x in enumerate(cmd[:-1]) if x == "-c:v" and cmd[i + 1] in _DECODER_HW), None)
    if not enc:
        return cmd
    # montagens com vários filtros (-filter_complex) e filtros que guardam quadros (duplicar, emendar,
    # selecionar) estouram a memória fixa do chip ("Failed to allocate a qsv frame from a fixed pool"):
    # esses decodificam no processador. O chip fica com o recorte e os intermediários simples.
    if "-filter_complex" in cmd:
        return cmd
    filtros = " ".join(str(cmd[i + 1]) for i, x in enumerate(cmd[:-1]) if x in ("-vf", "-af"))
    if re.search(r"\b(split|concat|select|reverse|loop|tpad|xfade)\b", filtros):
        return cmd
    novo = []
    for i, x in enumerate(cmd):
        if x == "-i" and i + 1 < len(cmd) and Path(str(cmd[i + 1])).suffix.lower() in _EXT_VIDEO:
            novo += ["-hwaccel", _DECODER_HW[enc]]
        novo.append(x)
    return novo


def _sem_hwaccel(cmd):
    novo, pular = [], False
    for x in cmd:
        if pular:
            pular = False
            continue
        if x == "-hwaccel":
            pular = True
            continue
        novo.append(x)
    return novo


def _tempo_curto(s):
    s = max(0, int(s))
    return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def _executar(cmd, cwd=None, progresso=None):
    """subprocess.run de sempre; com progresso=(rótulo, duração em s) lê o 'time=' do ffmpeg e
    avisa a cada 25% quanto falta."""
    limite = max(60, int(carregar_config().get("timeout_ffmpeg_seg", 3600)))
    if not progresso or not progresso[1]:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=limite,
                              encoding="utf-8", errors="replace", creationflags=SEM_JANELA)
    rotulo, duracao = progresso
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=SEM_JANELA)
    saida = []
    leitor = threading.Thread(target=lambda: saida.append(proc.stdout.read()), daemon=True)
    leitor.start()
    erro, janela, t0, proximo = bytearray(), b"", time.time(), 0.25
    try:
        while True:
            pedaco = proc.stderr.read(256)
            if not pedaco:
                break
            erro += pedaco
            janela = (janela + pedaco)[-300:]
            achados = re.findall(rb"time=(\d+):(\d+):(\d+(?:\.\d+)?)", janela)
            if achados:
                h, m, s = achados[-1]
                feito = min(1.0, (int(h) * 3600 + int(m) * 60 + float(s)) / duracao)
                if proximo <= feito < 0.99:
                    gasto = time.time() - t0
                    log(f"{rotulo}: {int(feito * 100)}% (falta ~{_tempo_curto(gasto / feito - gasto)})")
                    while proximo <= feito:
                        proximo += 0.25
            if time.time() - t0 > limite:
                proc.kill()
                raise subprocess.TimeoutExpired(cmd, limite)
        proc.wait(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
        leitor.join(5)
        proc.stdout.close()
        proc.stderr.close()
    return subprocess.CompletedProcess(cmd, proc.returncode, (saida[0] if saida else b"").decode("utf-8", "replace"),
                                       bytes(erro).decode("utf-8", "replace"))


def rodar(cmd, cwd=None, progresso=None):
    global _decodificar_hw
    if Path(str(cmd[0])).stem.lower() == 'ffmpeg':
        n = str(max(1, min(os.cpu_count() or 4, int(carregar_config().get('cpu_threads', 4)))))
        cmd = [cmd[0], '-threads', n, '-filter_threads', n, '-filter_complex_threads', n,
               *cmd[1:-1], '-threads', n, cmd[-1]]
        cmd = _com_decodificador_hw(cmd)
    r = _executar(cmd, cwd, progresso)
    if r.returncode != 0 and "-hwaccel" in cmd:
        # algum vídeo que o chip não sabe decodificar (ex.: AV1 num Intel antigo): volta pro processador
        print("   ⚠ o chip de vídeo não decodificou esse arquivo — decodificando no processador.")
        _falhas_hw_decod[0] += 1
        if _falhas_hw_decod[0] >= 3:           # falhou várias vezes: desliga pro resto da sessão
            _decodificar_hw = False
        cmd = _sem_hwaccel(cmd)
        r = _executar(cmd, cwd, progresso)
    if r.returncode != 0:
        # acelerador de vídeo (GPU) falhou nesse arquivo? refaz no processador e não tenta mais a GPU
        hw = next((i for i, x in enumerate(cmd[:-1]) if x == "-c:v" and cmd[i + 1] in _ENCODERS_HW), None)
        if hw is not None:
            global _encoder_h264_cache
            print(f"   ⚠ o acelerador de vídeo ({cmd[hw + 1]}) falhou — refazendo no processador.")
            _encoder_h264_cache = "libx264"
            novo = (cmd[:hw] + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19"]
                    + cmd[_fim_args_encoder(cmd, hw):])
            return _rodar_direto(novo, cwd)
        print(r.stderr[-3000:])
        raise RuntimeError(f"Erro ao rodar: {cmd[0]}")
    return r


_ENCODERS_HW = ("h264_nvenc", "h264_qsv", "h264_amf")
_FLAGS_ENCODER = {"-preset", "-cq", "-global_quality", "-look_ahead", "-rc", "-qp_i", "-qp_p", "-crf"}


def _fim_args_encoder(cmd, hw):
    """Onde terminam os argumentos do encoder que começa em cmd[hw] ('-c:v nome -flag valor ...')."""
    i = hw + 2
    while i < len(cmd) - 1 and cmd[i] in _FLAGS_ENCODER:
        i += 2
    return i


def _rodar_direto(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       timeout=max(60, int(carregar_config().get("timeout_ffmpeg_seg", 3600))),
                       encoding="utf-8", errors="replace", creationflags=SEM_JANELA)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise RuntimeError(f"Erro ao rodar: {cmd[0]}")
    return r


_ffmpeg_verificado = False
_encoder_h264_cache = None


def checar_ffmpeg():
    global _ffmpeg_verificado
    if not _ffmpeg_verificado:
        from recursos import configurar_ffmpeg
        configurar_ffmpeg()
        _ffmpeg_verificado = True


def filtro_chiado():
    """Redutor de chiado do microfone (opcional em ⚙ Qualidade)."""
    return ",afftdn=nf=-25" if carregar_config().get("reduzir_chiado", True) else ""


def filtro_limpeza_voz(jogo=False):
    """',arnndn=…' (RNNoise: IA que limpa a voz — no teste tirou 28 dB de ruído contra 6 dB do afftdn,
    mexendo menos na voz) ou o afftdn de antes. jogo=True: sem RNNoise (apagaria o som do jogo).
    Usado num passo separado (separar_voz.limpar_voz), nunca dentro do render: o arnndn às vezes
    trava no fechamento do FFmpeg."""
    modelo = PASTA_PROJETO / "modelos" / "rnnoise_voz.rnnn"
    if jogo or not carregar_config().get("limpar_voz_ia", True) or not modelo.exists():
        return filtro_chiado()
    caminho = str(modelo.resolve()).replace("\\", "/").replace(":", r"\:")
    return f",arnndn=m='{caminho}'"


def detectar_encoder_h264() -> str:
    """Descobre UMA vez se o PC tem encoder H.264 por hardware (NVENC/Nvidia, QSV/Intel, AMF/AMD)
    funcionando de verdade. O teste usa um vídeo de tamanho real (o QSV da Intel recusa imagem
    minúscula) e mostra no log qual ficou. Sem nenhum, usa o libx264 (processador)."""
    global _encoder_h264_cache
    if _encoder_h264_cache is not None:
        return _encoder_h264_cache
    checar_ffmpeg()
    nomes = {"h264_nvenc": "placa Nvidia (NVENC)", "h264_qsv": "vídeo integrado Intel (Quick Sync)",
             "h264_amf": "placa AMD (AMF)"}
    for candidato in ("h264_nvenc", "h264_qsv", "h264_amf"):
        try:
            r = subprocess.run(
                ["ffmpeg", "-hide_banner", "-v", "error", "-f", "lavfi",
                 "-i", "testsrc2=s=640x360:r=30:d=0.5", "-pix_fmt", "nv12",
                 "-c:v", candidato, "-f", "null", "-"],
                capture_output=True, timeout=15, creationflags=SEM_JANELA
            )
            if r.returncode == 0:
                _encoder_h264_cache = candidato
                print(f"   🎞 acelerando o vídeo com {nomes[candidato]}")
                return _encoder_h264_cache
        except Exception:
            continue
    _encoder_h264_cache = "libx264"
    print("   🎞 sem acelerador de vídeo — usando o processador (libx264)")
    return _encoder_h264_cache


def args_encoder_video(intermediario=False, crf_padrao=17):
    '''Encoder de vídeo: GPU se disponível e habilitado, senão libx264. Intermediário: quase sem
    perda (ainda será recomprimido). Final: mais bitrate (as plataformas recomprimem ao receber).'''
    usar_gpu = bool(carregar_config().get("usar_gpu_encoder", True))
    enc = detectar_encoder_h264() if usar_gpu else "libx264"
    if intermediario:
        if enc == "libx264":
            return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "16"]
        crf_padrao = 15
    if enc == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(crf_padrao)]
    if enc == "h264_qsv":
        import desempenho
        if not intermediario and desempenho.suporta_look_ahead():
            # LA-ICQ 19 no final: ~10 Mbps num 1080x1920 (o dobro do ICQ puro, mesma velocidade)
            return ["-c:v", "h264_qsv", "-global_quality", "19", "-look_ahead", "1"]
        crf_padrao = 15 if not intermediario else crf_padrao
        return ["-c:v", "h264_qsv", "-global_quality", str(crf_padrao)]
    if enc == "h264_amf":
        return ["-c:v", "h264_amf", "-rc", "cqp", "-qp_i", str(crf_padrao), "-qp_p", str(crf_padrao)]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf_padrao)]


def duracao_video(arquivo: Path) -> float:
    if Path(arquivo).suffix.lower() == '.m3u8' and Path(arquivo).is_file():
        from gravacao_segmentada import duracao
        return duracao(arquivo)
    r = rodar(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(arquivo)])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


# ============================================================
# 1. Obter o trecho
# ============================================================
def recortar_local(arquivo, inicio, fim, pasta: Path, meta=None):
    log("Recortando o trecho do arquivo...")
    saida = pasta / "original.mp4"
    total = duracao_video(Path(arquivo))
    if total and inicio >= total:
        raise ValueError('O início solicitado está além da gravação disponível.')
    if total:
        fim = min(fim, total)
    if fim <= inicio:
        raise ValueError('Não há vídeo disponível no intervalo solicitado.')
    cmd = ["-map", "0:v:0", "-map", "0:a:0?", *args_encoder_video(intermediario=True),
           "-c:a", "aac", "-avoid_negative_ts", "make_zero", str(saida)]
    rodar(["ffmpeg", "-y", "-fflags", "+discardcorrupt", "-ss", f"{inicio:.2f}", "-i", str(arquivo),
           "-t", f"{fim - inicio:.2f}", *cmd], progresso=("Recortando", fim - inicio))
    if duracao_video(saida) < 1:              # live com "buraco" (anúncio/queda): procura decodificando
        print("   ⚠ recorte rápido saiu vazio — tentando do jeito lento (mais preciso)...")
        rodar(["ffmpeg", "-y", "-fflags", "+discardcorrupt", "-i", str(arquivo), "-ss", f"{inicio:.2f}",
               "-t", f"{fim - inicio:.2f}", *cmd])
    if duracao_video(saida) < 1:
        raise RuntimeError("o trecho da gravação saiu vazio (a live pode ter caído ou estar em anúncio "
                           "nesse momento).")
    base = {"titulo": Path(arquivo).stem, "canal": "", "thumbnail": None}
    base.update(meta or {})
    return saida, base


def baixar_imagem(url, destino: Path):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            destino.write_bytes(r.read())
        from PIL import Image
        Image.open(destino).verify()
        return destino
    except Exception as e:
        print(f"   ⚠ Não consegui baixar a thumbnail ({e}).")
        return None


# ============================================================
# 2. Transcrição local (sem placa de vídeo)
# ============================================================
_modelo_cache = {}


MODELOS_WHISPER = {"turbo": "large-v3-turbo"}


def modelo_final(nome=None):
    """Qual Whisper usar na legenda do corte. 'auto' = o do config (small por padrão): a busca de
    momentos continua no base (rápido); só o corte final, de ~1 minuto, usa o mais preciso."""
    nome = nome or MODELO_WHISPER
    if nome == "auto":
        cfg = carregar_config()
        padrao = "base" if cfg.get("modo_pc_fraco") else "small"     # modo PC fraco: legenda ~2x mais rápida
        nome = str(cfg.get("whisper_final") or padrao)
        if cfg.get("modo_pc_fraco") and nome == "small":   # o "small" de fábrica sempre vinha no config e
            nome = "base"                                 # o PC fraco nunca usava o base que promete
    return nome if nome in ("tiny", "base", "small", "medium", "turbo", "large-v3") else "small"


def carregar_whisper(nome):
    from faster_whisper import WhisperModel
    nome = MODELOS_WHISPER.get(nome, nome)
    if nome not in _modelo_cache:
        opcoes = dict(device="cpu", compute_type="int8",
                      cpu_threads=max(1, min(os.cpu_count() or 4, int(carregar_config().get("cpu_threads", max(1, (os.cpu_count() or 4)-2))))))
        try:     # já baixado: abre direto do PC, sem consultar a internet (nada de "baixando" a cada corte)
            _modelo_cache[nome] = WhisperModel(nome, local_files_only=True, **opcoes)
            log(f"Whisper '{nome}' pronto (já estava no PC).")
        except Exception:
            log(f"Baixando o Whisper '{nome}' — só desta vez, depois fica salvo no PC...")
            _modelo_cache[nome] = WhisperModel(nome, **opcoes)
    return _modelo_cache[nome]


def extrair_audio(video: Path, destino: Path):
    rodar(["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(destino)])
    return destino


def ler_wav(caminho: Path):
    """Lê o .wav (16 kHz mono, feito pelo ffmpeg) direto, sem depender do PyAV."""
    import wave
    import numpy as np
    with wave.open(str(caminho), "rb") as w:
        dados = w.readframes(w.getnframes())
    return np.frombuffer(dados, dtype=np.int16).astype(np.float32) / 32768.0


def dica_transcricao(meta, contexto=""):
    """Frase com nomes do canal/título: o Whisper usa como 'vocabulário' e erra menos nomes."""
    partes = []
    if meta.get("canal"):
        partes.append(f"Live/vídeo de {meta['canal']}.")
    try:                                   # nomes que a IA/você já corrigiram neste canal
        import ia_aprende
        nomes = ia_aprende.dica_whisper(meta.get("canal"))
        if nomes:
            partes.append(nomes)
    except Exception:
        pass
    if meta.get("titulo"):
        partes.append(f"Título: {meta['titulo']}.")
    if contexto and len(contexto) < 300:
        partes.append(contexto)
    vocabulario = carregar_config(PERFIL_EM_USO).get("vocabulario", "")
    if vocabulario:
        partes.append("Vocabulário: " + str(vocabulario)[:220])
    texto = " ".join(partes).strip()
    return texto[:400] if texto else None


def transcrever(video: Path, pasta: Path, modelo=None, dica=None, wav_pronto: Path | None = None):
    audio = Path(wav_pronto) if wav_pronto and Path(wav_pronto).exists() else extrair_audio(video, pasta / "audio.wav")
    log("Transcrevendo o áudio no processador...")
    if dica:
        print(f"   usando nomes do vídeo pra acertar a legenda: {dica[:80]}...")
    amostras = ler_wav(audio)
    cfg = carregar_config(PERFIL_EM_USO)
    modelo = modelo_final(modelo)
    print(f"   modelo da legenda: {modelo}")
    segs, _ = carregar_whisper(modelo).transcribe(
        amostras, language="pt", word_timestamps=True, vad_filter=True,
        beam_size=3 if cfg.get("whisper_preciso") else 1,
        initial_prompt=dica, condition_on_previous_text=False)   # sem 'eco' do trecho anterior (loops)
    palavras = []
    for seg in segs:
        for w in seg.words or []:
            if w.word.strip():
                palavras.append({"t": w.word.strip(), "ini": round(w.start, 2),
                                 "fim": round(w.end, 2), "confianca": round(float(getattr(w, "probability", 0)), 3),
                                 "orig_ini": round(w.start, 2), "orig_fim": round(w.end, 2)})
    if cfg.get('retranscrever_incertos', False):
        janelas = []
        for p in palavras:
            if p.get('confianca', 1) < 0.6 and all(abs(p['ini'] - a) > 6 for a, _ in janelas):
                janelas.append((max(0, p['ini'] - 2), min(len(amostras) / 16000, p['fim'] + 3)))
        for a, b in janelas[:3]:
            segmentos, _ = carregar_whisper(modelo).transcribe(
                amostras[int(a * 16000):int(b * 16000)], language='pt', word_timestamps=True,
                vad_filter=True, beam_size=5, initial_prompt=dica)
            novas = [dict(t=w.word.strip(), ini=round(a+w.start, 2), fim=round(a+w.end, 2),
                          confianca=round(float(w.probability), 3), orig_ini=round(a+w.start, 2), orig_fim=round(a+w.end, 2))
                     for seg in segmentos for w in (seg.words or []) if w.word.strip() and 0 <= w.start < w.end <= b-a]
            antigas = [p for p in palavras if a <= p['ini'] and p['fim'] <= b]
            # Não substitui palavras que atravessam as bordas da janela.
            atravessa = any(p['ini'] < a < p['fim'] or p['ini'] < b < p['fim'] for p in palavras)
            if novas and antigas and not atravessa and sum(p['confianca'] for p in novas)/len(novas) > sum(p.get('confianca', 0) for p in antigas)/len(antigas):
                palavras = sorted([p for p in palavras if not (a <= p['ini'] and p['fim'] <= b)] + novas, key=lambda p:p['ini'])
    import otimizador_corte
    palavras, repetidas = otimizador_corte.limpar_repeticoes(palavras)
    if repetidas:
        print(f"   {repetidas} palavra(s) repetida(s) pelo Whisper removida(s) da legenda.")
    print(f"   {len(palavras)} palavras.")
    return palavras

from ia_cortes import (  # noqa: E402,F401 - ia_cortes.py
    IAS, URL_GEMINI, URL_OLLAMA, _CLAUDE_ENXUTO, _EXEMPLOS_PERGUNTA, _GEMINI_LISTA, _ITEM_PERGUNTA,
    _cmd_claude, _erro_google, _gemini_modelos_disponiveis, _gemini_req, _guia_estilo, _julgar,
    _ler_resposta, _limpar_pergunta, _modelo_para, _motivo_escalar, _nomes_confirmados, _origem_ia,
    _pedido_corte, _prompt_corte, _resposta_util, _sem_ia, _transcricao_numerada, _validar_dados, achar_cli,
    claude_json, codex_json, comando_claude, extrair_frames, extrair_json, gemini_api_json, gemini_json,
    ia_json, mosaico, ollama_json, ollama_rodando, pensar_com_ia, pensar_lote,
)




from faixas import (  # noqa: E402,F401 - faixa, foto do topo, selos e emojis: faixas.py
    FONTES_EMOJI, FORMATOS_FAIXA, _fonte_rasgada, _papel_colorido, _selo, _sombra_de, _texto_desenhar,
    _texto_layout, emoji_png, encaixar_inteira, estilo_thumbnail, faixa_adesivo, faixa_fita, faixa_pincelada,
    faixa_rasgada, faixa_reta_png, fonte, montar_topo, quebrar_linhas, selo_png,
)

from legendas import (  # noqa: E402,F401 - legendas .ass/.srt: legendas.py
    COR_FALANTE_B, blocos_legenda, gerar_ass, gerar_ass_blocos, gerar_srt, posicao_gancho, tempo_ass, tempo_srt,
    texto_gancho_ass,
)

from render import (  # noqa: E402,F401 - render.py
    _duracao_util, info_video, renderizar, tem_audio,
)




# ============================================================
# Função principal (usada pelo CLI e pelo monitor)
# ============================================================
def cfg_estilo():
    for nome, est in ESTILOS_FAIXA.items():
        if est[0] == FAIXA_COR_CIMA:
            return nome
    return ""


def escrever_saidas(saida: Path, ficha: dict, meta: dict):
    chamada = f"{ficha['chamada']}\n\n" if ficha.get("chamada") else ""
    saida.with_suffix(".txt").write_text(
        f"{ficha.get('titulo', '')}\n\n{chamada}{' '.join(ficha.get('hashtags', []))}\n\n"
        f"Fonte: {meta.get('canal', '')} — {meta.get('titulo', '')}\n", encoding="utf-8")
    salvar_json(saida.with_suffix(".json"), ficha)


def _palavras_chave(texto):
    comuns = {"para", "pelo", "pela", "com", "que", "não", "nao", "uma", "umas", "esse", "essa", "isso",
              "ele", "ela", "eles", "elas", "dele", "dela", "seu", "sua", "foi", "vai", "tem", "mais",
              "muito", "quando", "como", "sobre", "depois", "antes", "live", "corte", "cortes", "video"}
    return {w for w in re.findall(r"[a-zà-ú0-9]+", texto.lower()) if len(w) >= 4 and w not in comuns}


class LoggerMudo:
    """Não deixa o yt-dlp encher o log com erro de checagem opcional."""
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def contar_parecidos(titulo, canal=""):
    """Quantos vídeos desta semana no YouTube têm título parecido (outros cortes do mesmo lance).
    Devolve None se não conseguir checar."""
    try:
        import yt_dlp
        from urllib.parse import quote
    except ImportError:
        return None
    chave = _palavras_chave(titulo)
    if len(chave) < 2:
        return None
    termos = " ".join(([canal] if canal else []) + sorted(chave, key=len, reverse=True)[:4])
    url = f"https://www.youtube.com/results?search_query={quote(termos)}&sp=EgIIAw%253D%253D"
    try:
        import baixador
        with yt_dlp.YoutubeDL(baixador.opcoes_ytdlp(extract_flat="in_playlist", playlistend=15,
                                                    skip_download=True, logger=LoggerMudo())) as y:
            info = y.extract_info(url, download=False)
    except Exception:
        return None
    n = 0
    for e in info.get("entries") or []:
        outras = _palavras_chave(e.get("title") or "")
        if chave and len(chave & outras) / len(chave) >= 0.5:
            n += 1
    return n


def versao_espanhol(video, palavras, textos, dados, meta, ficha, saida, pasta, modo,
                    foto_path, eh_thumbnail, expr_x, gancho_t, boom, legenda, layout=None, extras=None,
                    margem=None, y_ajuste=0, estilo_render=None, previa=None):
    blocos = blocos_legenda(palavras, textos)
    frases = [" ".join(x["t"] for x in b) for b in blocos]
    prompt = ("Traduza para espanhol latino-americano, natural e com gírias leves, mantendo o tom de "
              "corte viral. Responda APENAS JSON com: \"pergunta\" (MAIÚSCULAS, termina com ??), "
              "\"destaque\" (1-2 palavras da pergunta), \"titulo\", \"hashtags\" (3-5, em espanhol) e "
              f"\"blocos\" (lista com EXATAMENTE {len(frases)} textos, um por item, na mesma ordem).\n\n"
              + json.dumps({"pergunta": dados["pergunta"], "titulo": dados.get("titulo", ""),
                            "hashtags": dados.get("hashtags", []), "blocos": frases}, ensure_ascii=False))
    log("Traduzindo pra espanhol (1 chamada curta de IA)...")
    es = ia_json(prompt, tarefa="espanhol")
    if not es or len(es.get("blocos", [])) != len(frases):
        print("   ⚠ a tradução não veio completa — pulando a versão em espanhol.")
        return None
    pasta_es = saida.parent / "espanhol"
    pasta_es.mkdir(exist_ok=True)
    if CLEAN:
        tp, fp, yp = None, None, 0
    else:
        tp, fp, yp = montar_topo(foto_path, es["pergunta"], es.get("destaque"), meta.get("canal", ""),
                                 pasta, inteira=eh_thumbnail, so_faixa=bool(layout))
        yp += y_ajuste
    tempos = []
    for i, b in enumerate(blocos):
        fim_b = b[-1]["fim"] + 0.2
        if i + 1 < len(blocos):
            fim_b = min(fim_b, blocos[i + 1][0]["ini"])
        tempos.append((b[0]["ini"], fim_b, es["blocos"][i]))
    global MARGEM_LEGENDA
    antes, MARGEM_LEGENDA = MARGEM_LEGENDA, (MARGEM_LEGENDA if margem is None else margem)
    try:
        ass = gerar_ass_blocos(tempos if legenda else [], pasta / "legenda_es.ass",
                               duracao_video(video) + (previa[1] - previa[0] if previa else 0))
    finally:
        MARGEM_LEGENDA = antes
    saida_es = pasta_es / (nome_seguro(es.get("titulo") or saida.stem) + ".mp4")
    renderizar(video, tp, ass, saida_es, modo, fp, yp, expr_x, gancho_t, boom, layout=layout, extras=extras,
               estilo_render=estilo_render, previa=previa)
    ficha_es = dict(ficha, pergunta=es["pergunta"], titulo=es.get("titulo", ""),
                    hashtags=es.get("hashtags", []), idioma="es", grupo_ab=None, variante=None)
    ficha_es.pop("capa", None)
    escrever_saidas(saida_es, ficha_es, meta)
    print(f"   versão em espanhol: {es['pergunta']}")
    return saida_es


def _rostos_na_tela(analise, painel, y0, altura):
    """Converte os rostos da análise pra posição na tela final 1080x1920.
    painel = (w, h, x, y) do recorte no vídeo original; ele é esticado pra 1080 x 'altura' em y0."""
    if not analise:
        return []
    W, H = analise["w"], analise["h"]
    cw, ch, cx0, cy0 = painel
    k = altura / ch
    saida = []
    for _, rostos in analise["amostras"]:
        for cx, cy, bw, bh in rostos:
            px, py = cx * W, cy * H
            if not (cx0 <= px <= cx0 + cw and cy0 <= py <= cy0 + ch) or bw < 0.04:
                continue
            topo = y0 + (py - bh * H * 0.6 - cy0) * k
            base = y0 + (py + bh * H * 0.6 - cy0) * k
            saida.append((max(y0, topo), min(y0 + altura, base)))
    return saida


def _faixa_longe_dos_rostos(rostos_px, y_faixa, faixa_png, limite_cima):
    """Se a faixa tampa rosto em boa parte do vídeo, sobe ela (até 'limite_cima')."""
    if not rostos_px or not faixa_png:
        return y_faixa
    from PIL import Image
    alt = Image.open(faixa_png).height
    ini, fim = y_faixa + alt * 0.25, y_faixa + alt * 0.85     # parte "sólida" da faixa
    batem = [r for r in rostos_px if r[0] < fim and r[1] > ini]
    if len(batem) < 0.3 * len(rostos_px):
        return y_faixa
    topo = sorted(r[0] for r in batem)[int(len(batem) * 0.2)]
    novo = int(topo - alt * 0.85 - 10)
    return max(limite_cima, min(y_faixa, novo))


def _revisar_com_ia(saida: Path, pasta: Path):
    """Revisão opcional: 4 quadros do corte pronto numa imagem só, 1 chamada curta."""
    from PIL import Image
    dur = duracao_video(saida) or 10
    folha = Image.new("RGB", (300 * 2, 534 * 2))            # imagem pequena = poucos tokens
    for i, frac in enumerate((0.2, 0.4, 0.6, 0.8)):
        f = pasta / f"rev_{i}.jpg"
        rodar(["ffmpeg", "-y", "-ss", f"{dur * frac:.2f}", "-i", str(saida), "-frames:v", "1",
               "-vf", "scale=300:534", "-q:v", "4", str(f)])
        if f.exists():
            folha.paste(Image.open(f).convert("RGB"), ((i % 2) * 300, (i // 2) * 534))
    img = pasta / "revisao.jpg"
    folha.save(img, quality=80)
    log("Revisão rápida com IA (1 imagem)...")
    desenho = ("vídeo em tela cheia, legenda embaixo e a pergunta escrita no alto nos primeiros segundos"
               if CLEAN else "foto em cima, faixa colorida com a pergunta no meio e vídeo embaixo com legenda")
    prompt = (f"Esta imagem tem 4 quadros de um vídeo vertical já editado ({desenho}). Olhe SÓ problemas "
              "visuais. "
              "Responda APENAS JSON: {\"legenda_sobre_rosto\": true/false, \"faixa_sobre_rosto\": true/false, "
              "\"problema\": \"frase curta ou vazio\"}")
    return ia_json(prompt, cwd=pasta, imagens=[img], timeout=180, tarefa="revisao") or {}


def _cortar_trecho(video: Path, pasta: Path, a, b, nome):
    import efeitos
    dur = duracao_video(video)
    tirar = ([(0, a)] if a > 0.05 else []) + ([(b, dur + 1)] if b < dur - 0.05 else [])
    return efeitos.cortar_intervalos(video, pasta, tirar, nome) if tirar else video


def _palavras_entre(palavras, textos, a, b):
    ps, ts = [], []
    for p, t in zip(palavras, textos):
        if p["ini"] >= a - 0.05 and p["fim"] <= b + 0.1:
            ps.append(dict(p, ini=round(max(0, p["ini"] - a), 2), fim=round(min(b, p["fim"]) - a, 2)))
            ts.append(t)
    return ps, ts


def _analise_entre(analise, a, b):
    if not analise:
        return None
    return dict(analise, amostras=[(t - a, r) for t, r in analise["amostras"] if a <= t <= b],
                cortes_cena=[t-a for t in analise.get("cortes_cena", []) if a <= t <= b])


class RevisaoNecessaria(RuntimeError):
    pass


def _fazer_longos(fonte_video, momentos, kwargs, dados_prontos=None):
    """Corte(s) longo(s) 16:9 do(s) mesmo(s) momento(s). Falha no longo nunca derruba o curto."""
    import longo
    try:
        return longo.gerar_longos(fonte_video, momentos, kwargs.get("pasta_saida") or PASTA_SAIDA,
                                  meta=kwargs.get("meta"), dados_prontos=dados_prontos,
                                  legenda=kwargs.get("legenda", True))
    except Exception as e:
        print(f"   ⚠ não consegui fazer o corte longo: {str(e)[:200]}")
        return []


def gerar_corte(*args, formato="curto", **kwargs):
    """formato: "curto" (9:16, o de sempre), "longo" (16:9, 3–8 min, pro YouTube normal) ou "ambos"."""
    callback = kwargs.pop('_progresso', None)
    job = kwargs.pop('_job_id', None)
    token_job = _job_atual.set(job)
    token = _callback_progresso.set(callback)
    marcas = [(time.time(), "Aguardando o renderizador")]
    token_cron = _cronometro.set(marcas)
    try:
        log('Aguardando o renderizador...')
        with contexto_render():
            checar_ffmpeg()
            if job:
                from conclusao_tarefas import recuperar
                pronto,saida = recuperar(job)
                if pronto:
                    log('Saída já confirmada; retomando sem duplicar o corte.')
                    return saida
            from recursos import verificar_disco
            verificar_disco(Path(__file__).resolve().parent, float(carregar_config().get("min_disco_gb", 2)))
            fonte_video, inicio, fim = (list(args) + [kwargs.get(k) for k in ("fonte_video", "inicio", "fim")][len(args):])[:3]
            if formato == "longo":
                if kwargs.get("perfil"):
                    aplicar_config(carregar_config(kwargs["perfil"]))
                feitos = _fazer_longos(fonte_video, [{"inicio": parse_tempo(inicio), "fim": parse_tempo(fim)}], kwargs)
                if not feitos:
                    raise RuntimeError("não consegui fazer o corte longo")
                return feitos[0]
            saida = _gerar_corte(*args, **kwargs)
            if saida:
                try:
                    registrar_tempos(marcas, saida, round(parse_tempo(fim) - parse_tempo(inicio), 1))
                except (TypeError, ValueError):
                    registrar_tempos(marcas, saida)
            if job:
                from conclusao_tarefas import confirmar
                confirmar(job,saida)
            if formato == "ambos" and saida:
                import longo
                _fazer_longos(fonte_video, [{"inicio": parse_tempo(inicio), "fim": parse_tempo(fim), "curto": saida}],
                              kwargs, dados_prontos=[longo.dados_do_curto(saida)])
            return saida
    finally:
        _cronometro.reset(token_cron)
        _job_atual.reset(token_job)
        _callback_progresso.reset(token)


def _gerar_corte(fonte_video, inicio, fim, foto=None, pergunta=None, legenda=True,
                transcrever_audio=True, modo="cortado", topo="auto", contexto="",
                meta=None, usar_claude=True, pasta_saida: Path | None = None,
                transcricao_teste=None, nota_minima=None, perfil=None, automatico=False,
                refinar=False, foco=None):
    """
    refinar/foco (live): o trecho veio LARGO de propósito; a IA (na mesma chamada de sempre) escolhe
    o pedaço exato em volta do lance, que fica em 'foco' segundos do começo.
    topo: "auto" (thumbnail do YouTube se tiver, senão a IA escolhe um frame),
          "thumb", "frame" (IA escolhe), "thumbnail" (IA escolhe o frame e ele ganha
          visual de thumbnail: zoom, cores fortes, emoji) — ignorado se passar foto=.
    legenda: queima a legenda no vídeo. Mesmo sem isso, gera o .srt pra editar à mão.
    nota_minima: se a IA der nota menor que isso, o corte é descartado (devolve None).
    perfil: nome do perfil (visual, @, horários...). None = descobre pelo canal de origem.
    Devolve o caminho do corte (na série, o da parte 1).
    """
    st = _preparar_corte(fonte_video, inicio, fim, foto, pergunta, legenda, transcrever_audio, modo, topo,
                         contexto, meta, usar_claude, pasta_saida, transcricao_teste, nota_minima, perfil,
                         automatico, refinar=refinar, foco=foco)
    return _finalizar_corte(st, _dados_ia(st))


def _preparar_corte(fonte_video, inicio, fim, foto=None, pergunta=None, legenda=True,
                transcrever_audio=True, modo="cortado", topo="auto", contexto="",
                meta=None, usar_claude=True, pasta_saida: Path | None = None,
                transcricao_teste=None, nota_minima=None, perfil=None, automatico=False,
                refinar=False, foco=None):
    """
    topo: "auto" (thumbnail do YouTube se tiver, senão a IA escolhe um frame),
          "thumb", "frame" (IA escolhe), "thumbnail" (IA escolhe o frame e ele ganha
          visual de thumbnail: zoom, cores fortes, emoji) — ignorado se passar foto=.
    legenda: queima a legenda no vídeo. Mesmo sem isso, gera o .srt pra editar à mão.
    nota_minima: se a IA der nota menor que isso, o corte é descartado (devolve None).
    Efeitos (rosto, silêncios, zoom+boom, marca d'água, layout, revisor, série...) seguem o
    config.json / aba Visual.
    perfil: nome do perfil (visual, @, horários...). None = descobre pelo canal de origem.
    Devolve o caminho do corte (na série, o da parte 1).
    """
    import efeitos
    checar_ffmpeg()
    if perfil:
        aplicar_config(carregar_config(perfil))
    inicio, fim = parse_tempo(inicio), parse_tempo(fim)
    if not (math.isfinite(inicio) and math.isfinite(fim)) or inicio < 0 or fim <= inicio:
        raise ValueError("Início e fim devem ser finitos, com início não negativo e fim após o início.")
    saida_dir = pasta_saida or PASTA_SAIDA
    saida_dir.mkdir(parents=True, exist_ok=True)
    raiz_trabalho = saida_dir / "_trabalho"
    raiz_trabalho.mkdir(parents=True, exist_ok=True)
    pasta = Path(tempfile.mkdtemp(prefix="tarefa_", dir=raiz_trabalho))

    if re.match(r"^https?://", str(fonte_video)):
        video, metadados = baixar_trecho(fonte_video, inicio, fim, pasta)
        meta = {**(meta or {}), **metadados}
    else:
        if not Path(fonte_video).exists():
            raise FileNotFoundError(fonte_video)
        video, meta = recortar_local(fonte_video, inicio, fim, pasta, meta)

    if not perfil:                       # descobre o perfil pelo canal de origem
        perfil = perfil_do_canal(meta.get("canal"), saida_dir.name)
        aplicar_config(carregar_config(perfil))
        if perfil != "Padrão":
            print(f"   usando o perfil: {perfil}")
    if nota_minima is None:
        # robô trabalhando sozinho: sem nota mínima própria, usa a régua do automático (padrão 6)
        nota_minima = NOTA_MINIMA or (NOTA_MINIMA_AUTO if automatico else 0)

    import separar_voz
    if carregar_config().get("tirar_musica_fonte") and tem_audio(video):
        video = separar_voz.tirar_musica(video, pasta, log) or video   # música com direito autoral fora
    limpo = separar_voz.limpar_voz(video, pasta, log)                  # 🎙 ruído fora (a transcrição agradece)
    _voz_limpa.set(bool(limpo))
    video = limpo or video
    dur_orig = duracao_video(video)
    manter_unificado = [(0.0, dur_orig)]
    precisa_corte_unificado = False

    if TIRAR_SILENCIOS and tem_audio(video):
        log("Analisando pausas longas...")
        manter_sil, _, removido = efeitos.intervalos_sem_silencio(video, dur=dur_orig)
        if removido >= 1.0:
            manter_unificado = manter_sil
            precisa_corte_unificado = True
            print(f"   {removido:.1f}s de silêncio marcados para corte único.")
            if foco is not None:          # live: o lance vai pra linha do tempo já sem os silêncios
                foco = efeitos.tempo_sem_silencio(foco, manter_sil)

    palavras = []
    if transcricao_teste is not None:
        palavras = [dict(p) for p in transcricao_teste]
    elif transcrever_audio:
        try:
            wav_pronto = None
            if precisa_corte_unificado and tem_audio(video):
                bruto = extrair_audio(video, pasta / "audio_bruto.wav")
                wav_pronto = efeitos.recortar_wav_mantidos(bruto, pasta / "audio.wav", manter_unificado)
            import ia_cortes
            ia_cortes.aquecer_local()          # IA local: carrega o modelo enquanto transcreve
            palavras = transcrever(video, pasta, dica=dica_transcricao(meta), wav_pronto=wav_pronto)
        except ImportError:
            print("   ⚠ faster-whisper não instalado — seguindo sem transcrição.")

    if _supercut.get() and palavras:     # supercut: onde cada lance começa viaja junto das palavras
        import supercut
        supercut.marcar_palavras(palavras, [efeitos.tempo_sem_silencio(t, manter_unificado)
                                            for t in _supercut.get()["marcas"]])
    # live: marca a palavra do lance (o chat reagiu ali) — a marca acompanha os cortes de vícios
    if refinar and foco is not None and palavras:
        min(palavras, key=lambda p: abs(p["ini"] - foco))["foco"] = True
    if TIRAR_VICIOS and palavras:
        palavras, _, rem_vicios, removido = efeitos.intervalos_sem_vicios(palavras)
        if rem_vicios:
            manter_unificado = efeitos.aplicar_remocao_em_mantidos(manter_unificado, rem_vicios)
            precisa_corte_unificado = True
            print(f"   {removido:.1f}s de \"é…/tipo/né\" marcados para corte único.")

    # ---- revisor (sem IA): não começar nem terminar no meio da frase ----
    if REVISOR and palavras:
        dur = sum(b - a for a, b in manter_unificado)
        ci, cf = efeitos.ajustar_frase(palavras, [p["t"] for p in palavras], dur)
        if ci or cf:
            log(f"Revisor: ajustando pra frase completa (-{ci:.1f}s no começo, -{cf:.1f}s no fim)...")
            rem_frase = ([(0.0, ci)] if ci > 0.05 else []) + ([(dur - cf, dur + 1.0)] if cf > 0.05 else [])
            manter_unificado = efeitos.aplicar_remocao_em_mantidos(manter_unificado, rem_frase)
            palavras, _ = _palavras_entre(palavras, [p["t"] for p in palavras], ci, dur - cf)
            precisa_corte_unificado = True

    if precisa_corte_unificado:
        log("Recortando vídeo em passada única (alta nitidez, zero re-encode intermediário)...")
        video = efeitos.cortar_intervalos_mantidos(video, pasta, manter_unificado, "editado_unico.mp4")

    # ---- rostos: UMA análise serve pro layout, pra câmera e pro revisor ----
    analise = None
    if modo == "cortado" and (SEGUIR_ROSTO or LAYOUT != "normal" or REVISOR):
        log("Olhando os rostos do vídeo...")
        analise = efeitos.analisar_rostos(video, passo=1.0 if MODO_PC_FRACO else 0.5)
    tipo, caixas = "normal", None
    if analise and LAYOUT in ("auto", "podcast", "jogo"):
        tipo, caixas = efeitos.detectar_layout(analise)
        if LAYOUT != "auto" and tipo != LAYOUT:
            print(f"   ⚠ não achei um layout de {LAYOUT} neste vídeo — usando o normal.")
            tipo, caixas = "normal", None
        if tipo == "podcast":
            print("   🎙 2 pessoas lado a lado → modo podcast (tela dividida).")
        elif tipo == "jogo":
            print("   🎮 câmera no canto → modo jogo + facecam.")
    usa_layout = tipo in ("podcast", "jogo")

    # ---- foto do topo (não precisa nos layouts: o topo vira vídeo) ----
    foto_path = Path(foto) if foto else None
    frames = None
    eh_thumbnail = False
    if not usa_layout and not CLEAN:          # clean não tem foto no topo (nem mosaico pra IA)
        if not foto_path and topo in ("auto", "thumb") and meta.get("thumbnail"):
            foto_path = baixar_imagem(meta["thumbnail"], pasta / "thumb.img")
            eh_thumbnail = bool(foto_path)
        if not foto_path:
            frames = extrair_frames(video, pasta)

    dur_total = duracao_video(video)
    pedir_serie = bool(SERIE and palavras and dur_total >= SERIE_MIN and not refinar)
    return {k: v for k, v in locals().items() if k != "efeitos"}


def _cache_ia_arquivo():
    if not _job_atual.get():
        return None
    import conclusao_tarefas
    return conclusao_tarefas.BASE / f"{conclusao_tarefas.identificador(_job_atual.get())}_ia.json"


def _cache_ia_ler(n_palavras):
    arq = _cache_ia_arquivo()
    if arq and arq.exists():
        try:
            guardado = json.loads(arq.read_text(encoding="utf-8"))
            if guardado.get("n_palavras") == n_palavras:
                return guardado["dados"]
        except (OSError, ValueError, KeyError):
            pass
    return None


def _cache_ia_salvar(n_palavras, dados):
    arq = _cache_ia_arquivo()
    if arq and isinstance(dados, dict) and dados.get("pergunta"):
        try:
            salvar_json(arq, {"n_palavras": n_palavras, "dados": dados})
        except (OSError, ValueError, TypeError):
            pass


def _pedido_de(st):
    return dict(palavras=st["palavras"], frames=st["frames"], pergunta=st["pergunta"],
                contexto=st["contexto"], pedir_serie=st["pedir_serie"],
                pedir_emoji=(st["topo"] == "thumbnail" and not st["foto"] and not st["usa_layout"]),
                pedir_trecho=bool(st.get("refinar")))


def gerar_cortes_lote(fonte_video, momentos, _job_ids=None, _progresso=None, formato="curto", **opcoes):
    """Vários cortes do MESMO vídeo com UMA chamada de IA pra todos (em vez de uma por corte).
    momentos = [{'inicio', 'fim', 'contexto'?}]. Devolve a lista de saídas (None = descartado/falhou).
    Se a resposta em lote falhar, cada corte pede a IA separado (nunca fica sem corte)."""
    job_ids = list(_job_ids or [None] * len(momentos))
    token_cb = _callback_progresso.set(_progresso)
    saidas = [None] * len(momentos)
    erros, revisoes = [], []
    try:
        log('Aguardando o renderizador...')
        with contexto_render():
            checar_ffmpeg()
            from recursos import verificar_disco
            verificar_disco(Path(__file__).resolve().parent, float(carregar_config().get("min_disco_gb", 2)))
            if formato == "longo":                  # só longos: 1 chamada de IA pra todos os títulos
                if opcoes.get("perfil"):
                    aplicar_config(carregar_config(opcoes["perfil"]))
                return _fazer_longos(fonte_video, [dict(m) for m in momentos], opcoes) or [None] * len(momentos)
            from conclusao_tarefas import recuperar, confirmar
            preparados = []
            for i, m in enumerate(momentos):
                token = _job_atual.set(job_ids[i])
                try:
                    if job_ids[i]:
                        pronto, saida = recuperar(job_ids[i])
                        if pronto:
                            log(f'Corte {i + 1}: já estava pronto; não refaço.')
                            saidas[i] = saida
                            continue
                    print(f"\n===== Preparando o corte {i + 1} de {len(momentos)} =====")
                    op = dict(opcoes)
                    if m.get("contexto"):
                        op["contexto"] = (m["contexto"] + " " + op.get("contexto", "")).strip()
                    st = _preparar_corte(fonte_video, m["inicio"], m["fim"], op.get("foto"), op.get("pergunta"),
                                         op.get("legenda", True), op.get("transcrever_audio", True),
                                         op.get("modo", "cortado"), op.get("topo", "auto"), op.get("contexto", ""),
                                         m.get("meta") or op.get("meta"), op.get("usar_claude", True),
                                         op.get("pasta_saida"), op.get("transcricao_teste"),
                                         op.get("nota_minima"), op.get("perfil"), op.get("automatico", False))
                    preparados.append((i, st))
                except Exception as e:
                    print(f"   ❌ corte {i + 1} falhou na preparação: {str(e)[:200]}")
                    erros.append(e)
                finally:
                    _job_atual.reset(token)

            # ---- IA: o que já estava guardado + UMA chamada pros que faltam ----
            dados = {}
            faltam = []
            for i, st in preparados:
                token = _job_atual.set(job_ids[i])
                try:
                    if not st["usar_claude"]:
                        dados[i] = _dados_ia(st)
                        continue
                    guardado = _cache_ia_ler(len(st["palavras"]))
                    if guardado is not None:
                        log(f"Corte {i + 1}: reaproveitando a resposta da IA (sem gastar de novo).")
                        dados[i] = guardado
                    else:
                        faltam.append((i, st))
                finally:
                    _job_atual.reset(token)
            if len(faltam) >= 2:
                st0 = faltam[0][1]
                lote = pensar_lote([_pedido_de(st) for _, st in faltam], st0["meta"], st0["pasta"])
                if lote:
                    for (i, st), d in zip(faltam, lote):
                        if d is None:               # não veio inteiro na resposta: pede separado
                            continue
                        token = _job_atual.set(job_ids[i])
                        try:
                            _cache_ia_salvar(len(st["palavras"]), d)
                        finally:
                            _job_atual.reset(token)
                        dados[i] = d
            for i, st in faltam:                     # sobrou (1 corte só, ou o lote falhou)
                if i not in dados:
                    token = _job_atual.set(job_ids[i])
                    try:
                        dados[i] = _dados_ia(st)
                    finally:
                        _job_atual.reset(token)

            # ---- montar cada corte ----
            for i, st in preparados:
                token = _job_atual.set(job_ids[i])
                try:
                    print(f"\n===== Montando o corte {i + 1} de {len(momentos)} =====")
                    saidas[i] = _finalizar_corte(st, dados[i])
                    if job_ids[i]:
                        confirmar(job_ids[i], saidas[i])
                except RevisaoNecessaria as e:
                    revisoes.append(e)
                except Exception as e:
                    print(f"   ❌ corte {i + 1} falhou: {str(e)[:300]}")
                    erros.append(e)
                finally:
                    _job_atual.reset(token)
            if formato == "ambos":                     # longos dos mesmos momentos, títulos do curto (0 IA)
                import longo
                feitos = [(m, s) for m, s in zip(momentos, saidas) if s]
                if feitos:
                    _fazer_longos(fonte_video, [dict(m, curto=s) for m, s in feitos], opcoes,
                                  dados_prontos=[longo.dados_do_curto(s) for _, s in feitos])
    finally:
        _callback_progresso.reset(token_cb)
    if erros and not any(saidas):
        raise erros[0]
    if erros:
        raise RuntimeError(f"{len(erros)} de {len(momentos)} cortes falharam (os outros ficaram prontos): "
                           f"{str(erros[0])[:200]}")
    if revisoes:
        raise RevisaoNecessaria('; '.join(str(e) for e in revisoes)[:500])
    return saidas


def _dados_ia(st):
    """A chamada de IA de UM corte (com o guardado por tarefa)."""
    usar_claude, palavras, meta, pasta, frames, pergunta, contexto, topo, foto, usa_layout, pedir_serie = (st[k] for k in ['usar_claude', 'palavras', 'meta', 'pasta', 'frames', 'pergunta', 'contexto', 'topo', 'foto', 'usa_layout', 'pedir_serie'])
    if usar_claude:
        # A resposta da IA fica guardada por tarefa: se o corte falhar depois (render, disco...)
        # ou ficar "em revisão" e você aprovar, a nova tentativa NÃO paga a IA de novo.
        dados = _cache_ia_ler(len(palavras))
        if dados is not None:
            log("Reaproveitando a resposta da IA desta tarefa (sem gastar de novo).")
        else:
            dados = pensar_com_ia(palavras, meta, pasta, frames, pergunta, contexto,
                                  pedir_emoji=(topo == "thumbnail" and not foto and not usa_layout),
                                  pedir_serie=pedir_serie, pedir_trecho=bool(st.get("refinar")))
            _cache_ia_salvar(len(palavras), dados)
    else:
        import otimizador_corte
        sugestao = otimizador_corte.gerar_pergunta_local(palavras, meta) if not pergunta else {"pergunta": pergunta, "destaque": []}
        dados = {"palavras": [p["t"] for p in palavras], "pergunta": pergunta or sugestao["pergunta"],
                 "destaque": sugestao.get("destaque", []), "titulo": meta.get("titulo", ""), "hashtags": [], "foto": None,
                 "emoji": "😱", "nota": None, "gancho": otimizador_corte.achar_gancho_multimodal(palavras)}

    return dados


def _finalizar_corte(st, dados):
    """Da resposta da IA até o .mp4 (faixa, legenda, série, render, ficha)."""
    (nota_minima, pasta, palavras, meta, automatico, usa_layout, foto_path, frames, topo, legenda, pedir_serie, video, analise, dur_total, tipo, caixas, saida_dir, eh_thumbnail, modo, foto, pergunta, fonte_video, inicio, fim) = (st[k] for k in ['nota_minima', 'pasta', 'palavras', 'meta', 'automatico', 'usa_layout', 'foto_path', 'frames', 'topo', 'legenda', 'pedir_serie', 'video', 'analise', 'dur_total', 'tipo', 'caixas', 'saida_dir', 'eh_thumbnail', 'modo', 'foto', 'pergunta', 'fonte_video', 'inicio', 'fim'])
    nota = dados.get("nota")
    try:
        nota = float(nota) if nota is not None else None
        nota = max(0, min(10, nota)) if nota is not None and math.isfinite(nota) else None
    except (TypeError, ValueError):
        nota = None
    if nota is not None:
        print(f"   Nota de viralidade: {nota:g}/10")
        if nota_minima and nota < nota_minima:
            log(f"Descartado: nota {nota:g} menor que a mínima ({nota_minima:g}).")
            shutil.rmtree(pasta, ignore_errors=True)
            return None

    from inteligencia_editorial import avaliar
    avaliacao_editorial=avaliar(' '.join(p['t'] for p in palavras),dados.get('avaliacao_editorial'))
    meta['avaliacao_editorial']=avaliacao_editorial
    limiar = float(carregar_config(PERFIL_EM_USO).get('autonomia_confianca', 0))
    if automatico and limiar:
        from calibracao import decidir
        decisao=decidir(avaliacao_editorial,palavras,PERFIL_EM_USO,limiar)
        meta['decisao_autonomia']=decisao
        if not decisao['automatico']:
            raise RevisaoNecessaria('; '.join(decisao['motivos']))

    parecidos = None
    if CHECAR_INEDITO and dados.get("titulo"):
        parecidos = contar_parecidos(dados["titulo"], meta.get("canal", ""))
        if parecidos:
            print(f"   ⚠ já existem {parecidos} corte(s) parecido(s) no YouTube esta semana.")
        elif parecidos == 0:
            print("   ✓ parece inédito no YouTube.")

    if not usa_layout and not foto_path and frames:
        try:
            idx = int(dados.get("foto") or 0)
        except (TypeError, ValueError):
            idx = 0
        if 1 <= idx <= len(frames):
            foto_path = frames[idx - 1]
        else:
            import otimizador_corte
            foto_path = otimizador_corte.escolher_melhor_quadro(frames) or frames[len(frames) // 3]
        if topo == "thumbnail":
            foto_path = estilo_thumbnail(foto_path, dados.get("emoji") or "😱", pasta)

    textos = list(dados["palavras"])
    if len(textos) != len(palavras):
        textos = [p["t"] for p in palavras]
    if palavras and (dados.get("_ia") or {}).get("provedor"):
        try:                                # nomes corrigidos pela IA entram no glossário do canal
            import ia_aprende
            novos = ia_aprende.aprender_correcoes(meta.get("canal"), [p["t"] for p in palavras], textos, "ia")
            if novos:
                print(f"   glossário do canal: {', '.join(novos[:6])}")
        except Exception:
            pass

    # marca nas palavras o gancho e os emojis (assim eles acompanham qualquer corte/deslocamento)
    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    gi = _int(dados.get("gancho"))
    if gi is None and palavras and (EFEITO_GANCHO or GANCHO_INICIO):
        import otimizador_corte
        gi = otimizador_corte.achar_gancho_multimodal(palavras, textos)
    if gi is not None and 0 <= gi < len(palavras):
        palavras[gi]["gancho"] = True
    if EMOJIS_LEGENDA and legenda:
        for par in (dados.get("emojis") or [])[:3]:
            if isinstance(par, (list, tuple)) and len(par) == 2:
                k = _int(par[0])
                if k is not None and 0 <= k < len(palavras) and isinstance(par[1], str) and par[1].strip():
                    palavras[k]["emoji"] = par[1].strip()[:4]
    for k in (dados.get("enfase") or [])[:8]:             # palavras-chave coloridas (template)
        if 0 <= k < len(palavras):
            palavras[k]["enfase"] = True

    ks_marca = _int(dados.get("corte_serie")) if pedir_serie else None
    if ks_marca is not None and 0 < ks_marca < len(palavras):
        palavras[ks_marca]["serie"] = True
    ap_ia = dados.get("aparar")                            # [1ª, última] sugerido pela IA (lista inteira)
    if ap_ia and 0 <= ap_ia[0] < ap_ia[1] < len(palavras):
        palavras[ap_ia[0]]["ap_ini"] = True
        palavras[ap_ia[1]]["ap_fim"] = True
    ab_ia = dados.get("abertura") or 0                     # índice sugerido pela IA (lista inteira)
    if 0 < ab_ia < len(palavras):
        palavras[ab_ia]["abertura"] = True

    # ---- live: recorta o pedaço exato em volta do lance (IA na mesma chamada; sem IA, pelas pausas) ----
    if st.get("refinar") and palavras:
        import efeitos
        par = dados.get("trecho")
        i0 = i1 = None
        if isinstance(par, (list, tuple)) and len(par) == 2:
            i0, i1 = _int(par[0]), _int(par[1])
        if i0 is None or i1 is None or not (0 <= i0 < i1 < len(palavras)):
            foco_t = next((p["ini"] for p in palavras if p.get("foco")), None)
            achado = efeitos.momento_do_trecho(palavras, foco_t, float(carregar_config().get("duracao_corte_seg", 65)))
            i0, i1 = achado if achado else (None, None)
            origem = "pelas pausas"
        else:
            origem = "escolhido pela IA"
        if i0 is not None:
            t0 = palavras[i0]["ini"] - 0.25
            if i0 > 0:
                t0 = max(t0, (palavras[i0 - 1]["fim"] + palavras[i0]["ini"]) / 2)
            t1 = palavras[i1]["fim"] + 0.45
            if i1 + 1 < len(palavras):
                t1 = min(t1, (palavras[i1]["fim"] + palavras[i1 + 1]["ini"]) / 2)
            t0, t1 = max(0.0, t0), min(dur_total, t1)
            if t1 - t0 >= 15 and (t0 > 0.5 or t1 < dur_total - 0.5):
                log(f"Momento exato da live ({origem}): {t0:.1f}s → {t1:.1f}s de {dur_total:.0f}s.")
                video = _cortar_trecho(video, pasta, t0, t1, "momento.mp4")
                palavras, textos = _palavras_entre(palavras, textos, t0, t1)
                analise = _analise_entre(analise, t0, t1)
                dur_total = t1 - t0

    # ---- IA apara as pontas fracas (começo que não prende / fim que sobra) ----
    if APARAR_IA and palavras and not st.get("refinar") and not _supercut.get():
        import acabamento
        i_a = next((i for i, p in enumerate(palavras) if p.get("ap_ini")), None)
        i_b = next((i for i, p in enumerate(palavras) if p.get("ap_fim")), None)
        par = acabamento.aparar_pela_ia(palavras, (i_a, i_b), dur_total) if i_a is not None and i_b is not None \
            else None
        if par:
            t0, t1 = par
            log(f"IA aparou o trecho: {t0:.1f}s → {t1:.1f}s de {dur_total:.0f}s "
                f"(-{t0:.1f}s no começo, -{dur_total - t1:.1f}s no fim).")
            video = _cortar_trecho(video, pasta, t0, t1, "aparado.mp4")
            palavras, textos = _palavras_entre(palavras, textos, t0, t1)
            analise = _analise_entre(analise, t0, t1)
            dur_total = t1 - t0
        elif ap_ia:
            inteiro = ap_ia[0] <= 0 and ap_ia[1] >= len(palavras) - 2
            if inteiro:
                print("   IA manteve o trecho inteiro (começo e fim já servem).")
            else:
                ini_s = palavras[i_a]["ini"] if i_a is not None else 0.0
                fim_s = dur_total - palavras[i_b]["fim"] if i_b is not None else 0.0
                print(f"   a IA queria tirar {ini_s:.0f}s do começo e {max(0.0, fim_s):.0f}s do fim — passa do "
                      "limite de segurança (ou cortaria o gancho); trecho mantido.")

    # ---- abertura limpa: os 3 primeiros segundos não podem ser enrolação ----
    if LIMPAR_ABERTURA and palavras and not st.get("refinar"):
        import acabamento
        i_ab = acabamento.abertura_limpa(palavras, textos,
                                         next((i for i, p in enumerate(palavras) if p.get("abertura")), None))
        if i_ab:
            t0 = max(0.0, palavras[i_ab]["ini"] - 0.18)
            t0 = max(t0, (palavras[i_ab - 1]["fim"] + palavras[i_ab]["ini"]) / 2)
            if t0 >= 0.4:
                pulou = " ".join(textos[:i_ab])[:60]
                log(f"Abertura limpa: começando {t0:.1f}s depois (pulou \"{pulou}\").")
                video = _cortar_trecho(video, pasta, t0, dur_total, "abertura.mp4")
                palavras, textos = _palavras_entre(palavras, textos, t0, dur_total)
                analise = _analise_entre(analise, t0, dur_total)
                dur_total -= t0

    # ---- corte em série (parte 1 termina no suspense) ----
    partes = [(video, palavras, textos, analise, None)]
    ks = next((i for i, p in enumerate(palavras) if p.get("serie")), None)         if pedir_serie and not _supercut.get() else None
    if ks is not None and 0 < ks < len(palavras):
        s_t = palavras[ks]["ini"]
        fim1 = min(s_t, palavras[ks - 1]["fim"] + 0.25)
        ini2 = max(0.0, s_t - 2.5)                       # parte 2 começa relembrando o fim da 1
        if fim1 >= 25 and dur_total - ini2 >= 25:
            log(f"Corte em série: parte 1 até {fim1:.1f}s, parte 2 de {ini2:.1f}s.")
            v1 = _cortar_trecho(video, pasta, 0, fim1, "parte1.mp4")
            v2 = _cortar_trecho(video, pasta, ini2, dur_total, "parte2.mp4")
            p1, t1 = _palavras_entre(palavras, textos, 0, fim1)
            p2, t2 = _palavras_entre(palavras, textos, ini2, dur_total)
            partes = [(v1, p1, t1, _analise_entre(analise, 0, fim1), 1),
                      (v2, p2, t2, _analise_entre(analise, ini2, dur_total), 2)]

    nome = nome_seguro(dados.get("titulo") or meta.get("titulo", ""))
    serie_id = nome if len(partes) > 1 else None
    resultado = None
    for v, ps, ts, an, parte in partes:
        saida = _montar_corte(v, ps, ts, an, tipo, caixas, parte, dados, meta, pasta, saida_dir, nome,
                              foto_path, eh_thumbnail, modo, legenda, topo, foto, pergunta, nota,
                              parecidos, fonte_video, inicio, fim, serie_id)
        resultado = resultado or saida
    shutil.rmtree(pasta, ignore_errors=True)
    log(f"PRONTO: {resultado.resolve()}")
    return resultado


def gancho_repete_inicio(palavras, textos, a, b, janela=6.0, limite=0.6):
    """True se as palavras da prévia [a, b] já aparecem quase todas nos primeiros segundos
    (a prévia viraria só uma repetição do começo, sem curiosidade nova)."""
    import unicodedata

    def norm(t):
        t = unicodedata.normalize("NFD", str(t).lower())
        return "".join(c for c in t if c.isalnum())

    def conjunto(cond):
        return {w for i, p in enumerate(palavras) if cond(p)
                for w in [norm(textos[i] if i < len(textos) else p.get("t", ""))] if len(w) >= 3}
    previa = conjunto(lambda p: p["ini"] >= a and p["fim"] <= b + 0.05)
    if not previa:
        return True                                   # prévia sem fala nenhuma não prende ninguém
    comeco = conjunto(lambda p: p["ini"] < janela and not (a <= p["ini"] <= b))
    return len(previa & comeco) / len(previa) >= limite


def _montar_corte(video, palavras, textos, analise, tipo, caixas, parte, dados, meta, pasta, saida_dir,
                  nome, foto_path, eh_thumbnail, modo, legenda, topo, foto, pergunta, nota, parecidos,
                  fonte_video, inicio, fim, serie_id):
    """Da edição pronta (vídeo + palavras) até o .mp4 final (+ versão B e espanhol)."""
    import efeitos
    usa_layout = tipo in ("podcast", "jogo")
    alt_topo = ALTURA_FOTO + ALTURA_FAIXA
    sufixo = f"_parte{parte}" if parte else ""
    if parte:
        log(f"Montando a PARTE {parte}...")
    import acabamento
    if FINAL_CORTE == "loop" and not parte and palavras:
        fim_l = acabamento.fim_para_loop(palavras, duracao_video(video))
        if fim_l:
            print(f"   final em loop: termina colado na última fala ({fim_l:.1f}s) pra emendar no replay.")
            video = _cortar_trecho(video, pasta, 0, fim_l, "loop.mp4")
            analise = _analise_entre(analise, 0, fim_l)

    gancho_t = next((p["ini"] for p in palavras if p.get("gancho")), None)
    boom = None
    t_virada = None                               # onde a prévia do gancho termina e o vídeo começa
    # prévia do gancho no primeiro segundo (não na série: cada parte já começa no ponto certo)
    prefixar = GANCHO_INICIO and not parte and gancho_t is not None and duracao_video(video) - gancho_t > 2         and not _supercut.get()                  # supercut: a contagem já é o gancho
    if prefixar and gancho_t < GANCHO_DISTANCIA_MIN:
        print(f"   gancho já está perto do começo ({gancho_t:.1f}s) — sem prévia repetida.")
        prefixar = False
    if prefixar:
        a, b = efeitos.janela_gancho(palavras, gancho_t)
        if gancho_repete_inicio(palavras, textos, a, b):
            print("   o momento mais forte repete o que já aparece no começo — sem prévia.")
            prefixar = False
    previa_gancho = None
    if prefixar:
        log(f"Colocando o momento mais forte no começo ({a:.1f}s → {b:.1f}s), direto na montagem...")
        previa_gancho = (a, b)                     # o render emenda a prévia (zero re-encode a mais)
        d = b - a
        previa = [(dict(p, ini=round(p["ini"] - a, 2), fim=round(min(p["fim"], b) - a, 2), emoji=None,
                        gancho=False), textos[i])
                  for i, p in enumerate(palavras) if p["ini"] >= a and p["fim"] <= b + 0.05]
        resto = [(dict(p, ini=round(p["ini"] + d, 2), fim=round(p["fim"] + d, 2)), textos[i])
                 for i, p in enumerate(palavras)]
        if resto:
            resto[0][0]["quebra"] = True
        palavras = [p for p, _ in previa + resto]
        textos = [t for _, t in previa + resto]
        gancho_t += d
        t_virada = d
        if analise:
            analise = dict(analise, amostras=[(t - a, r) for t, r in analise["amostras"] if a <= t <= b]
                           + [(t + d, r) for t, r in analise["amostras"]])
    if EFEITO_GANCHO and gancho_t is not None:
        boom = efeitos.gerar_boom(pasta)
        print(f"   gancho em {gancho_t:.1f}s (zoom + boom)")

    duracao = duracao_video(video) + (previa_gancho[1] - previa_gancho[0] if previa_gancho else 0)
    aviso_musica = None
    if CHECAR_MUSICA and tem_audio(video):        # áudio original do trecho (antes da nossa trilha)
        import audio_musica
        aviso_musica = audio_musica.detectar(video, palavras)
        if aviso_musica and aviso_musica["provavel"]:
            print(f"   ⚠ parece ter MÚSICA DE FUNDO (confiança {aviso_musica['confianca']}): {aviso_musica['motivo']}."
                  " Música com direitos autorais pode mutar ou bloquear o corte no YouTube — confira antes de postar.")
    W, H = (analise["w"], analise["h"]) if analise and analise.get("w") else info_video(video)

    # ---- template de edição (legenda + efeitos). "Automático" usa o tom que a IA já mandou ----
    import templates_edicao as te
    tpl = te.resolver(TEMPLATE_EDICAO, dados.get("tom"), tipo)
    tpl_origem = "fixo" if TEMPLATE_EDICAO != te.AUTOMATICO else "tom"
    if TEMPLATE_EDICAO == te.AUTOMATICO and TEMPLATE_APRENDE:
        try:                                      # prefere o que mais rende no canal (com amostra suficiente)
            import random
            import resultados
            import zlib
            sorteio = random.Random(zlib.crc32(str(nome).encode("utf-8")))   # mesma escolha nas partes da série
            aprendido = te.escolher_aprendido(tpl["nome"], resultados.desempenho_templates(PERFIL_EM_USO), sorteio)
            if aprendido != tpl["nome"]:
                print(f"   aprendizado: '{aprendido}' rende mais no seu canal que '{tpl['nome']}' — usando ele.")
                tpl = te.resolver(aprendido, dados.get("tom"), tipo)
                tpl_origem = "aprendido"
        except Exception as e:
            print(f"   ⚠ aprendizado de template indisponível: {str(e)[:100]}")
    efx = tpl["efeitos"]
    ajuste_exposicao = efeitos.correcao_exposicao(video)
    if ajuste_exposicao:
        print("   vídeo escuro — levantando a exposição de leve.")

    if tipo in ("podcast", "jogo"):              # recortes com zoom no rosto/câmera: sempre esticados
        ampliacao = 2.0
    elif modo == "inteiro":
        ampliacao = LARGURA / max(1, W)
    else:
        ampliacao = max((ALTURA if CLEAN else ALTURA_VIDEO) / max(1, H), LARGURA / max(1, W))

    def estilo_de(t_):
        """Efeitos de vídeo de um template (a versão B do teste A/B pode usar outro)."""
        e_ = t_["efeitos"]
        er_ = {"cor": ajuste_exposicao + te.filtro_cor(e_, H, ampliacao), "voz_limpa": _voz_limpa.get()}
        if e_.get("zoom_lento") and tipo not in ("podcast", "jogo"):
            er_["zoom_lento"] = float(e_["zoom_lento"])
        if e_.get("zoom_ritmo") and tipo not in ("podcast", "jogo"):
            er_["ritmo"] = te.trechos_ritmo(palavras, textos, duracao)
            er_["ritmo_int"] = float(e_["zoom_ritmo"])
        if e_.get("zoom_enfase") and tipo not in ("podcast", "jogo"):
            tempos_e = acabamento.tempos_enfase(palavras, gancho_t, duracao)
            if tempos_e:
                er_["enfase"] = tempos_e
                er_["enfase_int"] = float(e_["zoom_enfase"])
        if e_.get("barra_progresso"):
            er_["barra"] = e_["barra_progresso"]
        if e_.get("flash_gancho"):
            er_["flash"] = [t for t in (t_virada, gancho_t) if t is not None and 0 < t < duracao - 0.3]
        return er_
    estilo_render = estilo_de(tpl)
    if estilo_render.get("enfase"):
        print(f"   zoom em {len(estilo_render['enfase'])} palavra(s)-chave.")
    print(f"   template de edição: {tpl['nome']}" + (f" (tom: {dados.get('tom')})" if dados.get("tom") else ""))
    if MUSICA_FUNDO and MUSICA_VOLUME > 0 and tem_audio(video):
        import musica
        faixa_m = musica.escolher(dados.get("tom"), tipo)
        if faixa_m:
            copia_m = Path(video).parent / ("musica" + faixa_m.suffix.lower())
            shutil.copy2(faixa_m, copia_m)
            estilo_render["musica"] = {"arquivo": str(copia_m), "vol": MUSICA_VOLUME, "nome": faixa_m.name,
                                       "loop": FINAL_CORTE == "loop" and not parte}
            print(f"   música de fundo: {faixa_m.name} (abaixa quando falam)")

    # ---- enquadramento ----
    layout, expr_x, falantes, rostos_px, texto_px = None, None, None, [], None
    if tipo == "podcast":
        top = efeitos.recorte(caixas["A"], W, H, LARGURA / alt_topo, zoom=3.0)
        bot = efeitos.recorte(caixas["B"], W, H, LARGURA / ALTURA_VIDEO, zoom=3.0)
        layout = {"top": top, "bot": bot, "tipo": "podcast"}
        log("Vendo quem está falando...")
        falantes = efeitos.falantes(video, caixas["A"], caixas["B"], palavras=palavras)
        if falantes:
            # quem está calado fica um pouco mais escuro e quem domina a fala ganha foco dinâmico
            layout["escurecer_top"] = [(a, b) for a, b, q in falantes if q == "B"]
            layout["escurecer_bot"] = [(a, b) for a, b, q in falantes if q == "A"]
            layout.update(efeitos.foco_podcast(falantes))
        rostos_px = _rostos_na_tela(analise, top, 0, alt_topo) + _rostos_na_tela(analise, bot, alt_topo,
                                                                                 ALTURA_VIDEO)
    elif tipo == "jogo":
        top = efeitos.recorte(caixas["cam"], W, H, LARGURA / alt_topo, zoom=3.4, sobe=0.05)
        bot = efeitos.recorte_centro(W, H, LARGURA / ALTURA_VIDEO)
        layout = {"top": top, "bot": bot, "tipo": "jogo"}
        rostos_px = _rostos_na_tela(analise, bot, alt_topo, ALTURA_VIDEO)
    elif modo == "cortado":
        alt_v = ALTURA if CLEAN else ALTURA_VIDEO       # clean: o vídeo ocupa a tela toda
        k = max(alt_v / H, LARGURA / W)
        largura = int(round(W * k))
        cw, ch = LARGURA / k, alt_v / k
        painel = ((W - cw) / 2, (H - ch) / 2)
        if SEGUIR_ROSTO:
            traj = efeitos.trajetoria_de(analise) if analise else efeitos.trajetoria_rosto(video)
            if traj:
                expr_x = efeitos.expr_crop_x(traj, largura)
                print("   rosto encontrado — a câmera vai acompanhar.")
                painel = (0, painel[1])              # a câmera anda: considera a largura toda
                cw = W
            else:
                print("   sem rosto claro — usando o centro.")
        rostos_px = _rostos_na_tela(analise, (cw, ch, painel[0], painel[1]), 0 if CLEAN else alt_topo, alt_v)
        faixa_txt = efeitos.faixa_texto_fixa(analise)     # legenda que já vem gravada (jogo, vídeo legendado)
        if faixa_txt:
            y0_v, k_v = (0 if CLEAN else alt_topo), alt_v / ch
            texto_px = tuple(y0_v + (f * H - painel[1]) * k_v for f in faixa_txt)

    # ---- faixa / topo ----
    if CLEAN:
        img_topo, img_faixa, y_faixa = None, None, 0
        print("   estilo clean: sem faixa, vídeo em tela cheia" if not usa_layout else "   estilo clean: sem faixa")
    else:
        img_topo, img_faixa, y_faixa = montar_topo(foto_path, dados["pergunta"], dados.get("destaque"),
                                                   meta.get("canal", ""), pasta, inteira=eh_thumbnail,
                                                   so_faixa=usa_layout)
    y_base_faixa = y_faixa
    # a posição da legenda é a que a pessoa escolheu no Visual (a zona segura do app só aparece
    # na prévia, como guia; ela não empurra mais a legenda pra cima)
    margem = MARGEM_LEGENDA
    zona = acabamento.zona_segura(PLATAFORMA_ALVO)   # onde os botões/legenda do app cobrem o vídeo

    def ganchos(pergunta_txt, destaque):
        """Estilo clean: a pergunta vira texto na tela nos primeiros segundos."""
        if not (CLEAN and TEXTO_GANCHO and pergunta_txt):
            return []
        y = None
        if REVISOR and rostos_px and not usa_layout:     # desvia do rosto (sem descer até a legenda)
            y = acabamento.y_gancho_livre(rostos_px, acabamento.altura_gancho(pergunta_txt), 250,
                                          max(60, zona["topo"]), ALTURA - margem - TAMANHO_LEGENDA * 1.5 - 40)
            if y is not None:
                print(f"   revisor: pergunta do gancho movida pra não tampar o rosto (topo em {y}px).")
        return [(0.0, 3.6, texto_gancho_ass(pergunta_txt, destaque, y=y), "GanchoMeio" if usa_layout else "Gancho")]
    if REVISOR and rostos_px and img_faixa:
        y_faixa = _faixa_longe_dos_rostos(rostos_px, y_faixa, img_faixa, alt_topo - 520)
        if y_faixa != y_base_faixa:
            print(f"   revisor: faixa subiu {y_base_faixa - y_faixa}px pra não tampar rosto.")
    if REVISOR and rostos_px:
        if legenda and palavras:
            base_m = margem
            margem = efeitos.margem_legenda_segura(rostos_px, base_m, TAMANHO_LEGENDA, ALTURA, minimo=20)
            if margem != base_m:
                print(f"   revisor: legenda movida pra não ficar em cima do rosto (margem {margem}).")
    if REVISOR and texto_px and legenda and palavras:
        base_m = margem
        margem = efeitos.margem_longe_do_texto(texto_px, base_m, TAMANHO_LEGENDA, ALTURA, minimo=20)
        if margem != base_m:
            print(f"   revisor: o vídeo já tem legenda gravada embaixo — a nossa foi pra margem {margem} "
                  "(sem uma tampar a outra).")

    # ---- emojis, selo da parte e aviso de continuação ----
    # onde começa a área livre do vídeo (abaixo da faixa; no clean, abaixo dos botões do topo)
    topo_livre = max(20, zona["topo"]) if CLEAN else alt_topo + 20

    def montar_extras(margem_leg):
        extras, avisos = [], []
        # emoji no canto direito, logo acima da legenda (o rosto costuma ficar no meio)
        y_emoji = acabamento.y_acima_ou_abaixo(ALTURA, margem_leg, TAMANHO_LEGENDA, 150, topo_livre,
                                               zona["baixo"])
        for n, p in enumerate(w for w in palavras if w.get("emoji")):
            png = emoji_png(p["emoji"], pasta / f"emoji_{parte or 0}_{n}.png", tamanho=150)
            if png:
                extras.append({"png": png, "x": LARGURA - 150 - max(70, zona["direita"]) - (n % 2) * 40,
                               "y": y_emoji,
                               "ini": p["ini"], "fim": min(duracao, p["ini"] + 1.3)})
        if parte:
            selo = selo_png(f"PARTE {parte}", pasta / f"selo_{parte}.png",
                            cor=(255, 214, 0) if parte == 1 else (0, 200, 255))
            extras.append({"png": selo, "x": 36, "y": 40, "ini": 0, "fim": duracao + 1, "fade": False})
            if parte == 1:                          # cartaz no fim: "continua na parte 2"
                cont = selo_png("CONTINUA NA PARTE 2", pasta / "continua.png", cor=(225, 20, 30),
                                cor_texto=(255, 255, 255))
                from PIL import Image
                lw = Image.open(cont).width
                extras.append({"png": cont, "x": (LARGURA - lw) // 2, "y": alt_topo + 260,
                               "ini": max(0, duracao - 2.8), "fim": duracao + 1})
                seta = emoji_png("👉", pasta / "seta.png", tamanho=110)
                if seta:
                    extras.append({"png": seta, "x": (LARGURA - 110) // 2, "y": alt_topo + 370,
                                   "ini": max(0, duracao - 2.6), "fim": duracao + 1})
        if parte != 1 and FINAL_CORTE == "cta" and CTA_TEXTO and duracao >= 12:
            from PIL import Image
            cta = selo_png(CTA_TEXTO, pasta / f"cta_{parte or 0}.png")
            lw = Image.open(cta).width
            y_cta = max(60, zona["topo"] + 20) if CLEAN else alt_topo + 40
            leg_topo, leg_base = ALTURA - margem_leg - TAMANHO_LEGENDA * 2.6, ALTURA - margem_leg + 20
            if legenda and palavras and y_cta < leg_base and y_cta + 96 > leg_topo:   # em cima da legenda
                y_cta = int(leg_base + 30) if leg_base + 130 < ALTURA - zona["baixo"] else int(leg_topo - 120)
            ini_cta = max(0, duracao - 2.6)
            extras.append({"png": cta, "x": (LARGURA - lw) // 2, "y": y_cta, "ini": ini_cta, "fim": duracao + 1})
            limpos = []                     # emoji nunca aparece por cima do cartaz final
            for e in extras:
                if Path(e["png"]).name.startswith("emoji_"):
                    if e["ini"] >= ini_cta - 0.3:
                        continue
                    e["fim"] = min(e["fim"], ini_cta)
                limpos.append(e)
            extras[:] = limpos
        return extras, avisos

    extras, avisos = montar_extras(margem)
    avisos = avisos + ganchos(dados["pergunta"], dados.get("destaque"))
    viradas_sc = []
    if _supercut.get():                          # selo #N em cada lance + whoosh e flash na virada
        import supercut
        txt_sc, viradas_sc = supercut.contagem(palavras, _supercut.get()["total"], duracao,
                                               3.6 if CLEAN and TEXTO_GANCHO else 0.0)
        avisos = avisos + txt_sc
    tempos_pop = [e["ini"] for e in extras if Path(e["png"]).name.startswith("emoji_") and e["ini"] > 0.2]

    def com_sons(er_, e_):
        """Junta ao estilo os sons: 'pop' nos emojis (se o template pedir) e a música já escolhida."""
        if e_.get("pop_emojis") and tempos_pop:
            pop = efeitos.gerar_pop(pasta)
            er_["sfx"] = [{"arquivo": str(pop), "t": round(t, 2), "vol": 0.45} for t in tempos_pop[:4]]
        if estilo_render.get("musica"):
            er_["musica"] = estilo_render["musica"]
        if viradas_sc:
            wh = efeitos.gerar_whoosh(pasta, duracao=0.45)
            er_["sfx"] = [{"arquivo": str(wh), "t": round(max(0.0, t - 0.22), 2), "vol": 0.5}
                          for t in viradas_sc] + list(er_.get("sfx") or [])
            er_["flash"] = list(er_.get("flash") or [])[:1] + viradas_sc
        return er_
    com_sons(estilo_render, efx)

    def fazer_ass(margem_leg, extra_txt=None, nome_ass=None, tpl_=None):
        lista = avisos if extra_txt is None else extra_txt
        if (legenda and palavras) or MARCA or lista:
            return gerar_ass(palavras, textos, pasta / (nome_ass or f"legenda{sufixo}.ass"), duracao=duracao,
                             legenda=legenda, falantes=falantes, textos_extra=lista, margem=margem_leg,
                             template=tpl_ or tpl)
        return None

    titulo = dados.get("titulo") or meta.get("titulo", "")
    if parte:
        titulo = re.sub(r"\s*\(parte \d\)\s*$", "", titulo, flags=re.I) + f" (Parte {parte})"
    job = _job_atual.get()
    if job:
        from conclusao_tarefas import identificador
        nome = f"{nome[:60]}_{identificador(job)[:8]}"     # título legível + código fixo da tarefa
    saida = saida_dir / f"{nome}{sufixo}.mp4"
    n = 2
    while saida.exists() and not job:
        saida = saida_dir / f"{nome}{sufixo}_{n}.mp4"
        n += 1

    ass = fazer_ass(margem)
    renderizar(video, img_topo, ass, saida, modo, img_faixa, y_faixa, expr_x, gancho_t, boom,
               layout=layout, extras=extras, estilo_render=estilo_render, previa=previa_gancho)

    # ---- revisão com IA (opcional, 1 imagem; no máximo refaz 1 vez) ----
    revisao = None
    if REVISAO_IA and IA_PRINCIPAL != "local":
        try:
            revisao = _revisar_com_ia(saida, pasta)
        except Exception as e:
            print(f"   ⚠ revisão com IA falhou: {str(e)[:120]}")
        if revisao and (revisao.get("legenda_sobre_rosto") or revisao.get("faixa_sobre_rosto")):
            print(f"   revisor IA: {revisao.get('problema') or 'ajustando posição'} — refazendo uma vez.")
            if revisao.get("faixa_sobre_rosto"):
                y_faixa = max(alt_topo - 520, y_faixa - 140)
            if revisao.get("legenda_sobre_rosto") and legenda:
                margem = max(20, int(margem * 0.5))       # só desce (nunca sobe acima do escolhido)
                extras, avisos = montar_extras(margem)
                avisos = avisos + ganchos(dados["pergunta"], dados.get("destaque"))
                ass = fazer_ass(margem)
            renderizar(video, img_topo, ass, saida, modo, img_faixa, y_faixa, expr_x, gancho_t, boom,
                       layout=layout, extras=extras, estilo_render=estilo_render, previa=previa_gancho)

    if palavras:
        gerar_srt(palavras, textos, saida.with_suffix(".srt"))

    import datetime
    grupo = saida.stem if AB_TESTE and not parte else None
    ficha = {"_job_id": _job_atual.get(), "fonte": str(fonte_video), "inicio": inicio, "fim": fim, "pergunta": dados["pergunta"],
             "titulo": titulo, "hashtags": dados.get("hashtags", []),
             "nota": nota, "canal": meta.get("canal", ""), "titulo_original": meta.get("titulo", ""),
             "opcoes": {"foto": foto, "legenda": legenda, "modo": modo, "topo": topo},
             "perfil": PERFIL_EM_USO, "formato_faixa": FAIXA_FORMATO, "estilo_faixa": cfg_estilo(),
             "duracao": round(duracao, 1), "parecidos": parecidos, "idioma": "pt",
             "layout": tipo, "estilo": "clean" if CLEAN else "faixa", "template": tpl["nome"], "template_origem": tpl_origem,
             "musica": (estilo_render.get("musica") or {}).get("nome"),
             "resumo": dados.get("resumo") or None, "motivo_nota": dados.get("motivo_nota") or None,
             "chamada": dados.get("chamada") or None, "ia": dados.get("_ia") or None,
             "tom": te.normalizar_tom(dados.get("tom")), "perguntas_alternativas": dados.get("alternativas") or [],
             "musica_de_fundo": aviso_musica,
             "revisor": {"margem": margem, "faixa_y": y_faixa,
                                         "ia": revisao.get("problema") if revisao else None},
             "criado": datetime.datetime.now().isoformat(timespec="seconds"), "status": "novo"}
    if serie_id:
        ficha.update(serie=serie_id, parte=parte)
    tem_perg_b = bool(dados.get("pergunta_b")) and not pergunta
    variar = AB_VARIAR
    if variar == "alternar":                      # um corte testa a pergunta, o outro testa o template
        import zlib
        variar = "template" if zlib.crc32(saida.stem.encode("utf-8")) % 2 == 0 else "pergunta"
    if variar in ("pergunta", "ambos") and not tem_perg_b:
        variar = "template"
    tpl_b = te.alternativo(tpl["nome"], dados.get("tom"), tipo) if variar in ("template", "ambos") else tpl
    if grupo:
        hip = carregar_config(PERFIL_EM_USO).get("hipotese_ab", "")
        if variar == "template":                  # hipótese própria: não mistura com a de pergunta
            hip = f"Template {tpl['nome']} x {tpl_b['nome']}"
        ficha.update(grupo_ab=grupo, variante="A", ab_variou=variar, hipotese_ab=hip)
    if GERAR_CAPA:
        try:
            tem_texto = (not CLEAN) or bool(TEXTO_GANCHO and dados.get("pergunta"))
            if CLEAN and tem_texto:
                t_capa = 1.8                              # a pergunta está na tela nos primeiros segundos
            else:
                t_capa = gancho_t + 0.6 if gancho_t is not None else min(1.5, duracao / 2)
            tem_cta = parte != 1 and FINAL_CORTE == "cta" and bool(CTA_TEXTO) and duracao >= 12
            fim_livre = max(0.0, duracao - (3.4 if tem_cta else 1.5))    # nem o cartaz final nem o finzinho
            if t_capa > fim_livre:          # gancho no fim do corte: usa a prévia dele, que passa no começo
                t_capa = t_virada / 2 if t_virada else 1.5
            capa = acabamento.gerar_capa(saida, saida.with_suffix(".capa.jpg"), max(0.0, min(t_capa, fim_livre)),
                                         pergunta=None if tem_texto else dados.get("pergunta"), fonte=fonte)
            if capa:
                ficha["capa"] = capa.name
                print(f"   capa salva: {capa.name}")
        except Exception as e:
            print(f"   ⚠ não consegui gerar a capa: {str(e)[:120]}")
    if carregar_config(PERFIL_EM_USO).get('guardar_projeto_edicao', True):
        from projeto_edicao import guardar
        ficha['projeto_edicao'] = guardar(saida, video, img_topo, img_faixa, extras, boom,
            dict(modo=modo, y_faixa=y_faixa, expr_x=expr_x, gancho_t=gancho_t, layout=layout,
                 falantes=falantes, duracao=duracao, margem=margem, textos_extra=avisos,
                 template=tpl["nome"], estilo_render=estilo_render,
                 foto=str(foto_path) if foto_path and not usa_layout and not CLEAN else None,
                 eh_thumbnail=bool(eh_thumbnail), so_faixa=bool(usa_layout), clean=bool(CLEAN),
                 canal=meta.get("canal", ""), y_base_faixa=y_base_faixa, legenda=bool(legenda),
                 previa=list(previa_gancho) if previa_gancho else None,   # sem ela a revisão sai fora de sincronia
                 config_visual={k:_cfg_em_uso.get(k) for k in CHAVES_PERFIL}))
    ficha['sincronia'] = meta.get('sincronia')
    ficha['palavras_revisar'] = sum(p.get('confianca', 1) < 0.6 for p in palavras)
    ficha['correcoes_ia'] = {p['t']: textos[i] for i, p in enumerate(palavras)
                             if i < len(textos) and p.get('t') and textos[i] and p['t'].lower() != textos[i].lower()}
    import otimizador_corte
    ficha['retencao_local'] = otimizador_corte.analisar_ritmo_retencao(palavras, duracao)
    ficha['editorial'] = dict(meta.get('editorial', {}), avaliacao=meta.get('avaliacao_editorial'), autonomia=meta.get('decisao_autonomia'))
    salvar_json(saida.with_suffix('.transcricao.json'), {'palavras': [dict(p, t=textos[i]) for i, p in enumerate(palavras)]})
    escrever_saidas(saida, ficha, meta)

    if parte:                      # na série não faz versão B nem espanhol (fica confuso)
        return saida

    # versão B (teste A/B): mesma edição, mudando a pergunta, o template ou os dois (ab_variar)
    if AB_TESTE and (tem_perg_b or variar == "template"):
        muda_perg, muda_tpl = variar in ("pergunta", "ambos"), variar in ("template", "ambos")
        perg_b = dados["pergunta_b"] if muda_perg else dados["pergunta"]
        dest_b = dados.get("destaque_b") if muda_perg else dados.get("destaque")
        er_b = com_sons(estilo_de(tpl_b), tpl_b["efeitos"]) if muda_tpl else estilo_render
        log(f"Montando a versão B (teste A/B de {variar})...")
        saida_b = saida.with_name(saida.stem + "_B.mp4")
        if CLEAN:                                  # no clean a pergunta é o texto do gancho
            avisos_b = [a for a in avisos if a[3] not in ("Gancho", "GanchoMeio")] + ganchos(perg_b, dest_b)
            ass_b = fazer_ass(margem, avisos_b, f"legenda{sufixo}_B.ass", tpl_b)
            renderizar(video, None, ass_b, saida_b, modo, None, 0, expr_x, gancho_t, boom,
                       layout=layout, extras=extras, estilo_render=er_b, previa=previa_gancho)
        else:
            if muda_perg:
                tb, fb, yb = montar_topo(foto_path, perg_b, dest_b, meta.get("canal", ""), pasta,
                                         inteira=eh_thumbnail, so_faixa=usa_layout)
                yb += y_faixa - y_base_faixa
            else:
                tb, fb, yb = img_topo, img_faixa, y_faixa
            ass_b = fazer_ass(margem, None, f"legenda{sufixo}_B.ass", tpl_b) if muda_tpl else ass
            renderizar(video, tb, ass_b, saida_b, modo, fb, yb, expr_x, gancho_t, boom,
                       layout=layout, extras=extras, estilo_render=er_b, previa=previa_gancho)
        ficha_b = dict(ficha, pergunta=perg_b, variante="B", template=tpl_b["nome"])
        ficha_b.pop("capa", None)
        escrever_saidas(saida_b, ficha_b, meta)
        print(f"   versão B: {perg_b if muda_perg else ''}{' · ' if variar == 'ambos' else ''}"
              f"{'template ' + tpl_b['nome'] if muda_tpl else ''}")

    # versão em espanhol (2º canal)
    if ESPANHOL and palavras:
        try:
            versao_espanhol(video, palavras, textos, dados, meta, ficha, saida, pasta, modo,
                            foto_path, eh_thumbnail, expr_x, gancho_t, boom, legenda,
                            layout=layout, extras=[e for e in extras if "emoji" not in Path(e["png"]).name
                                    and not Path(e["png"]).name.startswith("cta_")],
                            margem=margem, y_ajuste=y_faixa - y_base_faixa, estilo_render=estilo_render,
                            previa=previa_gancho)
        except Exception as e:
            print(f"   ⚠ não consegui fazer a versão em espanhol: {str(e)[:150]}")
    return saida


def main():
    global MODELO_WHISPER
    ap = argparse.ArgumentParser(description="Gera corte 9:16 com foto, faixa vermelha e legenda.")
    ap.add_argument("fonte", help="Link do YouTube/Twitch ou vídeo no PC")
    ap.add_argument("--inicio", required=True)
    ap.add_argument("--fim", required=True)
    ap.add_argument("--foto", help="imagem pro topo")
    ap.add_argument("--topo", choices=["auto", "thumb", "frame", "thumbnail"], default="auto",
                    help="auto = thumbnail do YouTube; frame = Claude escolhe um frame do corte")
    ap.add_argument("--pergunta", help="texto fixo da faixa (sem isso o Claude cria)")
    ap.add_argument("--modo", choices=["cortado", "inteiro"], default="cortado")
    ap.add_argument("--sem-legenda", action="store_true",
                    help="não queima legenda (ainda gera .srt pra você editar)")
    ap.add_argument("--sem-transcricao", action="store_true",
                    help="nem transcreve (mais rápido, mas o Claude só vê título e imagens)")
    ap.add_argument("--sem-claude", action="store_true")
    ap.add_argument("--modelo", default=MODELO_WHISPER)
    ap.add_argument("--transcricao-json", help=argparse.SUPPRESS)
    a = ap.parse_args()
    MODELO_WHISPER = a.modelo
    teste = json.loads(Path(a.transcricao_json).read_text(encoding="utf-8")) if a.transcricao_json else None
    gerar_corte(a.fonte, a.inicio, a.fim, foto=a.foto, pergunta=a.pergunta,
                legenda=not a.sem_legenda, transcrever_audio=not a.sem_transcricao,
                modo=a.modo, topo=a.topo, usar_claude=not a.sem_claude,
                transcricao_teste=teste)


if __name__ == "__main__":
    main()
