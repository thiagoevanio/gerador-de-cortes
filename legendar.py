"""Legendar um vídeo pronto (aba 📝 Legendar): só a legenda, sem cortar nem mudar o vídeo.

Fluxo: transcrever (Whisper, com as travas anti-repetição) → corrigir nomes e marcar palavras-chave
com IA (opcional, com a trava contra legenda duplicada) → você revisa o texto, frase por frase →
queimar a legenda no vídeo com um template de edição (mesmos estilos dos cortes) + .srt ao lado.

Serve pra vídeo vertical, horizontal ou quadrado: a legenda é desenhada na tela do PRÓPRIO vídeo
(nada de esticar fonte), o áudio sai intacto e o fps é o da fonte.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import cortes

EXTENSOES = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".ts", ".flv", ".wmv")


# ------------------------------------------------------------------ o vídeo
def info(video) -> dict:
    """Largura, altura, duração, fps e codec de áudio do vídeo (ffprobe)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                       creationflags=cortes.SEM_JANELA)
    if r.returncode != 0:
        raise ValueError("Não consegui ler esse arquivo de vídeo.")
    dados = json.loads(r.stdout or "{}")
    vs = [s for s in dados.get("streams", []) if s.get("codec_type") == "video"]
    au = [s for s in dados.get("streams", []) if s.get("codec_type") == "audio"]
    if not vs:
        raise ValueError("Esse arquivo não tem imagem de vídeo.")
    v = vs[0]
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    giro = str((v.get("tags") or {}).get("rotate", "0"))
    for sd in v.get("side_data_list") or []:
        giro = str(sd.get("rotation", giro))
    if giro.lstrip("-") in ("90", "270"):
        w, h = h, w                                # vídeo de celular gravado "deitado"
    try:
        num, den = str(v.get("avg_frame_rate") or "30/1").split("/")
        fps = round(float(num) / max(1.0, float(den)), 3)
    except (ValueError, ZeroDivisionError):
        fps = 30.0
    return {"largura": w, "altura": h, "fps": fps or 30.0,
            "duracao": float((dados.get("format") or {}).get("duration") or 0),
            "audio": (au[0].get("codec_name") if au else None)}


def tela(largura, altura):
    """Tela da legenda (PlayRes) na escala dos cortes: o lado menor vira 1080. Assim o 'tamanho 62' e
    a 'posição 170' significam a mesma coisa num vídeo vertical, horizontal ou quadrado."""
    k = 1080 / max(1, min(largura, altura))
    return int(round(largura * k)), int(round(altura * k))


# ------------------------------------------------------------------ transcrição + IA
def transcrever(video, pasta, log=print, modelo=None) -> list[dict]:
    if not info(video)["audio"]:
        raise ValueError("Esse vídeo não tem áudio — não tem o que legendar.")
    nome = Path(video).stem.replace("_", " ")
    palavras = cortes.transcrever(Path(video), Path(pasta), modelo=modelo,
                                  dica=cortes.dica_transcricao({"titulo": nome}))
    if not palavras:
        raise ValueError("Não encontrei fala nesse vídeo.")
    return palavras


def melhorar_com_ia(palavras, log=print, corrigir=True, enfase=True, bloco=350) -> list[dict]:
    """Corrige nomes/acentos e marca as palavras-chave, em pedaços (vídeo longo cabe). Toda correção
    passa pela trava contra palavra duplicada; ênfase só em palavra forte (no máximo 1 a cada ~8)."""
    if not (corrigir or enfase) or cortes.IA_PRINCIPAL == "nenhuma":
        return palavras
    import ia_cortes
    import otimizador_corte
    saida = [dict(p) for p in palavras]
    partes = range(0, len(saida), bloco)
    for n, ini in enumerate(partes, 1):
        trecho = saida[ini:ini + bloco]
        log(f"IA revisando a legenda ({n}/{len(partes)})...")
        numeradas = " ".join(f"{i}:{p['t']}" for i, p in enumerate(trecho))
        chaves = []
        if corrigir:
            chaves.append('"correcoes": {"número": "PalavraCorrigida"} SÓ com as palavras erradas da '
                          'transcrição (nomes próprios, marcas, gírias, acentos). Cada valor é UMA palavra. '
                          '{} se estiver tudo certo.')
        if enfase:
            chaves.append(f'"enfase": lista com até {max(1, len(trecho) // 8)} números das palavras de mais '
                          'impacto (nomes, números, palavras fortes) pra ficarem coloridas. [] se nada merecer.')
        prompt = ("Transcrição automática de um vídeo em português (pode ter erros). Formato número:palavra.\n"
                  f"<transcricao>\n{numeradas}\n</transcricao>\n"
                  "Responda APENAS com um JSON com estas chaves:\n" + "\n".join(f"- {c}" for c in chaves))
        r = cortes.ia_json(prompt, tarefa="legendar", timeout=300)
        if not isinstance(r, dict):
            log("   ⚠ a IA não respondeu nesse pedaço — fica a transcrição do Whisper.")
            continue
        if corrigir and r.get("correcoes"):
            textos, _ = otimizador_corte.reconciliar_palavras_ia(trecho, None, r.get("correcoes"))
            mudou = sum(1 for p, t in zip(trecho, textos) if p["t"] != t)
            for p, t in zip(trecho, textos):
                p["t"] = t
            if mudou:
                log(f"   {mudou} palavra(s) corrigida(s).")
        if enfase and isinstance(r.get("enfase"), list):
            fortes = []                                # filtra as fracas ANTES de limitar a quantidade
            for k in r["enfase"]:
                try:
                    k = int(k)
                except (TypeError, ValueError):
                    continue
                if 0 <= k < len(trecho) and ia_cortes._forte(trecho[k]["t"]) and k not in fortes:
                    fortes.append(k)
            for k in fortes[:max(1, len(trecho) // 8)]:
                trecho[k]["enfase"] = True
    return saida


def sem_muletas(palavras) -> list[dict]:
    """Tira da LEGENDA (o vídeo não muda) 'hum', 'éé', 'ahn' e companhia."""
    import efeitos
    saida = []
    for i, p in enumerate(palavras):
        if not efeitos.eh_vicio(p, palavras[i - 1] if i else None):
            saida.append(p)
    return saida


# ------------------------------------------------------------------ revisão do texto
def frases(palavras, maximo=9, pausa=0.6) -> list[list[int]]:
    """Índices das palavras agrupados em frases (pra revisar uma frase por linha)."""
    grupos, atual = [], []
    for i, p in enumerate(palavras):
        if atual and (len(atual) >= maximo or p["ini"] - palavras[atual[-1]]["fim"] > pausa):
            grupos.append(atual)
            atual = []
        atual.append(i)
        if re.search(r"[.!?…]$", p["t"]) and len(atual) >= 3:
            grupos.append(atual)
            atual = []
    if atual:
        grupos.append(atual)
    return grupos


def _mmss(s):
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def texto_para_revisar(palavras) -> str:
    """Uma frase por linha, com o tempo na frente: '[00:12] ele falou que...'."""
    return "\n".join(f"[{_mmss(palavras[g[0]]['ini'])}] " + " ".join(palavras[i]["t"] for i in g)
                     for g in frases(palavras))


def aplicar_revisao(palavras, texto) -> list[dict]:
    """Volta o texto revisado pras palavras com tempo. Linha com a MESMA quantidade de palavras: troca
    só o texto (mantém o tempo exato de cada uma). Linha com quantidade diferente: as palavras novas
    dividem o tempo da frase em partes proporcionais ao tamanho. Linha apagada = frase sem legenda."""
    grupos = frases(palavras)
    linhas = [ln for ln in str(texto).splitlines() if ln.strip()]
    linhas = [re.sub(r"^\s*\[\d{1,3}:\d{2}\]\s*", "", ln).strip() for ln in linhas]
    if len(linhas) > len(grupos):
        raise ValueError(f"O texto tem {len(linhas)} linhas, mas a legenda tem {len(grupos)} frases. "
                         "Corrija dentro das linhas (não crie linhas novas).")
    if len(linhas) < len(grupos):
        raise ValueError(f"Faltam linhas: a legenda tem {len(grupos)} frases e o texto {len(linhas)}. "
                         "Pra tirar uma frase, deixe só o tempo dela na linha, ex.: [00:12]")
    saida = []
    for g, linha in zip(grupos, linhas):
        novas = linha.split()
        velhas = [palavras[i] for i in g]
        if not novas:
            continue
        if len(novas) == len(velhas):
            saida += [dict(p, t=t) for p, t in zip(velhas, novas)]
            continue
        ini, fim = velhas[0]["ini"], velhas[-1]["fim"]
        pesos = [max(2, len(t)) for t in novas]
        total, t0 = sum(pesos), ini
        for t, peso in zip(novas, pesos):
            d = (fim - ini) * peso / total
            saida.append({"t": t, "ini": round(t0, 3), "fim": round(t0 + d * 0.92, 3)})
            t0 += d
    return saida


# ------------------------------------------------------------------ a legenda no vídeo
def opcoes_padrao() -> dict:
    cfg = cortes.carregar_config(cortes.PERFIL_EM_USO)
    return {"template": cfg.get("template_edicao") or "Clássico", "margem": int(cfg.get("legenda_margem", 170)),
            "tamanho": int(cfg.get("legenda_tamanho", 62)), "palavras": int(cfg.get("legenda_palavras", 3)),
            "marca": False, "corrigir": True, "enfase": True, "sem_muletas": True}


def _template(op):
    import templates_edicao as te
    nome = op.get("template") or "Clássico"
    if nome == te.AUTOMATICO:
        nome = te.PADRAO
    tpl = te.resolver(nome)
    tpl["legenda"]["palavras"] = int(op.get("palavras") or tpl["legenda"].get("palavras") or 3)
    return tpl


def montar_ass(palavras, destino, video_info, op) -> Path:
    pw, ph = tela(video_info["largura"], video_info["altura"])
    margem = max(10, min(int(op.get("margem", 170)), int(ph * 0.85)))
    antes = cortes.MARCA
    try:
        if not op.get("marca"):
            cortes.MARCA = ""
        return cortes.gerar_ass(palavras, [p["t"] for p in palavras], Path(destino),
                                duracao=video_info["duracao"], margem=margem, template=_template(op),
                                largura=pw, altura=ph, tamanho_base=int(op.get("tamanho", 62)))
    finally:
        cortes.MARCA = antes


def _pasta_com_fontes():
    pasta = Path(tempfile.mkdtemp(prefix="legendar_"))
    for f in (cortes.PASTA_PROJETO / "fontes").glob("*.[ot]tf"):
        shutil.copy2(f, pasta / f.name)
    return pasta


def previa(video, op, palavras=None, t=None, largura_saida=360):
    """Um quadro do PRÓPRIO vídeo com a legenda no estilo escolhido (PIL.Image). Com a transcrição
    pronta, mostra a frase de verdade daquele momento."""
    from PIL import Image
    vi = info(video)
    pw, ph = tela(vi["largura"], vi["altura"])
    if t is None:
        t = vi["duracao"] * 0.35
    exemplo = palavras or [{"t": w, "ini": 0.5 * i, "fim": 0.5 * i + 0.45, "enfase": w == "PROFISSIONAL"}
                           for i, w in enumerate(["SUA", "LEGENDA", "PROFISSIONAL", "AQUI"])]
    if palavras:                                   # a frase falada perto do quadro escolhido
        perto = min(range(len(palavras)), key=lambda i: abs(palavras[i]["ini"] - t))
        exemplo = palavras[perto:perto + 6]
    base = exemplo[0]["ini"]
    exemplo = [dict(p, ini=p["ini"] - base, fim=p["fim"] - base) for p in exemplo]
    pasta = _pasta_com_fontes()
    try:
        montar_ass(exemplo, pasta / "p.ass", dict(vi, duracao=1.0), op)
        alvo = min(len(exemplo) - 1, 1)
        quando = exemplo[alvo]["ini"] + 0.3          # 2ª palavra falando, animação já terminou
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={pw}:{ph},setpts=PTS-STARTPTS+{quando:.2f}/TB,ass=p.ass:fontsdir=.",
                            "q.png"], cwd=pasta, capture_output=True, timeout=60, creationflags=cortes.SEM_JANELA)
        if r.returncode != 0 or not (pasta / "q.png").exists():
            raise ValueError("Não consegui gerar a prévia.")
        img = Image.open(pasta / "q.png").convert("RGB")
        img.load()
        k = largura_saida / img.width if img.width >= img.height else (largura_saida * 16 / 9) / img.height
        return img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


PASTA_PREVIAS = cortes.PASTA_PROJETO / "analises" / "previas"


def video_previa(video, palavras, op, log=print, limite_s=240) -> Path:
    """Versão LEVE do vídeo com a legenda (lado menor 540 px, codificação rápida) pra assistir antes
    de queimar a definitiva. Vídeo longo: só os primeiros 'limite_s' segundos. Cada prévia tem nome
    próprio (o player pode estar com a anterior aberta) e as antigas são apagadas."""
    import time
    video = Path(video).resolve()
    vi = info(video)
    PASTA_PREVIAS.mkdir(parents=True, exist_ok=True)
    for velha in PASTA_PREVIAS.glob("legendar_previa_*.mp4"):
        try:
            velha.unlink()
        except OSError:
            pass                                   # aberta no player: fica pra próxima
    destino = PASTA_PREVIAS / f"legendar_previa_{int(time.time())}.mp4"
    dur = min(vi["duracao"], float(limite_s)) if vi["duracao"] else float(limite_s)
    pw, ph = (540, -2) if vi["largura"] <= vi["altura"] else (-2, 540)
    pasta = _pasta_com_fontes()
    try:
        montar_ass(palavras, pasta / "legenda.ass", vi, op)
        log("Preparando a prévia pra assistir" + (f" (primeiros {int(dur)} s)" if dur < vi["duracao"] else "")
            + "...")
        cortes.rodar(["ffmpeg", "-y", "-i", str(video), "-t", f"{dur:.2f}", "-map", "0:v:0", "-map", "0:a:0?",
                      "-vf", f"ass=legenda.ass:fontsdir=.,scale={pw}:{ph}", "-c:v", "libx264", "-preset", "ultrafast",
                      "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
                      str(destino)], cwd=pasta, progresso=("Prévia", dur))
        return destino
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def saida_para(video) -> Path:
    video = Path(video)
    destino = video.with_name(video.stem + "_legendado.mp4")
    n = 2
    while destino.exists():
        destino = video.with_name(f"{video.stem}_legendado_{n}.mp4")
        n += 1
    return destino


def queimar(video, palavras, op, destino=None, log=print) -> Path:
    """Desenha a legenda no vídeo (render pelo chip de vídeo quando tiver) e salva o .srt ao lado.
    O áudio é copiado sem mexer (vira AAC só se o formato não couber num .mp4)."""
    video = Path(video).resolve()
    vi = info(video)
    destino = Path(destino) if destino else saida_para(video)
    pasta = _pasta_com_fontes()
    try:
        montar_ass(palavras, pasta / "legenda.ass", vi, op)
        audio = (["-c:a", "copy"] if vi["audio"] in ("aac", "mp3", "alac", "opus")
                 else ["-c:a", "aac", "-b:a", "256k"])
        temporario = pasta / "saida.mp4"
        with cortes.contexto_render():
            log("Desenhando a legenda no vídeo...")
            cortes.rodar(["ffmpeg", "-y", "-i", str(video), "-map", "0:v:0", "-map", "0:a:0?",
                          "-vf", "ass=legenda.ass:fontsdir=.", *cortes.args_encoder_video(intermediario=False),
                          "-pix_fmt", "yuv420p", *audio, "-movflags", "+faststart", str(temporario)],
                         cwd=pasta, progresso=("Legendando", vi["duracao"]))
        from qualidade import inspecionar
        rel = inspecionar(temporario, vi["duracao"], exigir_audio=bool(vi["audio"]), aprofundar=False)
        if not rel["aprovado"]:
            raise RuntimeError("O vídeo legendado não passou na revisão técnica: " + "; ".join(rel["erros"]))
        shutil.move(str(temporario), str(destino))
        cortes.gerar_srt(palavras, [p["t"] for p in palavras], destino.with_suffix(".srt"))
        (destino.with_suffix(".legenda.json")).write_text(
            json.dumps({"video": video.name, "opcoes": op, "palavras": palavras}, ensure_ascii=False),
            encoding="utf-8")
        log(f"✅ Pronto: {destino.name}")
        return destino
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def legendar(video, op=None, log=print, revisar=None) -> Path:
    """Tudo de uma vez (sem a revisão na tela): transcreve, melhora com IA e queima."""
    op = dict(opcoes_padrao(), **(op or {}))
    pasta = Path(tempfile.mkdtemp(prefix="legendar_audio_"))
    try:
        palavras = transcrever(video, pasta, log)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    palavras = melhorar_com_ia(palavras, log, op.get("corrigir", True), op.get("enfase", True))
    if op.get("sem_muletas", True):
        palavras = sem_muletas(palavras)
    if revisar:
        palavras = revisar(palavras)
    return queimar(video, palavras, op, log=log)
