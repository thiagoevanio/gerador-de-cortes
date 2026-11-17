"""Downloads (YouTube, Twitch, Kick): rápidos e que nunca ficam travados.

Por que existe (medido em 16/11/2026, vídeo de 18 min, trecho de 45 s):
  • O YouTube agora exige resolver um desafio em JavaScript ("n challenge"). Sem isso ele estrangula a
    velocidade e o download do trecho ficava parado por mais de 10 minutos. Com o pacote yt-dlp-ejs e
    o Node (ou Deno), o yt-dlp resolve sozinho → opcoes_ytdlp() liga isso em todo lugar.
  • O jeito antigo de pegar só o trecho (download_ranges) abre o vídeo inteiro numa conexão só pelo
    ffmpeg: 86 s mesmo com o desafio resolvido, e sem limite de tempo. trecho_rapido() lê o índice
    (sidx) do arquivo e baixa SÓ os pedaços do trecho, em pedidos pequenos: 3,5 s.
  • O jeito antigo continua como reserva, mas num processo separado com limite de tempo.
"""
from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PEDACO = 10 * 1024 * 1024          # pedidos de no máximo 10 MB (o YouTube não estrangula)
NODE_PADRAO = (r"C:\Program Files\nodejs\node.exe", r"C:\Program Files (x86)\nodejs\node.exe")


# ============================================================ opções comuns do yt-dlp
def motor_js():
    """Deno ou Node: o yt-dlp usa pra resolver o desafio do YouTube. None se não tiver nenhum."""
    deno = shutil.which("deno")
    if deno:
        return {"deno": {"path": deno}}
    node = shutil.which("node") or next((p for p in NODE_PADRAO if os.path.exists(p)), None)
    if node:
        return {"node": {"path": node}}
    return None


def tem_ejs():
    try:
        import yt_dlp_ejs  # noqa: F401
        return True
    except ImportError:
        return False


def opcoes_ytdlp(**extra):
    """Opções de sempre + desafio do YouTube resolvido + limites de tempo (nada fica pendurado)."""
    op = {"quiet": True, "no_warnings": True, "socket_timeout": 30, "retries": 5, "fragment_retries": 5,
          "http_chunk_size": PEDACO, "concurrent_fragment_downloads": 4}
    js = motor_js()
    if js:
        op["js_runtimes"] = js
    op.update(extra)
    return op


def args_cli_js():
    js = motor_js()
    if not js:
        return []
    nome, cfg = next(iter(js.items()))
    return ["--js-runtimes", f"{nome}:{cfg['path']}"]


# ============================================================ trecho rápido (índice sidx)
def _pegar(fmt, a, b, tentativas=3):
    url = fmt["url"] + ("&" if "?" in fmt["url"] else "?") + f"range={a}-{b}"
    for n in range(1, tentativas + 1):
        try:
            req = urllib.request.Request(url, headers=fmt.get("http_headers") or {})
            with urllib.request.urlopen(req, timeout=30) as r:
                dados = r.read()
            if len(dados) != b - a + 1:
                raise IOError(f"veio {len(dados)} de {b - a + 1} bytes")
            return dados
        except Exception:
            if n == tentativas:
                raise
            time.sleep(n)


def _caixas(dados):
    pos = 0
    while pos + 8 <= len(dados):
        tam, tipo = struct.unpack(">I4s", dados[pos:pos + 8])
        if tam == 1:
            tam = struct.unpack(">Q", dados[pos + 8:pos + 16])[0]
        if tam < 8:
            break
        yield tipo.decode("latin1"), pos, tam
        pos += tam


def ler_indice(cabeca: bytes):
    """Do começo de um mp4 fragmentado: (fim do 'moov', [(início s, fim s, byte a, byte b), ...])."""
    fim_moov, sidx = None, None
    for tipo, pos, tam in _caixas(cabeca):
        if tipo == "moov":
            fim_moov = pos + tam
        elif tipo == "sidx":
            sidx = (pos, tam)
            break
    if not (fim_moov and sidx) or sidx[0] + sidx[1] > len(cabeca):
        return None
    p, tam = sidx
    d = cabeca[p:p + tam]
    versao, escala = d[8], struct.unpack(">I", d[16:20])[0]
    if versao == 0:
        pts, primeiro = struct.unpack(">II", d[20:28])
        q = 28
    else:
        pts, primeiro = struct.unpack(">QQ", d[20:36])
        q = 36
    n = struct.unpack(">H", d[q + 2:q + 4])[0]
    q += 4
    byte, t, partes = p + tam + primeiro, pts / escala, []
    for _ in range(n):
        ref, dur, _sap = struct.unpack(">III", d[q:q + 12])
        q += 12
        tamanho = ref & 0x7FFFFFFF
        partes.append((t, t + dur / escala, byte, byte + tamanho - 1))
        byte += tamanho
        t += dur / escala
    return fim_moov, partes


def baixar_partes(fmt, ini, fim, destino: Path):
    """Baixa o cabeçalho + só os pedaços que cobrem [ini, fim]. Devolve o segundo em que o arquivo começa."""
    cabeca, indice = b"", None
    for tam in (65_536, 1_048_576, 4_194_304):        # o índice costuma estar nos primeiros KB
        cabeca = _pegar(fmt, 0, tam - 1)
        indice = ler_indice(cabeca)
        if indice:
            break
    if not indice:
        raise ValueError("arquivo sem índice (sidx)")
    fim_moov, partes = indice
    usar = [s for s in partes if s[1] > ini - 0.5 and s[0] < fim + 0.5]
    if not usar:
        raise ValueError("o trecho está fora do vídeo")
    a, b = usar[0][2], usar[-1][3]
    with open(destino, "wb") as f:
        f.write(cabeca[:fim_moov])
        for x in range(a, b + 1, PEDACO):
            f.write(_pegar(fmt, x, min(b, x + PEDACO - 1)))
    return usar[0][0]


def formato_trecho(res):
    """Vídeo H.264 em mp4 + áudio m4a separados (os que têm índice). H.264 é leve de decodificar."""
    return (f"bv*[ext=mp4][vcodec^=avc1][height<={res}]+ba[ext=m4a]/"
            f"bv*[ext=mp4][height<={res}]+ba[ext=m4a]")


def trecho_rapido(info, ini, fim, pasta: Path, log=print):
    """Com o info do yt-dlp (format=formato_trecho): baixa só o trecho e monta pasta/original.mp4."""
    import cortes
    formatos = info.get("requested_formats") or []
    if len(formatos) != 2 or any(f.get("protocol") not in ("https", "http") for f in formatos):
        raise ValueError("formato sem vídeo e áudio separados por https")
    video = next(f for f in formatos if f.get("vcodec") not in (None, "none"))
    audio = next(f for f in formatos if f is not video)
    t0 = time.time()
    pv, pa = pasta / "parte_video.mp4", pasta / "parte_audio.m4a"
    iv = baixar_partes(video, ini, fim, pv)
    ia = baixar_partes(audio, ini, fim, pa)
    mb = (pv.stat().st_size + pa.stat().st_size) / 1e6
    log(f"   baixei só o trecho: {mb:.0f} MB em {time.time() - t0:.1f}s ({video.get('height', '?')}p)")
    saida = pasta / "original.mp4"
    cortes.rodar(["ffmpeg", "-y", "-ss", f"{max(0.0, ini - iv):.3f}", "-i", str(pv),
                  "-ss", f"{max(0.0, ini - ia):.3f}", "-i", str(pa), "-t", f"{fim - ini:.3f}",
                  "-map", "0:v:0", "-map", "1:a:0", *cortes.args_encoder_video(intermediario=True),
                  "-c:a", "aac", "-b:a", "192k", "-avoid_negative_ts", "make_zero", str(saida)],
                 progresso=("Preparando o trecho", fim - ini))
    for p in (pv, pa):
        try:
            p.unlink()
        except OSError:
            pass
    return saida


# ============================================================ reserva: yt-dlp com limite de tempo
def trecho_com_limite(url, ini, fim, pasta: Path, formato, ordem, limite_s, log=print):
    """O jeito antigo (download_ranges), mas num processo separado que é encerrado se passar do limite."""
    cmd = [sys.executable, "-m", "yt_dlp", "-q", "--no-warnings", "--no-playlist", *args_cli_js(),
           "-f", formato, "-S", ",".join(ordem), "--download-sections", f"*{ini:.2f}-{fim:.2f}",
           "--force-keyframes-at-cuts", "--merge-output-format", "mp4", "--socket-timeout", "30",
           "--retries", "5", "-o", str(pasta / "original.%(ext)s"), url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=limite_s, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"o download passou de {limite_s // 60} min e foi cancelado")
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or f"yt-dlp saiu com {r.returncode}").strip()[-400:])
    arquivos = [a for a in sorted(pasta.glob("original.*"))
                if a.suffix.lower() not in (".part", ".ytdl") and a.stat().st_size > 10_000]
    if not arquivos:
        raise RuntimeError("o arquivo baixado saiu vazio")
    return arquivos[0]


_ERROS_DEFINITIVOS = ("private video", "video unavailable", "vídeo indisponível", "sign in to confirm your age",
                      "members-only", "this live event will begin", "copyright", "has been removed",
                      "is not available in your country", "unsupported url")


def baixar_trecho(url, inicio, fim, pasta: Path, tentativas=3):
    """Baixa só o trecho. No YouTube, o jeito rápido (trecho_rapido) baixa só os pedaços do
    trecho em segundos; se não der, o jeito tradicional roda com limite de tempo e tenta de novo
    (na última vez com um formato de arquivo único, que falha menos). Nada fica travado pra sempre."""
    import cortes
    import yt_dlp

    cortes.log(f"Baixando só o trecho {cortes.fmt_tempo(inicio)} → {cortes.fmt_tempo(fim)} ...")
    res = 1080 if cortes.BAIXAR_1080 else 720
    eh_youtube = bool(re.search(r"(youtube\.com|youtu\.be)/", str(url)))
    ultimo_erro, info = None, None
    for n in range(1, tentativas + 1):
        plano_b = n == tentativas and tentativas > 1
        for velho in [*pasta.glob("original.*"), *pasta.glob("parte_*")]:   # restos de uma tentativa
            try:
                velho.unlink()
            except OSError:
                pass
        try:
            if eh_youtube and n == 1:
                with yt_dlp.YoutubeDL(opcoes_ytdlp(format=formato_trecho(res))) as ydl:
                    info = ydl.extract_info(url, download=False)
                arquivo = trecho_rapido(info, inicio, fim, pasta, log=print)
            else:
                if info is None:
                    with yt_dlp.YoutubeDL(opcoes_ytdlp()) as ydl:
                        info = ydl.extract_info(url, download=False)
                formato = f"b[ext=mp4][height<={res}]/b[height<={res}]/b" if plano_b else "bv*+ba/b"
                arquivo = trecho_com_limite(
                    url, inicio, fim, pasta, formato, [f"res:{res}", "vcodec:h264", "acodec:m4a"],
                    limite_s=max(300, int((fim - inicio) * 8)), log=print)
            if cortes.duracao_video(arquivo) < 0.5:
                raise RuntimeError("o arquivo baixado saiu vazio")
        except Exception as e:                            # noqa: BLE001 - qualquer falha do yt-dlp/ffmpeg
            ultimo_erro = e
            texto = str(e).lower()
            if any(m in texto for m in _ERROS_DEFINITIVOS) or n == tentativas:
                break
            if eh_youtube and n == 1:
                print(f"   ⚠ o download rápido não deu ({str(e).strip()[:120]}) — usando o jeito tradicional...")
                continue
            espera = 4 * n
            print(f"   ⚠ download falhou ({str(e).strip()[:120]}) — tentando de novo em {espera}s "
                  f"({n + 1}/{tentativas}{', formato mais simples' if n + 1 == tentativas else ''})...")
            time.sleep(espera)
            continue
        if n > 1:
            print(f"   download OK na tentativa {n}.")
        meta = {"titulo": (info or {}).get("title", ""),
                "canal": (info or {}).get("uploader") or (info or {}).get("channel") or "",
                "thumbnail": (info or {}).get("thumbnail")}
        return arquivo, meta
    raise RuntimeError(f"Não consegui baixar o vídeo: {str(ultimo_erro).strip()[:300]}")



def diagnostico():
    """Pro Examinar o PC: o download do YouTube está completo?"""
    js = motor_js()
    return {"ejs": tem_ejs(), "motor": next(iter(js)) if js else None}


# ============================================================ yt-dlp sempre atualizado
BASE = Path(__file__).resolve().parent
ARQ_ATUALIZADO = BASE / "analises" / "ytdlp_atualizado.txt"


def manter_atualizado(log=print, dias=3, forcar=False):
    """A cada 3 dias: pip install -U yt-dlp yt-dlp-ejs. O YouTube muda toda semana e um yt-dlp
    parado acaba falhando ou ficando lento. Avisa só quando atualiza ou quando dá erro."""
    try:
        ultima = float(ARQ_ATUALIZADO.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        ultima = 0.0
    if not forcar and time.time() - ultima < dias * 86400:
        return None
    try:                                   # marca antes: o monitor e a tela não atualizam juntos
        ARQ_ATUALIZADO.parent.mkdir(exist_ok=True)
        ARQ_ATUALIZADO.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass
    py = sys.executable.replace("pythonw.exe", "python.exe")
    try:
        r = subprocess.run([py, "-m", "pip", "install", "-U", "--quiet", "--disable-pip-version-check",
                            "yt-dlp", "yt-dlp-ejs"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        log(f"⚠ não consegui atualizar o yt-dlp agora ({e}); tento de novo depois.")
        return False
    if r.returncode != 0:
        log("⚠ não consegui atualizar o yt-dlp agora; tento de novo depois.")
        return False
    novas = subprocess.run([py, "-c", "import importlib.metadata as m;print(m.version('yt-dlp'), m.version('yt-dlp-ejs'))"],
                           capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
    log(f"⬇ yt-dlp conferido/atualizado ({novas}) — downloads do YouTube em dia.")
    return True
