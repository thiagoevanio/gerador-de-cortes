"""
Chat de lives que JÁ ACABARAM — VOD da Twitch e live antiga do YouTube.

O chat é o melhor "termômetro" de um momento (todo mundo reage junto), e não custa IA:
baixa as mensagens com o tempo de cada uma, mede onde o chat explodiu e devolve esses trechos
como candidatos. A IA só escolhe entre eles (ou nem isso, se estiver sem IA).

Também lê um arquivo de chat que você já tenha:
  - TwitchDownloader (.json)          - chat-downloader (.json)
  - yt-dlp do YouTube (.live_chat.json)   - texto "[0:12:34] fulano: mensagem"
"""
from __future__ import annotations

import json
import re
import statistics
import time
import urllib.request
from collections import Counter
from pathlib import Path

RISADA = re.compile(r"k{3,}|ka(ka)+|rs(rs)+|ha(ha)+|he(he)+|kek|lul|omegalul|😂|🤣|💀", re.I)
REACAO = re.compile(r"\b(clipa|clip|clipe|corta|corte|caralho|mds|meu deus|nossa|vish|eita|que isso|"
                    r"wtf|omg|absurdo|n[ãa]o acredito|monstro|insano)\b|[!?]{3,}|😱|😳|🔥", re.I)
CLIENT_ID_TWITCH = "kimne78kx3ncx6brgo4mv6wki5h1ko"     # o mesmo do site da Twitch (público)
HASH_COMENTARIOS = "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"


# ---------------- ler arquivos de chat ----------------
def _tempo(txt):
    p = [float(x) for x in txt.split(":")]
    s = 0.0
    for x in p:
        s = s * 60 + x
    return s


def _json_ok(texto):
    try:
        json.loads(texto)
        return True
    except ValueError:
        return False


def ler_arquivo(caminho) -> list[tuple[float, str, str]]:
    """Lê qualquer formato conhecido. Devolve [(segundo_no_video, usuario, mensagem)], ordenado."""
    caminho = Path(caminho)
    texto = caminho.read_text(encoding="utf-8", errors="ignore")
    msgs = []
    bruto = texto.lstrip()
    if bruto.startswith("{") and '"comments"' in bruto[:5000]:              # TwitchDownloader
        dados = json.loads(bruto)
        for c in dados.get("comments", []):
            corpo = (c.get("message") or {}).get("body") or ""
            autor = (c.get("commenter") or {}).get("name") or (c.get("commenter") or {}).get("display_name") or ""
            if corpo:
                msgs.append((float(c.get("content_offset_seconds", 0)), autor, corpo))
    elif bruto.startswith("[") and _json_ok(bruto):                          # chat-downloader
        for c in json.loads(bruto):
            t = c.get("time_in_seconds")
            if t is None or not c.get("message"):
                continue
            msgs.append((float(t), (c.get("author") or {}).get("name", ""), c["message"]))
    elif "replayChatItemAction" in bruto[:20000]:                            # yt-dlp (YouTube)
        for linha in texto.splitlines():
            try:
                msgs.extend(_linha_youtube(json.loads(linha)))
            except (ValueError, KeyError, TypeError):
                continue
    else:                                                                    # texto "[0:12:34] fulano: msg"
        for linha in texto.splitlines():
            m = re.match(r"\s*\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s+([^:]{1,40}):\s*(.+)", linha)
            if m:
                msgs.append((_tempo(m[1]), m[2].strip(), m[3].strip()))
    return sorted(msgs)


def _linha_youtube(obj):
    acao = obj.get("replayChatItemAction") or {}
    t = float(acao.get("videoOffsetTimeMsec", obj.get("videoOffsetTimeMsec", 0))) / 1000
    saida = []
    for a in acao.get("actions", []):
        item = (a.get("addChatItemAction") or {}).get("item") or {}
        r = item.get("liveChatTextMessageRenderer") or item.get("liveChatPaidMessageRenderer")
        if not r:
            continue
        partes = []
        for run in (r.get("message") or {}).get("runs", []):
            if "text" in run:
                partes.append(run["text"])
            elif "emoji" in run:
                atalhos = run["emoji"].get("shortcuts") or []
                partes.append(atalhos[0] if atalhos else run["emoji"].get("emojiId", ""))
        autor = (r.get("authorName") or {}).get("simpleText") or r.get("authorExternalChannelId", "")
        if partes:
            saida.append((t, autor, "".join(partes)))
    return saida


def chat_ao_lado(video) -> Path | None:
    """Arquivo de chat com o mesmo nome do vídeo (ex: live.mp4 + live.chat.json / live.live_chat.json)."""
    video = Path(video)
    for sufixo in (".chat.json", ".live_chat.json", ".json", ".chat.txt", "_chat.json", "_chat.txt"):
        c = video.with_name(video.stem + sufixo)
        if c.is_file() and c.suffix != ".mp4":
            try:
                if ler_arquivo(c):
                    return c
            except (OSError, ValueError):
                continue
    return None


# ---------------- baixar ----------------
def id_vod_twitch(url):
    m = re.search(r"twitch\.tv/(?:[^/]+/)?videos?/(\d+)", str(url))
    return m[1] if m else None


def baixar_twitch(video_id, log=print, limite_seg=240, max_paginas=6000):
    """Chat do VOD pela API pública do site da Twitch (paginando pelo segundo do vídeo)."""
    msgs, vistos, offset, paginas = [], set(), 0.0, 0
    inicio = time.time()
    while paginas < max_paginas and time.time() - inicio < limite_seg:
        corpo = json.dumps([{"operationName": "VideoCommentsByOffsetOrCursor",
                             "variables": {"videoID": str(video_id), "contentOffsetSeconds": int(offset)},
                             "extensions": {"persistedQuery": {"version": 1, "sha256Hash": HASH_COMENTARIOS}}}])
        req = urllib.request.Request("https://gql.twitch.tv/gql", data=corpo.encode(), method="POST",
                                     headers={"Client-Id": CLIENT_ID_TWITCH, "Content-Type": "text/plain"})
        with urllib.request.urlopen(req, timeout=20) as r:
            dados = json.loads(r.read().decode("utf-8"))
        video = ((dados[0] if isinstance(dados, list) else dados).get("data") or {}).get("video") or {}
        com = video.get("comments") or {}
        arestas = com.get("edges") or []
        if not arestas:
            break
        ultimo = offset
        for e in arestas:
            n = e.get("node") or {}
            if n.get("id") in vistos:
                continue
            vistos.add(n.get("id"))
            t = float(n.get("contentOffsetSeconds") or 0)
            texto = "".join(f.get("text", "") for f in (n.get("message") or {}).get("fragments") or [])
            autor = (n.get("commenter") or {}).get("login", "")
            if texto:
                msgs.append((t, autor, texto))
            ultimo = max(ultimo, t)
        paginas += 1
        if paginas % 50 == 0:
            log(f"   chat do VOD: {len(msgs)} mensagens ({int(ultimo // 60)} min)...")
        if not (com.get("pageInfo") or {}).get("hasNextPage"):
            break
        offset = ultimo + 1 if ultimo + 1 > offset else offset + 5      # sempre anda pra frente
        time.sleep(0.05)
    return sorted(msgs)


def baixar_youtube(url, pasta: Path, log=print):
    """Chat de uma live antiga do YouTube (o yt-dlp baixa como 'legenda' live_chat)."""
    import yt_dlp
    opcoes = {"skip_download": True, "writesubtitles": True, "subtitleslangs": ["live_chat"],
              "outtmpl": str(Path(pasta) / "chat.%(ext)s"), "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opcoes) as y:
        y.download([url])
    arq = next(Path(pasta).glob("chat*.live_chat.json"), None)
    return ler_arquivo(arq) if arq else []


def baixar(url, pasta: Path, info=None, log=print):
    """Chat da live antiga, se houver. None = não tem / não conseguiu (segue sem chat)."""
    try:
        vid = id_vod_twitch(url)
        if vid:
            log("💬 Baixando o chat do VOD da Twitch (é de graça, sem IA)...")
            msgs = baixar_twitch(vid, log)
        elif re.search(r"youtu\.?be", str(url)) and info and (
                info.get("was_live") or info.get("live_status") in ("was_live", "post_live")):
            log("💬 Baixando o chat da live antiga do YouTube (sem IA)...")
            msgs = baixar_youtube(url, pasta, log)
        else:
            return None
    except Exception as e:                       # sem internet, API mudou, chat desativado...
        log(f"   (não consegui o chat: {str(e)[:100]} — sigo pelo áudio)")
        return None
    if len(msgs) < 50:
        log("   (chat muito pequeno — sigo pelo áudio)")
        return None
    log(f"   {len(msgs)} mensagens de chat.")
    return msgs


# ---------------- achar os picos ----------------
def picos(msgs, total, dur, n=6, atraso=7.0, passo=5):
    """Onde o chat explodiu. Devolve [{'ini','fim','pico','nota','resumo'}] (sem sobrepor).
    'atraso': o chat reage alguns segundos DEPOIS do lance — o trecho começa antes do pico."""
    if not msgs:
        return []
    total = total or (msgs[-1][0] + 30)
    nb = int(total // passo) + 1
    usuarios = [set() for _ in range(nb)]
    risadas, reacoes, qtd = [0] * nb, [0] * nb, [0] * nb
    for t, u, m in msgs:
        i = int(t // passo)
        if 0 <= i < nb:
            usuarios[i].add(u or f"anon{len(usuarios[i])}")
            qtd[i] += 1
            risadas[i] += bool(RISADA.search(m))
            reacoes[i] += bool(REACAO.search(m))
    # nota de cada janela de 15s, comparada com o "normal" dos 10 minutos em volta
    janela = 3
    bruto = []
    for i in range(nb):
        u = len(set().union(*usuarios[i:i + janela]))
        r = sum(risadas[i:i + janela])
        x = sum(reacoes[i:i + janela])
        q = max(1, sum(qtd[i:i + janela]))
        bruto.append(u * (1 + 1.5 * r / q + 1.0 * x / q))
    raio = int(300 // passo)
    notas = []
    for i, v in enumerate(bruto):
        viz = bruto[max(0, i - raio):i + raio + 1]
        base = statistics.median(viz) if viz else 0
        notas.append(v / (base + 2.0))
    escolhidos = []
    for nota, i in sorted(((v, i) for i, v in enumerate(notas)), reverse=True):
        if nota < 1.6 or len(escolhidos) >= n:
            break
        pico = i * passo + passo * janela / 2
        evento = max(0.0, pico - atraso)
        ini, fim = max(0.0, evento - dur * 0.65), min(total, evento + dur * 0.65)
        if fim - ini < 15 or any(ini < e["fim"] and fim > e["ini"] for e in escolhidos):
            continue
        perto = [m for t, u, m in msgs if pico - 15 <= t <= pico + 10]
        comuns = [m for m, _ in Counter(x.strip().lower()[:40] for x in perto).most_common(6)]
        escolhidos.append({"ini": round(ini, 2), "fim": round(fim, 2), "pico": round(pico, 2),
                           "nota": round(nota, 2), "resumo": " | ".join(comuns)[:220]})
    return escolhidos
