"""
Cortes LONGOS (16:9, 3 a 8 minutos) — pro YouTube normal, que conta horas assistidas
(a partir de fev/2027 o YouTube pede 8 mil horas em vídeo longo pra monetizar canal novo,
e os Shorts só pagam com 10 milhões de views em 90 dias).

Pega o mesmo momento do corte curto e abre o contexto em volta (começo da história + desfecho),
em tela cheia na horizontal, com legenda embaixo (com destaque de escala e correção de nomes),
a pergunta no topo nos primeiros segundos e o seu @.
Não substitui o curto: é uma opção a mais ("curto", "longo" ou "os dois").
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import tempfile
from pathlib import Path

import cortes

W, H = 1920, 1080


def janela(inicio, fim, alvo, total=None):
    """Abre o contexto em volta do momento: ~60% do tempo extra ANTES (a história) e ~40% depois
    (a reação/desfecho)."""
    extra = max(0.0, alvo - (fim - inicio))
    a = max(0.0, inicio - extra * 0.6)
    b = a + max(alvo, fim - inicio)
    if total:
        if b > total:
            a, b = max(0.0, total - max(alvo, fim - inicio)), total
    return round(a, 2), round(b, 2)


def aplicar_correcoes(palavras, correcoes):
    """Aplica dicionário {'termo_errado': 'Termo Certo'} nas palavras transcritas do corte longo,
    preservando pontuação nas bordas sem precisar reenviar todas as palavras pra IA."""
    if not palavras or not isinstance(correcoes, dict) or not correcoes:
        return [p["t"] for p in palavras]
    mapa = {str(k).strip().lower(): str(v).strip()
            for k, v in correcoes.items()
            if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()}
    if not mapa:
        return [p["t"] for p in palavras]
    saida = []
    for p in palavras:
        bruto = p["t"]
        m = re.match(r"^([^\wÀ-ÿ]*)(.*?)([^\wÀ-ÿ]*)$", bruto, flags=re.UNICODE)
        if not m:
            saida.append(bruto)
            continue
        pref, miolo, suf = m.groups()
        chave = miolo.lower()
        if chave in mapa:
            novo = mapa[chave]
            saida.append(f"{pref}{novo}{suf}")
        else:
            saida.append(bruto)
    return saida


def _ass_longo(palavras, textos, destino: Path, duracao):
    """Legenda pra tela deitada: bloco embaixo, palavra falada em amarelo + leve zoom de destaque, @ no canto."""
    cor = cortes.cor_ass(cortes.COR_LEGENDA_DESTAQUE)
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Leg,{cortes.FONTE_LEGENDA},64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,5,2,2,160,160,70,1
Style: Marca,{cortes.FONTE_LEGENDA},38,&H50FFFFFF,&H50FFFFFF,&H70000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,9,40,40,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    if cortes.MARCA:
        marca = cortes.MARCA if cortes.MARCA.startswith("@") else "@" + cortes.MARCA
        ev.append(f"Dialogue: 1,0:00:00.00,{cortes.tempo_ass(duracao + 1)},Marca,,0,0,0,,{marca}")
    antes = cortes.PALAVRAS_POR_BLOCO
    cortes.PALAVRAS_POR_BLOCO = max(5, antes * 2)          # tela larga: mais palavras por vez
    try:
        blocos = cortes.blocos_legenda(palavras, textos)
    finally:
        cortes.PALAVRAS_POR_BLOCO = antes
    animar = getattr(cortes, "LEGENDA_ANIMADA", True)
    for bi, bloco in enumerate(blocos):
        fim_b = bloco[-1]["fim"]
        prox = blocos[bi + 1][0]["ini"] if bi + 1 < len(blocos) else fim_b + 0.4
        for i, w in enumerate(bloco):
            fim = bloco[i + 1]["ini"] if i + 1 < len(bloco) else min(prox, fim_b + 0.5)
            fim = max(fim, w["ini"] + 0.1)
            partes = []
            for j, x in enumerate(bloco):
                t = x["t"].replace("{", "").replace("}", "")
                if j == i:
                    escala_on = "\\fscx112\\fscy112" if animar else ""
                    escala_off = "\\fscx100\\fscy100" if animar else ""
                    partes.append("{\\c" + cor + escala_on + "}" + t + "{" + escala_off + "\\c&HFFFFFF&}")
                else:
                    partes.append(t)
            ev.append(f"Dialogue: 0,{cortes.tempo_ass(w['ini'])},{cortes.tempo_ass(fim)},Leg,,0,0,0,,"
                      + " ".join(partes))
    destino.write_text(cab + "\n".join(ev) + "\n", encoding="utf-8")
    return destino


def renderizar_longo(video: Path, ass: Path | None, faixa: Path | None, saida: Path, segundos_faixa=5.0):
    """1920x1080. Vídeo em pé ganha fundo desfocado; deitado ocupa a tela toda."""
    entradas = ["-i", video.name]
    filtro = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"boxblur=24:2,eq=brightness=-0.1[fundo];"
              f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[frente];"
              f"[fundo][frente]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[base]")
    atual = "base"
    if faixa:
        entradas += ["-loop", "1", "-i", faixa.name]
        filtro += (f";[1:v]format=rgba,scale=iw*0.8:-1,fade=t=out:st={segundos_faixa - 0.4:.2f}:d=0.4:alpha=1[fx];"
                   f"[{atual}][fx]overlay=(W-w)/2:24:shortest=1:enable='lt(t,{segundos_faixa:.2f})'[cfx]")
        atual = "cfx"
    if ass:
        filtro += f";[{atual}]ass={ass.name}[leg]"
        atual = "leg"
    filtro += f";[{atual}]null[final]"
    mapa = []
    if cortes.tem_audio(video):
        filtro += (";[0:a]highpass=f=75" + cortes.filtro_chiado() + ","
                   "acompressor=threshold=-20dB:ratio=3:attack=8:release=220:makeup=2,"
                   "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,"
                   "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aud]")
        mapa = ["-map", "[aud]"]
    cortes.rodar(["ffmpeg", "-y", *entradas, "-filter_complex", filtro, "-map", "[final]", *mapa,
                  "-shortest", "-r", "30", *cortes.args_encoder_video(intermediario=False),
                  "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                  str(Path(saida).resolve())], cwd=video.parent)
    return saida


def _pedido_texto(k, texto):
    return f"### TRECHO {k}\n{texto[:6000]}"


def pensar_longo(textos, meta):
    """Título/pergunta/descrição e dicionário compacto de correção de nomes dos cortes longos.
    Resposta curta e UMA chamada pra todos os trechos. Devolve lista de dicts (ou padrões sem IA)."""
    padrao = [{"titulo": (meta.get("titulo") or "Melhores momentos")[:90], "pergunta": "VOCÊ VIU ISSO??",
               "destaque": [], "hashtags": ["#cortes"], "descricao": "", "correcoes": {}} for _ in textos]
    if cortes.IA_PRINCIPAL == "nenhuma" or not textos:
        return padrao
    prompt = (f'Você é editor de YouTube brasileiro. Vídeo de origem: "{meta.get("titulo", "")}" — canal '
              f'"{meta.get("canal", "")}". Abaixo há {len(textos)} trecho(s) que viram vídeos LONGOS (3 a 8 min, '
              'horizontal). Pra cada um, responda APENAS JSON {"trechos": [{"titulo": "até 90 caracteres, chamativo '
              'e FIEL", "pergunta": "pergunta curta em MAIÚSCULAS terminando com ??, até 55 caracteres", '
              '"destaque": ["1 ou 2 palavras da pergunta"], "hashtags": ["3 a 5"], "descricao": "2 a 3 frases '
              'resumindo, sem inventar", "correcoes": {"palavra_errada": "PalavraCerta"}}]} na mesma ordem. '
              'Em "correcoes", liste até 10 nomes próprios, canais, jogos ou gírias que a transcrição errou.\n\n' +
              "\n\n".join(_pedido_texto(k, t) for k, t in enumerate(textos, 1)))
    cortes.log(f"IA dando título e corrigindo nomes dos {len(textos)} corte(s) longo(s) (1 chamada só)...")
    resp = cortes.ia_json(prompt, tarefa="longo")
    lista = resp.get("trechos") if isinstance(resp, dict) else None
    if not isinstance(lista, list) or len(lista) != len(textos):
        return padrao
    saida = []
    for p, d in zip(padrao, lista):
        d = d if isinstance(d, dict) else {}
        r = dict(p)
        for k in ("titulo", "pergunta", "descricao"):
            if isinstance(d.get(k), str) and d[k].strip():
                r[k] = d[k].strip()
        for k in ("hashtags", "destaque"):
            if isinstance(d.get(k), list):
                r[k] = [x for x in d[k] if isinstance(x, str)][:8]
        if isinstance(d.get("correcoes"), dict):
            r["correcoes"] = {str(k): str(v) for k, v in list(d["correcoes"].items())[:15]
                              if isinstance(k, str) and isinstance(v, str)}
        saida.append(r)
    return saida


def preparar(fonte, inicio, fim, pasta: Path, alvo=None, meta=None):
    """Baixa/recorta a janela longa, planeja cortes de silêncio e bordas de frase e executa
    em UMA única passada de vídeo (zero re-encode duplicado)."""
    import efeitos
    cfg = cortes.carregar_config(cortes.PERFIL_EM_USO)
    alvo = float(alvo or cfg.get("duracao_longo_seg", 240))
    total = None
    if not re.match(r"^https?://", str(fonte)):
        total = cortes.duracao_video(Path(fonte)) or None
    a, b = janela(float(inicio), float(fim), alvo, total)
    cortes.log(f"Corte longo: {cortes.fmt_tempo(a)} → {cortes.fmt_tempo(b)} ({(b - a) / 60:.1f} min)")
    if re.match(r"^https?://", str(fonte)):
        video, m = cortes.baixar_trecho(fonte, a, b, pasta)
        meta = {**(meta or {}), **m}
    else:
        video, meta = cortes.recortar_local(fonte, a, b, pasta, meta)

    dur_orig = cortes.duracao_video(video)
    manter_unificado = [(0.0, dur_orig)]
    precisa_corte = False

    if cortes.TIRAR_SILENCIOS and cortes.tem_audio(video):
        manter_sil, _, removido = efeitos.intervalos_sem_silencio(video, dur=dur_orig)
        if removido >= 1.0:
            manter_unificado = manter_sil
            precisa_corte = True

    palavras = []
    try:
        wav_pronto = None
        if precisa_corte and cortes.tem_audio(video):
            bruto = cortes.extrair_audio(video, pasta / "audio_bruto.wav")
            wav_pronto = efeitos.recortar_wav_mantidos(bruto, pasta / "audio.wav", manter_unificado)
        palavras = cortes.transcrever(video, pasta, dica=cortes.dica_transcricao(meta), wav_pronto=wav_pronto)
    except ImportError:
        pass
    except TypeError:
        palavras = cortes.transcrever(video, pasta, dica=cortes.dica_transcricao(meta))

    if palavras:                                   # não terminar no meio da frase
        dur_atual = sum(x1 - x0 for x0, x1 in manter_unificado)
        ci, cf = efeitos.ajustar_frase(palavras, [p["t"] for p in palavras], dur_atual)
        if ci or cf:
            rem_frase = ([(0.0, ci)] if ci > 0.05 else []) + ([(dur_atual - cf, dur_atual + 1.0)] if cf > 0.05 else [])
            manter_unificado = efeitos.aplicar_remocao_em_mantidos(manter_unificado, rem_frase)
            palavras, _ = cortes._palavras_entre(palavras, [p["t"] for p in palavras], ci, dur_atual - cf)
            precisa_corte = True

    if precisa_corte:
        video = efeitos.cortar_intervalos_mantidos(video, pasta, manter_unificado, "longo_unico.mp4")

    return {"video": video, "palavras": palavras, "meta": meta, "janela": (a, b), "fonte": str(fonte)}


def finalizar(prep, dados, pasta_saida: Path, pasta: Path, legenda=True, origem_curto=None):
    """Monta o .mp4 16:9 + ficha (tipo 'longo', postado como vídeo normal, sem #shorts)."""
    video, palavras, meta = prep["video"], prep["palavras"], prep["meta"]
    destino_dir = Path(pasta_saida) / "longos"
    destino_dir.mkdir(parents=True, exist_ok=True)
    duracao = cortes.duracao_video(video)
    textos = aplicar_correcoes(palavras, dados.get("correcoes"))
    for p, t in zip(palavras, textos):
        p["t"] = t
    ass = _ass_longo(palavras, textos, pasta / "longo.ass", duracao) if (legenda and palavras) or cortes.MARCA else None
    _, faixa, _ = cortes.montar_topo(None, dados.get("pergunta", "VOCÊ VIU ISSO??"), dados.get("destaque"),
                                     meta.get("canal", ""), pasta, so_faixa=True)
    nome = cortes.nome_seguro(dados.get("titulo") or meta.get("titulo", "") or "corte_longo", 60)
    saida = destino_dir / f"{nome}_longo.mp4"
    n = 2
    while saida.exists():
        saida = destino_dir / f"{nome}_longo_{n}.mp4"
        n += 1
    cortes.log("Montando o corte longo 16:9 (leva uns minutos)...")
    renderizar_longo(video, ass, faixa, saida)
    if palavras:
        cortes.gerar_srt(palavras, textos, saida.with_suffix(".srt"))
    descricao = (dados.get("descricao") or "").strip()
    credito = f"Fonte: {meta.get('canal', '')} — {meta.get('titulo', '')}".strip(" —")
    tags = [t if t.startswith("#") else "#" + t for t in dados.get("hashtags", []) if t]
    ficha = {"tipo": "longo", "formato": "16:9", "titulo": dados.get("titulo", nome)[:100],
             "pergunta": dados.get("pergunta", ""), "hashtags": tags,
             "descricao": "\n\n".join(x for x in (descricao, credito, " ".join(tags)) if x),
             "fonte": prep["fonte"], "inicio": prep["janela"][0], "fim": prep["janela"][1],
             "canal": meta.get("canal", ""), "titulo_original": meta.get("titulo", ""),
             "perfil": cortes.PERFIL_EM_USO, "duracao": round(duracao, 1), "idioma": "pt",
             "curto": str(origem_curto) if origem_curto else None,
             "correcoes_aplicadas": len(dados.get("correcoes") or {}),
             "criado": dt.datetime.now().isoformat(timespec="seconds"), "status": "novo"}
    cortes.escrever_saidas(saida, ficha, meta)
    cortes.log(f"PRONTO (longo): {saida.resolve()}")
    return saida


def dados_do_curto(saida_curto):
    """Reaproveita título/pergunta/hashtags e correções de nomes do corte curto (zero IA a mais)."""
    try:
        p_curto = Path(saida_curto)
        f = json.loads(p_curto.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    correcoes = dict(f.get("correcoes_ia") or {})
    return {"titulo": f.get("titulo", ""), "pergunta": f.get("pergunta", ""), "destaque": [],
            "hashtags": f.get("hashtags", []), "descricao": "", "correcoes": correcoes}


def gerar_longos(fonte, momentos, pasta_saida: Path, meta=None, dados_prontos=None, legenda=True, alvo=None):
    """Gera os cortes longos de vários momentos do mesmo vídeo. Se 'dados_prontos' (do curto) vier,
    não chama IA; senão faz UMA chamada pra todos. Devolve lista de saídas."""
    pasta_saida = Path(pasta_saida)
    raiz = pasta_saida / "_trabalho"
    raiz.mkdir(parents=True, exist_ok=True)
    pastas, preps = [], []
    try:
        for m in momentos:
            pasta = Path(tempfile.mkdtemp(prefix="longo_", dir=raiz))
            pastas.append(pasta)
            preps.append(preparar(fonte, m["inicio"], m["fim"], pasta, alvo, m.get("meta") or meta))
        dados = list(dados_prontos or [])
        if len(dados) != len(preps) or not all(dados):
            faltam = [i for i in range(len(preps)) if i >= len(dados) or not dados[i]]
            novos = pensar_longo([" ".join(p["t"] for p in preps[i]["palavras"]) for i in faltam],
                                 preps[faltam[0]]["meta"] if faltam else {})
            dados = dados + [None] * (len(preps) - len(dados))
            for i, d in zip(faltam, novos):
                dados[i] = d
        saidas = []
        for k, (prep, d, pasta) in enumerate(zip(preps, dados, pastas)):
            saidas.append(finalizar(prep, d, pasta_saida, pasta, legenda,
                                    origem_curto=(momentos[k].get("curto") if k < len(momentos) else None)))
        return saidas
    finally:
        for p in pastas:
            shutil.rmtree(p, ignore_errors=True)
