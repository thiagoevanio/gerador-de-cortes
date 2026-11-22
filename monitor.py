"""
MONITOR DE CORTES — deixa rodando e ele trabalha sozinho
---------------------------------------------------------
- TWITCH: quando um canal da lista entra ao vivo, grava a live + o chat.
  De tempos em tempos (e quando a live acaba) acha os momentos em que o chat
  explodiu (KKKK, KEKW, ???...) e gera os cortes automaticamente.
- YOUTUBE: quando um canal da lista posta vídeo novo, pega os trechos
  "mais repetidos" (gráfico do YouTube). Se o vídeo ainda não tiver esse
  gráfico, o Claude lê a transcrição e escolhe os melhores momentos.

Configuração: canais.json  (pode editar com o monitor rodando)
Rodar:        python monitor.py      (ou dois cliques em monitor.bat)
Parar:        Ctrl + C
"""
from __future__ import annotations

import json
import os
import random
import math
import secrets
import re
import shutil
import socket
import statistics
import subprocess
import sys
import threading
import time
import queue
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from datetime import datetime
from pathlib import Path

import cortes
import momentos
import tendencias
import detector
from fila_tarefas import FilaTarefas
from infraestrutura import salvar_json

BASE = Path(__file__).resolve().parent
ARQ_CONFIG = BASE / "canais.json"
ARQ_ESTADO = BASE / "estado.json"
ARQ_LOG = BASE / "monitor.log"
PASTA_GRAVACOES = BASE / "gravacoes"
PASTA_CORTES = BASE / "cortes_prontos"
ARQ_PARAR = BASE / "parar.flag"

PADRAO = {
    "twitch": [],
    "youtube": [],
    "kick": [],                  # canais da Kick (só o nome)
    "youtube_lives": [],         # canais do YouTube pra gravar quando estiverem AO VIVO
    "clips_twitch": True,        # também corta os clips mais vistos do dia dos canais da Twitch
    "clips_por_dia": 2,
    "verificar_a_cada_min": 5,
    "duracao_corte_seg": 65,     # TikTok só paga vídeo com 60s ou mais
    "legenda": True,
    "transcrever": True,
    "modo": "cortado",
    "topo_youtube": "thumb",
    "cortes_por_video_youtube": 2,
    "analisar_live_a_cada_min": 20,
    "max_cortes_por_live": 6,
    "qualidade_live": "720p,720p60,best",
    "apagar_gravacao_depois": True,
    "extensao_gravar_ao_abrir": True,   # abriu a live no Chrome → já começa a gravar
    "tendencias_auto": False,           # corta sozinho os vídeos mais em alta do YouTube
    "tendencias_por_dia": 2,
    "tendencias_nichos": ["podcast", "react", "entrevista", "live", "polêmica", "fofoca",
                          "futebol", "BBB", "treta", "humor"],
    "tendencias_periodo": "semana",
    "modo_madrugada": False,            # cortes automáticos só no horário abaixo (PC livre)
    "madrugada_inicio": "01:00",
    "madrugada_fim": "07:00",
    "desligar_pc_ao_terminar": False,   # no modo madrugada: desliga o PC quando acabar a fila
    "compilacao_auto": False,           # domingo à noite: compilação TOP 5 da semana
    "pasta_vigiada": "",                # vídeo colocado nessa pasta vira corte sozinho
    "nota_minima_live": 6,              # live automática: a IA dá nota; abaixo disso o corte é descartado
    "tempo_real": True,                 # live: detecta o momento na hora (a cada 30s) e já corta
    "sensibilidade": "media",           # baixa / media / alta  (canal:alta na lista muda só ele)
    "tempo_real_aprovar": False,        # pede sua aprovação na extensão antes de cortar
    "modo_diagnostico": False,          # anota cada pico na pasta 'diagnostico' pra calibrar
    "extensao_parar_sem_sinal_min": 10, # fechou a aba → para de gravar depois de X min
    "esperar_grafico_youtube_horas": 6,
    "max_minutos_video_sem_grafico": 120,
    "pegar_ultimo_video_ao_iniciar": False,
}

RISADA = re.compile(r"(k{3,}|KEKW|LUL|OMEGALUL|ICANT|LMAO|HAHA|rsrs|\?{2,}|!{3,}|CARALHO|"
                    r"MEU DEUS|NOOO|Pog|WTF|AAAA)", re.IGNORECASE)
MIN_MSGS_PICO = 12      # mínimo de "pontos" de chat em 15s pra considerar pico


# ============================================================
# Utilidades
# ============================================================
def log(msg):
    linha = f"[{datetime.now():%d/%m %H:%M:%S}] {msg}"
    print(linha, flush=True)
    try:
        with open(ARQ_LOG, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError:
        pass


def carregar_config():
    if not ARQ_CONFIG.exists():
        salvar_json(ARQ_CONFIG, PADRAO)
        log("Criei o canais.json — coloque seus canais lá e rode de novo.")
        sys.exit(0)
    cfg = dict(PADRAO)
    cfg.update(json.loads(ARQ_CONFIG.read_text(encoding="utf-8")))
    # "gaules:alta" na lista = sensibilidade só pra esse canal
    cfg["sensibilidade_canal"] = {}
    for plat in ("twitch", "kick"):
        nomes = []
        for c in cfg.get(plat, []):
            c = c.strip()
            if not c:
                continue
            nome, _, sens = c.partition(":") if not c.startswith("http") else (c, "", "")
            nome = nome.rstrip("/").split("/")[-1].lower()
            if sens.strip().lower() in detector.LIMIAR:
                cfg["sensibilidade_canal"][nome] = sens.strip().lower()
            nomes.append(nome)
        cfg[plat] = nomes
    cfg["youtube_lives"] = [c.strip().rstrip("/") for c in cfg.get("youtube_lives", []) if c.strip()]
    return cfg


def carregar_estado():
    if ARQ_ESTADO.exists():
        try:
            return json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"youtube": {}, "pendentes": {}}


def salvar_estado(estado):
    salvar_json(ARQ_ESTADO, estado)


def ytdlp_info(url, **extra):
    import yt_dlp
    import baixador
    opts = baixador.opcoes_ytdlp(skip_download=True, **extra)
    with yt_dlp.YoutubeDL(opts) as y:
        return y.extract_info(url, download=False)


# ============================================================
# TWITCH: chat (conexão anônima, não precisa de conta)
# ============================================================
class ChatTwitch(threading.Thread):
    def __init__(self, canal, arquivo: Path):
        super().__init__(daemon=True)
        self.canal, self.arquivo = canal, arquivo
        self.parar = threading.Event()

    def run(self):
        while not self.parar.is_set():
            try:
                s = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=60)
                s.sendall(f"NICK justinfan{random.randint(10000, 99999)}\r\n"
                          f"JOIN #{self.canal}\r\n".encode())
                buf = ""
                with open(self.arquivo, "a", encoding="utf-8") as f:
                    while not self.parar.is_set():
                        try:
                            dados = s.recv(8192).decode("utf-8", "ignore")
                        except socket.timeout:
                            s.sendall(b"PING :tmi.twitch.tv\r\n")
                            continue
                        if not dados:
                            break
                        buf += dados
                        *linhas, buf = buf.split("\r\n")
                        for l in linhas:
                            if l.startswith("PING"):
                                s.sendall(l.replace("PING", "PONG", 1).encode() + b"\r\n")
                                continue
                            m = re.match(r":(\w+)!\S+ PRIVMSG #\S+ :(.*)", l)
                            if m:
                                f.write(json.dumps({"t": round(time.time(), 2), "u": m[1],
                                                    "m": m[2]}, ensure_ascii=False) + "\n")
                                f.flush()
                s.close()
            except Exception:
                time.sleep(10)


def checar_lives(lista, simultaneas=4):
    """info_live de vários canais ao mesmo tempo (na ordem da lista)."""
    if not lista:
        return []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, min(simultaneas, len(lista)))) as pool:
        return list(pool.map(lambda c: info_live(c[1], c[3]), lista))


def info_live(canal, url=None):
    """Devolve os dados da live se estiver ao vivo, senão None. Funciona pra Twitch, Kick e YouTube."""
    url = url or f"https://www.twitch.tv/{canal}"
    try:
        r = subprocess.run([sys.executable, "-m", "streamlink", "--json", url], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=90)
        j = json.loads(r.stdout)
    except Exception:
        j = {"error": "falhou"}
    if j.get("streams") and not j.get("error"):
        return j.get("metadata") or {}
    if "No plugin" in str(j.get("error", "")):      # streamlink não conhece o site: tenta o yt-dlp
        try:
            info = ytdlp_info(url)
            if info.get("is_live") or info.get("live_status") == "is_live":
                return {"title": info.get("title", ""), "author": info.get("uploader", canal),
                        "_ytdlp": True}
        except Exception:
            pass
    return None


class GravacaoLive:
    def __init__(self, canal, meta, cfg, plataforma="twitch", url=None):
        self.canal, self.meta, self.plataforma = canal, meta, plataforma
        self.url = url or f"https://www.twitch.tv/{canal}"
        self.pasta = PASTA_GRAVACOES / f"{plataforma}_{canal}_{datetime.now():%Y%m%d_%H%M}"
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.video = self.pasta / "live.ts"
        self.chat = self.pasta / "chat.jsonl"
        self.analisado_ate = 0.0
        self.ultima_analise = time.time()
        self.cortes_feitos: list[float] = []
        self.desde = time.time()
        self.pela_extensao = False          # começou porque você abriu a live no Chrome
        self.ultimo_sinal = time.time()     # última vez que a aba da extensão "deu sinal"
        self.saida_log = open(self.pasta / "gravador.log", "w", encoding="utf-8")
        alt = 1080 if cortes.BAIXAR_1080 else 720
        qualidade = cfg["qualidade_live"]
        if cortes.BAIXAR_1080 and qualidade == "720p,720p60,best":
            qualidade = "1080p60,1080p,936p60,900p60,720p60,720p,best"
        if meta.get("_ytdlp"):
            cmd = [sys.executable, "-m", "yt_dlp", self.url, "-f", f"best[height<={alt}]/best",
                   "--hls-use-mpegts", "--no-part", "-o", str(self.video)]
        else:
            cmd = [sys.executable, "-m", "streamlink", "--retry-open", "3", self.url,
                   qualidade, "-o", str(self.video)]
            if plataforma == "twitch":
                cmd.insert(3, "--twitch-disable-ads")
        self.segmentada = bool(cortes.carregar_config().get('gravacao_segmentada', False))
        self.produtor = None
        if self.segmentada:
            from gravacao_segmentada import comando_ffmpeg
            cortes.checar_ffmpeg()
            if meta.get('_ytdlp'):
                cmd[-1] = '-'
            else:
                cmd = cmd[:-2] + ['-O']
            self.produtor = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=self.saida_log)
            try:
                self.proc = subprocess.Popen(comando_ffmpeg(self.pasta), stdin=self.produtor.stdout,
                                             stdout=self.saida_log, stderr=self.saida_log)
            except Exception:
                self.produtor.terminate(); self.produtor.wait(timeout=15)
                raise
            finally:
                self.produtor.stdout.close()
            self.video = self.pasta / 'live.m3u8'
        else:
            self.proc = subprocess.Popen(cmd, stdout=self.saida_log, stderr=subprocess.STDOUT)
        self.chat_thread = None
        self.termometro = detector.Termometro(
            canal, plataforma, cfg.get("sensibilidade_canal", {}).get(canal, cfg.get("sensibilidade", "media")),
            cfg.get("modo_diagnostico", False))
        self.ultimo_termometro = time.time()
        if plataforma == "twitch":
            self.chat_thread = ChatTwitch(canal, self.chat)
            self.chat_thread.start()
        log(f"🔴 {canal} ({plataforma}) está AO VIVO — gravando: {meta.get('title', '')}")

    def ativa(self):
        if self.segmentada:
            from gravacao_segmentada import snapshot
            try:
                snapshot(self.pasta)
            except OSError:
                pass
        return self.proc.poll() is None

    def tamanho(self):
        return sum(p.stat().st_size for p in self.pasta.glob('segmento_*.ts')) if self.segmentada else (self.video.stat().st_size if self.video.exists() else 0)

    def fim_relogio(self):
        """Hora (relógio) do último segundo gravado. No Windows a 'data de modificação' de um arquivo
        que ainda está sendo gravado NÃO atualiza — por isso, gravando, usa a hora de agora."""
        if self.segmentada and (self.pasta/'captura.m3u8').exists():
            return (self.pasta/'captura.m3u8').stat().st_mtime
        if self.ativa() or not self.video.exists():
            return time.time()
        return self.video.stat().st_mtime

    def parar(self):
        if self.produtor and self.produtor.poll() is None:
            self.produtor.terminate()
            try:
                self.produtor.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.produtor.kill(); self.produtor.wait(timeout=5)
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
        if self.ativa():
            self.proc.terminate()
            try:
                self.proc.wait(15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.chat_thread:
            self.chat_thread.parar.set()
        self.saida_log.close()


def adicionar(fila, tarefa, prioridade=None):
    """Coloca a tarefa na fila respeitando a prioridade (maior primeiro). Vídeo que cita um
    assunto em alta no Brasil passa na frente dos outros automáticos."""
    if prioridade is None:
        prioridade = tarefa.get("prioridade")
    if prioridade is None:
        titulo = (tarefa.get("meta") or {}).get("titulo") or (tarefa.get("base") or {}).get("meta", {}).get("titulo", "")
        prioridade = tendencias.prioridade_titulo(titulo)
    tarefa["prioridade"] = prioridade
    if isinstance(fila, FilaTarefas):
        fila.adicionar(tarefa)
        return
    i = 0
    for i, t in enumerate(list(fila)):
        if t.get("prioridade", 0) < prioridade:
            break
    else:
        i = len(fila)
    fila.insert(i, tarefa)


def analisar_por_audio(g: GravacaoLive, cfg, fila, final=False):
    """Kick/YouTube (sem chat): acha os momentos mais agitados do áudio e a IA escolhe."""
    if len(fila) >= int(cortes.carregar_config().get("max_tarefas_pendentes", 100)):
        return
    if not g.video.exists() or g.tamanho() < 1_000_000:
        return
    dur_total = cortes.duracao_video(g.video)
    t0, t1 = g.analisado_ate, dur_total - (0 if final else 15)
    restante = cfg["max_cortes_por_live"] - len(g.cortes_feitos)
    if t1 - t0 < 120 or restante <= 0:
        return
    dur = cfg["duracao_corte_seg"]
    meta = {"titulo": g.meta.get("title", ""), "canal": g.meta.get("author") or g.canal}
    quantidade = min(2, restante)
    base = {"tipo": "corte", "fonte": str(g.video), "topo": "frame", "pasta": g.canal, "meta": meta}
    adicionar(fila, {"_job_id": f"analise:{g.video}:{t0:.2f}:{t1:.2f}", "tipo": "analise_audio_live", "fonte": str(g.video), "inicio": t0, "fim": t1,
                     "quantidade": quantidade, "duracao": dur, "base": base,
                     "excluir_inicios": list(g.cortes_feitos)})
    g.analisado_ate = max(0.0, t1 - dur)
    # Reserva o limite antes de a análise assíncrona terminar.
    g.cortes_feitos.extend(t0 + i * 0.001 for i in range(quantidade))


def picos_chat(mensagens, t0, t1, dur, max_picos, ja_cortados, janela=15):
    """mensagens: lista de (segundo_no_video, texto). Devolve o segundo central de cada pico."""
    if max_picos <= 0 or t1 - t0 < janela * 4:
        return []
    n = int(t1 - t0) + 1
    pontos = [0.0] * n
    for seg, txt in mensagens:
        if t0 <= seg < t1:
            pontos[int(seg - t0)] += 2.0 if RISADA.search(txt) else 1.0
    soma = sum(pontos[:janela])
    janelas = [soma]
    for i in range(janela, n):
        soma += pontos[i] - pontos[i - janela]
        janelas.append(soma)
    # pico = pelo menos 2,5x o movimento normal do chat (mediana) — se adapta a chat grande ou pequeno
    limiar = max(statistics.median(janelas) * 2.5, MIN_MSGS_PICO)
    picos = []
    for i in sorted(range(len(janelas)), key=lambda k: -janelas[k]):
        if janelas[i] < limiar or len(picos) >= max_picos:
            break
        centro = t0 + i + janela / 2
        if all(abs(centro - p) >= dur for p in picos + ja_cortados):
            picos.append(centro)
    return picos


def analisar_gravacao(g: GravacaoLive, cfg, fila, final=False):
    if len(fila) >= int(cortes.carregar_config().get("max_tarefas_pendentes", 100)):
        return
    if not g.video.exists() or g.tamanho() < 1_000_000:
        return
    dur_total = cortes.duracao_video(g.video)
    if dur_total < 90:
        return
    inicio_real = g.fim_relogio() - dur_total             # relógio de quando a gravação começou
    mensagens = []
    if g.chat.exists():
        for linha in g.chat.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                m = json.loads(linha)
                mensagens.append((m["t"] - inicio_real, m["m"]))
            except (json.JSONDecodeError, KeyError):
                pass
    if not mensagens:
        log(f"   {g.canal}: sem mensagens no chat ainda.")
        return
    dur = cfg["duracao_corte_seg"]
    t1 = min(dur_total, mensagens[-1][0]) - (0 if final else 20)
    restante = cfg["max_cortes_por_live"] - len(g.cortes_feitos)
    picos = picos_chat(mensagens, g.analisado_ate, t1, dur, min(2 if not final else restante, restante),
                       g.cortes_feitos)
    g.analisado_ate = max(0.0, t1 - dur)
    if not picos:
        log(f"   {g.canal}: nenhum pico forte no chat nesse período.")
    for c in picos:
        ini = max(0.0, c - dur * 0.75)          # o chat reage alguns segundos DEPOIS do lance
        fim = min(dur_total - 1, ini + dur)
        amostra = [txt for seg, txt in mensagens if c - 15 <= seg <= c + 10][:40]
        g.cortes_feitos.append(c)
        log(f"   ✂ pico no chat de {g.canal} em {cortes.fmt_tempo(c)} → corte na fila")
        adicionar(fila, {"tipo": "corte", "fonte": str(g.video), "inicio": ini, "fim": fim,
                     "topo": "frame", "pasta": g.canal,
                     "meta": {"titulo": g.meta.get("title", ""),
                              "canal": g.meta.get("author") or g.canal},
                     "contexto": " | ".join(amostra)})


# ============================================================
# YOUTUBE
# ============================================================
def listar_videos(url, n=5):
    url = url.rstrip("/")
    if re.search(r"/(@[^/]+|channel/[^/]+|c/[^/]+)$", url):
        url += "/videos"
    info = ytdlp_info(url, extract_flat="in_playlist", playlistend=n)
    return [(e["id"], e.get("title", "")) for e in (info.get("entries") or []) if e.get("id")]


def verificar_youtube(url, cfg, estado):
    try:
        videos = listar_videos(url)
    except Exception as e:
        log(f"   ⚠ não consegui ler {url}: {str(e)[:150]}")
        return
    reg = estado["youtube"].setdefault(url, {"vistos": [], "iniciado": False})
    if not reg["iniciado"]:
        reg["iniciado"] = True
        reg["vistos"] = [v for v, _ in videos]
        if cfg["pegar_ultimo_video_ao_iniciar"] and videos:
            v, t = videos[0]
            estado["pendentes"][v] = {"desde": time.time(), "titulo": t}
        log(f"   YouTube {url}: começando a vigiar ({len(videos)} vídeos já existentes ignorados)")
        return
    for v, t in videos:
        if v not in reg["vistos"]:
            reg["vistos"].append(v)
            estado["pendentes"][v] = {"desde": time.time(), "titulo": t}
            log(f"🆕 vídeo novo: {t}")
    reg["vistos"] = reg["vistos"][-300:]


def picos_grafico(heatmap, duracao, dur, n):
    """Usa o gráfico 'mais repetidos' do YouTube. Devolve segundos de início."""
    if not heatmap or duracao < dur:
        return []
    valores = [0.0] * (int(duracao) + 1)
    for h in heatmap:
        for s in range(int(h["start_time"]), min(int(h["end_time"]) + 1, len(valores))):
            valores[s] = h.get("value", 0)
    soma = sum(valores[:dur])
    janelas = [soma]
    for s in range(1, len(valores) - dur + 1):
        soma += valores[s + dur - 1] - valores[s - 1]
        janelas.append(soma)
    ignorar = max(30, duracao * 0.03)       # o comecinho sempre é alto, não conta
    escolhidos = []
    for s in sorted(range(len(janelas)), key=lambda k: -janelas[k]):
        if len(escolhidos) >= n:
            break
        if s < ignorar:
            continue
        if all(abs(s - e) >= dur for e in escolhidos):
            escolhidos.append(s)
    return escolhidos


def verificar_clips_twitch(canal, cfg, estado, fila):
    """Os clips mais vistos das últimas 24h (o público já escolheu o melhor momento)."""
    reg = estado.setdefault("clips", {}).setdefault(canal, {"feitos": [], "ultima": 0})
    if time.time() - reg["ultima"] < 6 * 3600:
        return
    reg["ultima"] = time.time()
    try:
        info = ytdlp_info(f"https://www.twitch.tv/{canal}/clips?filter=clips&range=24hr",
                          extract_flat="in_playlist", playlistend=10)
    except Exception as e:
        log(f"   ⚠ não consegui ler os clips de {canal}: {str(e)[:120]}")
        return
    novos = 0
    for e in info.get("entries") or []:
        cid = e.get("id")
        if not cid or cid in reg["feitos"] or novos >= cfg["clips_por_dia"]:
            continue
        url = e.get("url") or e.get("webpage_url")
        dur = e.get("duration")
        if not dur:
            try:
                dur = ytdlp_info(url).get("duration") or 30
            except Exception:
                continue
        reg["feitos"].append(cid)
        novos += 1
        log(f"🎬 clip popular de {canal}: {e.get('title', '')[:60]}")
        adicionar(fila, {"_job_id": "twitch_clip:" + cid, "tipo": "corte", "fonte": url, "inicio": 0, "fim": float(dur), "topo": "frame",
                     "pasta": canal, "meta": {"titulo": e.get("title", ""), "canal": canal}})
    reg["feitos"] = reg["feitos"][-200:]


def processar_pendentes_youtube(cfg, estado, fila):
    dur = cfg["duracao_corte_seg"]
    for vid, p in list(estado["pendentes"].items()):
        url = f"https://www.youtube.com/watch?v={vid}"
        idade_h = (time.time() - p["desde"]) / 3600
        try:
            info = ytdlp_info(url)
        except Exception as e:
            if idade_h > 48:
                del estado["pendentes"][vid]
            log(f"   ⚠ não consegui abrir {p['titulo']}: {str(e)[:120]}")
            continue
        if info.get("live_status") in ("is_live", "is_upcoming", "post_live"):
            continue
        duracao = info.get("duration") or 0
        meta = {"titulo": info.get("title", ""), "canal": info.get("uploader", "")}
        base = {"tipo": "corte", "fonte": url, "topo": cfg["topo_youtube"],
                "pasta": info.get("uploader", "youtube"), "meta": meta}

        if duracao <= dur * 1.5:                       # vídeo curto: vira corte inteiro
            adicionar(fila, {**base, "inicio": 0, "fim": duracao})

        elif info.get("heatmap") or duracao / 60 <= cfg["max_minutos_video_sem_grafico"]:
            adicionar(fila, {"_job_id": "youtube:" + vid, "tipo": "yt_transcricao", "url": url, "base": base})
        elif idade_h < cfg["esperar_grafico_youtube_horas"]:
            continue
        else:
            log(f"   ⏭ {meta['titulo'][:60]}: excede o limite de análise configurado")
        del estado["pendentes"][vid]


# ============================================================
# Execução das tarefas
# ============================================================
def planejar_uma_vez(tarefa,fila,funcao):
    if not isinstance(fila,FilaTarefas) or not tarefa.get('_job_id'):return funcao()
    chave='plano:'+tarefa['_job_id']
    plano=fila.carregar_contexto(chave)
    if plano is None:
        plano=funcao()
        fila.salvar_contexto(chave,plano)
    return plano


def enfileirar_momentos(fila, tarefa, achados, base, prioridade=None):
    """Põe os momentos achados na fila. Com 'IA em lote' (padrão): UMA tarefa pra todos os cortes
    do vídeo = UMA chamada de IA. Cada corte ainda tem o seu código (não duplica se repetir)."""
    if not achados:
        return
    filhos = []
    for m in achados:
        job = f"{tarefa['_job_id']}:{m['inicio']}:{m['fim']}" if tarefa.get("_job_id") else None
        filhos.append(({**base, **({"_job_id": job} if job else {}),
                        "meta": {**base.get("meta", {}), "editorial": m.get("evidencias", {})},
                        "contexto": m.get("motivo", ""), "inicio": m["inicio"], "fim": m["fim"]}, job))
    extra = {} if prioridade is None else {"prioridade": prioridade}
    if len(filhos) >= 2 and cortes.carregar_config().get("ia_lote", True):
        lote = {**base, **extra, "tipo": "corte_lote",
                "momentos": [{k: f[k] for k in ("inicio", "fim", "contexto", "meta")} for f, _ in filhos],
                "jobs": [j for _, j in filhos]}
        if tarefa.get("_job_id"):
            lote["_job_id"] = "lote:" + tarefa["_job_id"]
        adicionar(fila, lote)
    else:
        for f, _ in filhos:
            adicionar(fila, {**f, **extra})


def _registrar_pronto(saida, tarefa):
    try:
        titulo = json.loads(saida.with_suffix(".json").read_text(encoding="utf-8")).get("titulo", "")
    except (OSError, json.JSONDecodeError):
        titulo = saida.stem
    ESTADO_PAINEL["prontos"] = (ESTADO_PAINEL["prontos"] + [{
        "id": saida.stem + str(int(time.time())), "arquivo": saida.name, "titulo": titulo,
        "canal": tarefa.get("pasta", ""), "quando": time.time()}])[-15:]


def executar(tarefa, cfg, fila):
    if isinstance(fila, FilaTarefas):
        fila.progresso(tarefa, "Preparando tarefa")
    try:
        if tarefa["tipo"] == "corte":
            log(f"✂ gerando corte: {tarefa['meta'].get('titulo', '')[:60]} "
                f"[{cortes.fmt_tempo(tarefa['inicio'])}]")
            sync=tarefa.get('sincronia')
            if sync and not sync.get('resultado'):
                from sincronia_live import alinhar
                resultado_sync=alinhar(tarefa['fonte'],sync['previsto'],sync.get('hash'))
                if resultado_sync.get('confirmado'):
                    deslocamento=resultado_sync['instante']-sync['previsto']
                    tarefa['inicio']=max(0,tarefa['inicio']+deslocamento)
                    tarefa['fim']+=deslocamento
                sync['resultado']=resultado_sync
                tarefa.setdefault('meta',{})['sincronia']=resultado_sync
                if isinstance(fila,FilaTarefas):fila.atualizar(tarefa)
            saida = cortes.gerar_corte(
                tarefa["fonte"], tarefa["inicio"], tarefa["fim"],
                _job_id=tarefa.get("_job_id"),
                _progresso=(lambda msg: fila.progresso(tarefa, msg)) if isinstance(fila, FilaTarefas) else None,
                automatico=not tarefa.get("manual") and tarefa.get("prioridade", 0) < 100 and not tarefa.get("_aprovado"),
                legenda=cfg["legenda"], transcrever_audio=cfg["transcrever"],
                modo=cfg["modo"], topo=tarefa.get("topo", "auto"),
                contexto=tarefa.get("contexto", ""), meta=tarefa.get("meta") or None,
                formato=tarefa.get("formato") or cortes.carregar_config().get("formato_corte", "curto"),
                refinar=bool(tarefa.get("refinar")), foco=tarefa.get("foco"),
                **({"nota_minima": float(cfg.get("nota_minima_live", 6) or 0)} if tarefa.get("auto") else {}),
                pasta_saida=PASTA_CORTES / cortes.nome_seguro(tarefa.get("pasta", "outros"), 40))
            log(f"✅ pronto: {saida.name}" if saida else "🗑 corte descartado (nota baixa)")
            if tarefa.get("id"):
                STATUS_MOMENTOS[tarefa["id"]] = "pronto" if saida else "nota baixa"
            if saida:
                _registrar_pronto(saida, tarefa)
        elif tarefa["tipo"] == "corte_lote":
            n = len(tarefa["momentos"])
            log(f"✂ gerando {n} cortes de uma vez (1 chamada de IA): {tarefa.get('meta', {}).get('titulo', '')[:50]}")
            saidas = cortes.gerar_cortes_lote(
                tarefa["fonte"], tarefa["momentos"], _job_ids=tarefa.get("jobs"),
                _progresso=(lambda msg: fila.progresso(tarefa, msg)) if isinstance(fila, FilaTarefas) else None,
                automatico=not tarefa.get("manual") and tarefa.get("prioridade", 0) < 100 and not tarefa.get("_aprovado"),
                legenda=cfg["legenda"], transcrever_audio=cfg["transcrever"], modo=cfg["modo"],
                topo=tarefa.get("topo", "auto"), meta=tarefa.get("meta") or None,
                formato=tarefa.get("formato") or cortes.carregar_config().get("formato_corte", "curto"),
                pasta_saida=PASTA_CORTES / cortes.nome_seguro(tarefa.get("pasta", "outros"), 40))
            for saida in saidas:
                if saida:
                    _registrar_pronto(Path(saida), tarefa)
            log(f"✅ {sum(1 for x in saidas if x)} de {n} cortes prontos")
        elif tarefa['tipo'] == 'analise_audio_live':
            achados = planejar_uma_vez(tarefa,fila,lambda: momentos.momentos_do_trecho(tarefa['fonte'], tarefa['inicio'], tarefa['fim'],
                                                  tarefa['quantidade'], tarefa['duracao'], tarefa['base']['meta'], log=log))
            achados = [m for m in achados
                       if not any(abs(m['inicio']-c) < tarefa['duracao'] for c in tarefa.get('excluir_inicios', []))]
            enfileirar_momentos(fila, tarefa, achados, tarefa['base'])
        elif tarefa["tipo"] == "yt_transcricao":
            achados = planejar_uma_vez(tarefa,fila,lambda: momentos.achar_momentos(tarefa["url"], cfg["cortes_por_video_youtube"],
                                                 cfg["duracao_corte_seg"], log=log)[0])
            enfileirar_momentos(fila, tarefa, achados, tarefa["base"], tarefa.get("prioridade", 0))
        elif tarefa["tipo"] == "compilacao":
            import compilacao
            compilacao.gerar_compilacao(log=log)
        elif tarefa["tipo"] == "apagar":
            shutil.rmtree(tarefa["pasta"], ignore_errors=True)
            log(f"🗑 gravação apagada pra liberar espaço: {Path(tarefa['pasta']).name}")
    except cortes.RevisaoNecessaria as e:
        if isinstance(fila, FilaTarefas):
            fila.aguardar_revisao(tarefa, str(e))
        if tarefa.get("id"):
            STATUS_MOMENTOS[tarefa["id"]] = "aguardando revisão"
        log(str(e))
    except Exception as e:
        log(f"❌ erro na tarefa ({tarefa['tipo']}): {str(e)[:300]}")
        if isinstance(fila, FilaTarefas):
            estado = fila.falhar(tarefa, e)
            if tarefa.get("id"):
                STATUS_MOMENTOS[tarefa["id"]] = "erro" if estado == "falhou" else "tentando novamente"
    else:
        if isinstance(fila, FilaTarefas):
            fila.concluir(tarefa)


# ============================================================
# PAINEL (localhost:8765) + botão "Cortar agora" da extensão do Chrome
# ============================================================
TOKEN_SESSAO = secrets.token_urlsafe(32)
# só a NOSSA extensão (o ID vem da "key" do manifest.json, igual em qualquer PC): outra extensão do Chrome
# não consegue pegar o token nem mandar comando
ID_EXTENSAO = "lcadmjbfbmmdpkpcengdielodgbkcngh"
ORIGEM_EXTENSAO = f"chrome-extension://{ID_EXTENSAO}"
MSG_ORIGEM = ("Origem não permitida. Se for a extensão do Cortes: em chrome://extensions remova ela e "
              "clique em 'Carregar sem compactação' de novo na pasta extensao_chrome.")
FILA_ATIVA = None
PORTA = 8765
COMANDOS: "queue.Queue[dict]" = queue.Queue()
ESTADO_PAINEL = {"gravando": {}, "lives": {}, "fila": 0, "prontos": []}
try:
    VERSAO_PROGRAMA = (Path(__file__).with_name("VERSAO.txt").read_text(encoding="utf-8").strip() or "?")
except OSError:
    VERSAO_PROGRAMA = "?"


def chave_live(canal, plat):
    return canal if plat == "twitch" else f"{plat}:{canal}"


def url_live(canal, plat):
    return f"https://kick.com/{canal}" if plat == "kick" else f"https://www.twitch.tv/{canal}"

PAINEL_HTML = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<title>Painel de Lives - Cortes 9:16</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--v:#d90f0f;--a:#ffd600;--f:#16161a;--c:#222228;--t:#f2f2f2;--g:#9a9aa5}
*{box-sizing:border-box}body{margin:0;background:var(--f);color:var(--t);font-family:Segoe UI,Arial,sans-serif}
header{background:var(--v);border-bottom:4px solid var(--a);padding:10px 16px;display:flex;justify-content:space-between;align-items:center}
header b{font-size:18px}#info{font-size:13px}
main{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:10px;height:calc(100vh - 56px)}
.slot{background:var(--c);border-radius:10px;display:flex;flex-direction:column;overflow:hidden;min-height:0}
.barra{display:flex;gap:6px;padding:6px;align-items:center}
.barra input{flex:1;background:#2e2e36;border:1px solid #3a3a44;color:var(--t);padding:6px 8px;border-radius:6px;font-size:14px}
button{border:0;border-radius:6px;padding:7px 10px;font-weight:700;cursor:pointer;color:#fff;background:#34343e}
button.cortar{background:var(--v)}button.cortar:active{transform:scale(.97)}
.player{flex:1;background:#000;min-height:0}.player iframe{width:100%;height:100%;border:0}
.st{font-size:12px;color:var(--g);padding:0 8px 6px}.rec{color:#ff4d4d;font-weight:700}
.vazio{display:flex;align-items:center;justify-content:center;height:100%;color:var(--g);font-size:14px;text-align:center;padding:20px}
</style></head><body>
<header><b>✂ PAINEL DE LIVES</b><span id="info">conectando ao monitor...</span></header>
<main id="grade"></main><section style="padding:16px"><h2>Tarefas do robô</h2><div id="tarefas"></div></section>
<script>
const fetchOriginal = window.fetch.bind(window);
window.fetch = (url, opcoes={}) => {
  const u = new URL(url, location.href);
  if (u.origin !== location.origin) return fetchOriginal(url, opcoes);
  const leitura = ["/status", "/sessao"].includes(u.pathname);
  return fetchOriginal(url, { ...opcoes, method: leitura ? "GET" : "POST",
    headers: { ...opcoes.headers, "X-Cortes-Token": "__TOKEN_SESSAO__" } });
};
const N=4, grade=document.getElementById('grade');
let salvos=[]; try{salvos=JSON.parse(localStorage.getItem('canais')||'[]')}catch(e){}
for(let i=0;i<N;i++){
  const d=document.createElement('div'); d.className='slot';
  d.innerHTML=`<div class="barra"><input placeholder="canal da twitch" value="${salvos[i]||''}">
   <button class="ver">Ver</button><button class="cortar">✂ CORTAR AGORA</button></div>
   <div class="player"><div class="vazio">Digite o nome do canal e clique em Ver.<br>Ou espere: canais que o monitor está gravando aparecem sozinhos.</div></div>
   <div class="st"></div>`;
  grade.appendChild(d);
  const inp=d.querySelector('input'), st=d.querySelector('.st');
  d.querySelector('.ver').onclick=()=>ver(d,inp.value.trim().toLowerCase());
  d.querySelector('.cortar').onclick=async()=>{
    const c=inp.value.trim().toLowerCase(); if(!c){st.textContent='Coloque o canal primeiro.';return}
    st.textContent='enviando...';
    try{const r=await (await fetch('/cortar?canal='+encodeURIComponent(c))).json(); st.textContent=r.msg}
    catch(e){st.textContent='Monitor desligado. Ligue ele na interface.'}
  };
  if(salvos[i]) ver(d,salvos[i]);
}
function ver(d,c){
  if(!c) return; d.dataset.canal=c;
  d.querySelector('.player').innerHTML=`<iframe allowfullscreen src="https://player.twitch.tv/?channel=${encodeURIComponent(c)}&parent=localhost&muted=true&autoplay=true"></iframe>`;
  const todos=[...document.querySelectorAll('.slot input')].map(x=>x.value.trim().toLowerCase());
  try{localStorage.setItem('canais',JSON.stringify(todos))}catch(e){}
}
async function status(){
  try{
    const s=await (await fetch('/status')).json();
    const jobs = document.getElementById('tarefas'); jobs.replaceChildren();
    for (const m of s.aprovacoes || []) {
      const linha = document.createElement('div'); linha.style.padding = '8px';
      const texto = document.createElement('span'); texto.textContent = `Aprovar momento de ${m.canal}: ${(m.motivos || []).join(', ')} `; linha.appendChild(texto);
      for (const acao of ['aprovar', 'descartar']) {
        const b = document.createElement('button'); b.textContent = acao;
        b.onclick = async () => { await fetch('/momento?' + new URLSearchParams({id:m.id, acao})); status(); };
        linha.appendChild(b);
      }
      jobs.appendChild(linha);
    }
    for (const t of s.historico_tarefas || []) {
      const linha = document.createElement('div'); linha.style.padding = '8px';
      const texto = document.createElement('span');
      texto.textContent = `${t.estado} · ${t.titulo || t.tipo} · ${t.tentativas} tentativa(s) ${t.etapa || ""} ${t.erro ? '· ' + t.erro : ''} `;
      linha.appendChild(texto);
      const acao = ['falhou','cancelado','revisao'].includes(t.estado) ? 'retomar' : t.estado === 'pendente' ? 'cancelar' : null;
      if (acao) { const b = document.createElement('button'); b.textContent = acao === 'retomar' ? (t.estado === 'revisao' ? 'Aprovar processamento' : 'Tentar novamente') : 'Cancelar';
        b.onclick = async () => { await fetch('/tarefa?' + new URLSearchParams({id:t.id, acao})); status(); }; linha.appendChild(b); }
      jobs.appendChild(linha);
    }
    const grav=Object.keys(s.gravando);
    document.getElementById('info').textContent=`🔴 gravando: ${grav.join(', ')||'nenhum'}  |  cortes na fila: ${s.fila}`;
    const slots=[...document.querySelectorAll('.slot')];
    for(const c of grav){
      if(slots.some(x=>x.dataset.canal===c)) continue;
      const livre=slots.find(x=>!x.dataset.canal); if(!livre) break;
      livre.querySelector('input').value=c; ver(livre,c);
    }
    for(const x of slots){
      const c=x.dataset.canal, g=s.gravando[c], st=x.querySelector('.st');
      if(c && g && !st.dataset.fixo) st.innerHTML=`<span class="rec">● gravando</span> — ${g.cortes} corte(s) automático(s) até agora`;
    }
  }catch(e){document.getElementById('info').textContent='⚠ monitor desligado'}
}
status(); setInterval(status,10000);
</script></body></html>"""


MINI_HTML = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<title>Live - Cortes 9:16</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--v:#d90f0f;--a:#ffd600;--f:#111114;--c:#1f1f25;--t:#f2f2f2;--g:#9a9aa5}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--f);color:var(--t);font-family:Segoe UI,Arial,sans-serif;display:flex;flex-direction:column;font-size:13px}
#abas{display:flex;gap:4px;padding:5px;background:var(--c);overflow-x:auto}
#abas button{border:0;border-radius:5px;padding:4px 8px;background:#34343e;color:#fff;cursor:pointer;white-space:nowrap;font-size:12px}
#abas button.on{background:var(--v)}
#player{flex:1;background:#000;min-height:0;position:relative}#player iframe{width:100%;height:100%;border:0}
.vazio{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;color:var(--g);padding:16px}
#info{padding:6px 8px;background:var(--c)}
#calor{height:6px;background:#2e2e36;border-radius:3px;overflow:hidden;margin:4px 0}#calor div{height:100%;background:linear-gradient(90deg,#ffd600,#d90f0f);width:0}
#linha{display:flex;gap:6px;align-items:center;justify-content:space-between}
#cortar{border:0;border-radius:5px;padding:5px 9px;font-weight:700;background:var(--v);color:#fff;cursor:pointer}
#momentos{color:var(--g);font-size:12px;margin-top:3px;max-height:48px;overflow:auto}
</style></head><body>
<div id="abas"></div><div id="player"><div class="vazio">Esperando um canal entrar ao vivo...<br>O robô está vigiando os canais da aba Automático.</div></div>
<div id="info"><div id="linha"><span id="txt">conectando ao robô...</span><button id="cortar" hidden>✂ CORTAR AGORA</button></div>
<div id="calor"><div></div></div><div id="momentos"></div></div>
<script>
const fetchOriginal = window.fetch.bind(window);
window.fetch = (url, opcoes={}) => fetchOriginal(url, { ...opcoes, method: new URL(url, location.href).pathname === "/status" ? "GET" : "POST",
  headers: { ...opcoes.headers, "X-Cortes-Token": "__TOKEN_SESSAO__" } });
const q = new URLSearchParams(location.search);
let fixo = q.get("canal") ? {canal: q.get("canal").toLowerCase(), plataforma: q.get("plat") || "twitch", chave: "fixo"} : null;
let atual = null, mostrado = "";
function src(l){
  const c = encodeURIComponent(l.canal);
  if (l.plataforma === "kick") return `https://player.kick.com/${c}?autoplay=true&muted=true`;
  if (l.plataforma === "youtube") return l.video_id ? `https://www.youtube.com/embed/${encodeURIComponent(l.video_id)}?autoplay=1&mute=1` : "";
  return `https://player.twitch.tv/?channel=${c}&parent=${location.hostname}&muted=true&autoplay=true`;
}
function mostrar(l){
  atual = l; const u = src(l), pl = document.getElementById("player");
  if (u === mostrado) return; mostrado = u;
  pl.replaceChildren();
  if (!u) { const d = document.createElement("div"); d.className = "vazio";
    d.textContent = "Essa live do YouTube não deixa assistir aqui. O robô continua gravando e cortando normalmente."; pl.appendChild(d); return; }
  const f = document.createElement("iframe"); f.src = u; f.allow = "autoplay; fullscreen"; f.allowFullscreen = true; pl.appendChild(f);
}
document.getElementById("cortar").onclick = async () => {
  if (!atual) return; const t = document.getElementById("txt"); t.textContent = "enviando...";
  try { const r = await (await fetch("/cortar?" + new URLSearchParams({canal: atual.canal, plat: atual.plataforma}))).json(); t.textContent = r.msg; }
  catch (e) { t.textContent = "O robô está desligado."; }
};
async function status(){
  let s; try { s = await (await fetch("/status")).json(); } catch (e) { document.getElementById("txt").textContent = "⚠ robô desligado"; return; }
  const lives = Object.entries(s.lives || {}).map(([chave, l]) => ({...l, chave}));
  if (fixo && !lives.some(l => l.canal === fixo.canal)) lives.unshift(fixo);
  const abas = document.getElementById("abas"); abas.replaceChildren();
  if (!atual || !lives.some(l => l.chave === atual.chave)) atual = lives.find(l => fixo && l.canal === fixo.canal) || lives[0] || null;
  for (const l of lives) {
    const b = document.createElement("button"); b.textContent = (l.desde ? "🔴 " : "") + l.canal;
    if (atual && l.chave === atual.chave) b.className = "on"; b.onclick = () => { atual = l; status(); }; abas.appendChild(b);
  }
  abas.hidden = lives.length < 2;
  if (!atual) return;
  mostrar(atual);
  const l = lives.find(x => x.chave === atual.chave) || atual, min = l.desde ? Math.round((Date.now()/1000 - l.desde) / 60) : 0;
  document.getElementById("txt").textContent = l.desde ? `🔴 gravando há ${min} min · ${l.cortes} corte(s) · calor ${Math.round(l.calor || 0)}%` : `👀 assistindo ${l.canal} — o robô corta quando ele estiver nos canais vigiados`;
  document.getElementById("cortar").hidden = !l.desde || l.plataforma === "youtube";
  document.querySelector("#calor div").style.width = Math.min(100, l.calor || 0) + "%";
  document.getElementById("momentos").textContent = (l.momentos || []).slice(-3).reverse().map(m => `${m.hora} nota ${m.nota}: ${(m.motivos || []).join(", ")} ${m.status ? "(" + m.status + ")" : ""}`).join("  ·  ");
}
status(); setInterval(status, 5000);
</script></body></html>"""


class Painel(BaseHTTPRequestHandler):
    def _origem_permitida(self):
        host = self.headers.get('Host', '')
        origem = self.headers.get('Origin', '')
        return (host in (f'localhost:{PORTA}', f'127.0.0.1:{PORTA}') and
                (not origem or origem in (f'http://localhost:{PORTA}', f'http://127.0.0.1:{PORTA}') or
                 origem == ORIGEM_EXTENSAO))

    def _autorizado(self):
        return self._origem_permitida() and secrets.compare_digest(self.headers.get('X-Cortes-Token', ''), TOKEN_SESSAO)

    def log_message(self, *a):
        pass

    def _enviar(self, codigo, corpo, tipo="application/json"):
        dados = corpo.encode("utf-8") if isinstance(corpo, str) else corpo
        self.send_response(codigo)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        origem = self.headers.get('Origin')
        if origem and self._origem_permitida():
            self.send_header("Access-Control-Allow-Origin", origem)
            self.send_header('Vary', 'Origin')
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_OPTIONS(self):
        if not self._origem_permitida():
            return self._enviar(403, json.dumps({"ok": False, "msg": MSG_ORIGEM}))
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.headers.get('Origin', f'http://localhost:{PORTA}'))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Cortes-Token")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def _comando(self, dados):
        if COMANDOS.qsize() >= 500:
            return self._enviar(429, '{"ok":false,"msg":"Muitos pedidos. Aguarde o monitor."}')
        dados["resposta"] = queue.Queue()
        COMANDOS.put(dados)
        try:
            retorno = dados["resposta"].get(timeout=100)
        except queue.Empty:
            retorno = {"ok": False, "msg": "Confirmação pendente. Consulte o painel antes de repetir."}
        return self._enviar(200, json.dumps(retorno, ensure_ascii=False))

    def do_POST(self):
        if not self._autorizado():
            # lê (e joga fora) o corpo antes de recusar: fechar com dado não lido faz o Windows
            # derrubar a conexão (WinError 10053) e quem pediu nem via a mensagem
            try:
                self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 2_000_000))
            except (ValueError, OSError):
                pass
            return self._enviar(403, '{"ok":false,"msg":"Sessão inválida. Reconecte a extensão."}')
        self._post_autorizado = True
        url = urlparse(self.path)
        if url.path == '/tarefa':
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if FILA_ATIVA is None:
                return self._enviar(503, '{"ok":false}')
            acao, ident = q.get('acao'), q.get('id', '')
            ok = FILA_ATIVA.retomar(ident) if acao == 'retomar' else FILA_ATIVA.cancelar(ident) if acao == 'cancelar' else False
            return self._enviar(200, json.dumps(dict(ok=ok, msg='Atualizado.' if ok else 'Tarefa não disponível para essa ação.')))
        if url.path == "/bot":                        # bot da extensão (pergunta pra IA, só sugere ações)
            try:
                tam = int(self.headers.get("Content-Length") or 0)
                if not 0 < tam <= 300_000:
                    return self._enviar(413, '{"ok":false,"msg":"Pedido grande demais."}')
                pedido = json.loads(self.rfile.read(tam).decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                return self._enviar(400, '{"ok":false,"msg":"Pedido inválido."}')
            import bot
            return self._enviar(200, json.dumps(bot.responder(pedido), ensure_ascii=False))
        if url.path == "/ia_momentos":                # 🤖 IA corta os melhores momentos (YouTube)
            try:
                tam = int(self.headers.get("Content-Length") or 0)
                if not 0 < tam <= 200_000:
                    return self._enviar(413, '{"ok":false,"msg":"Pedido grande demais."}')
                pedido = json.loads(self.rfile.read(tam).decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                return self._enviar(400, '{"ok":false,"msg":"Pedido inválido."}')
            import ia_youtube
            try:
                trabalho = ia_youtube.iniciar(pedido, enfileirar_cortes_ia)
            except ValueError as e:
                return self._enviar(200, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))
            log(f"🤖 IA escolhendo {trabalho['n']} momento(s) de {trabalho['url'][:60]} (pedido da extensão)")
            return self._enviar(200, json.dumps({"ok": True, "trabalho": trabalho}, ensure_ascii=False))
        if url.path == "/instagram":                  # 📥 reels de um perfil (links juntados pela extensão)
            try:
                tam = int(self.headers.get("Content-Length") or 0)
                if not 0 < tam <= 500_000:
                    return self._enviar(413, '{"ok":false,"msg":"Pedido grande demais."}')
                pedido = json.loads(self.rfile.read(tam).decode("utf-8"))
                if not isinstance(pedido, dict):
                    raise ValueError
            except (ValueError, json.JSONDecodeError):
                return self._enviar(400, '{"ok":false,"msg":"Pedido inválido."}')
            import instagram
            if pedido.get("parar"):
                return self._enviar(200, json.dumps({"ok": instagram.parar(str(pedido["parar"])[:20])}))
            try:
                trabalho = instagram.iniciar(pedido.get("usuario"), [str(x)[:200] for x in (pedido.get("links") or [])[:500]])
            except ValueError as e:
                return self._enviar(200, json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))
            log(f"📥 baixando {trabalho['total']} reel(s) de @{trabalho['usuario']} (pedido da extensão)")
            return self._enviar(200, json.dumps({"ok": True, "trabalho": trabalho}, ensure_ascii=False))
        if url.path == "/chat":                       # mensagens do chat lidas pela extensão
            try:
                tam = int(self.headers.get("Content-Length") or 0)
                if not 0 < tam <= 2_000_000:
                    return self._enviar(413, '{"ok":false,"msg":"Lote de chat inválido."}')
                dados = json.loads(self.rfile.read(tam).decode("utf-8"))
                if not isinstance(dados, dict) or not isinstance(dados.get("msgs", []), list):
                    raise ValueError("Lote inválido")
            except (ValueError, json.JSONDecodeError):
                return self._enviar(400, json.dumps({"ok": False}))
            canal = re.sub(r"[^a-z0-9_]", "", str(dados.get("canal", "")).lower())
            plat = dados.get("plat") if dados.get("plat") in ("twitch", "kick") else "twitch"
            msgs = [m for m in dados.get("msgs", []) if isinstance(m, dict)][:500]
            if canal and msgs:
                COMANDOS.put({"acao": "chat", "canal": canal, "plat": plat, "msgs": msgs,
                              "resposta": queue.Queue()})
            return self._enviar(200, json.dumps({"ok": True}))
        self.do_GET()

    def do_GET(self):
        if not self._origem_permitida():
            return self._enviar(403, json.dumps({"ok": False, "msg": MSG_ORIGEM}))
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path in ("/", "/painel"):
            return self._enviar(200, PAINEL_HTML.replace('__TOKEN_SESSAO__', TOKEN_SESSAO), "text/html")
        if url.path == "/mini":                     # janelinha da live (aba Automático)
            return self._enviar(200, MINI_HTML.replace('__TOKEN_SESSAO__', TOKEN_SESSAO), "text/html")
        if url.path == '/sessao':
            return self._enviar(200, json.dumps(dict(token=TOKEN_SESSAO)))
        if url.path == "/status":
            import bot
            import ia_youtube
            return self._enviar(200, json.dumps(dict(ESTADO_PAINEL, agora=time.time(), ia=bot.status_ia(),
                                                     versao=VERSAO_PROGRAMA, ia_momentos=ia_youtube.resumo(),
                                                     instagram=__import__("instagram").resumo()),
                                                ensure_ascii=False))
        if not getattr(self, '_post_autorizado', False):
            return self._enviar(405, '{"ok":false,"msg":"Use POST com a sessão do programa."}')
        if url.path == "/gerar":
            link = q.get("url", "")
            try:
                ini, fim = float(q.get("ini", "")), float(q.get("fim", ""))
            except ValueError:
                return self._enviar(400, json.dumps({"ok": False, "msg": "Marque início e fim."}))
            if not re.match(r"^https://(www\.|m\.)?(youtube\.com|youtu\.be|twitch\.tv|kick\.com)/", link):
                return self._enviar(400, json.dumps({"ok": False, "msg": "Link não suportado."}))
            if not (math.isfinite(ini) and math.isfinite(fim)) or ini < 0 or not 5 <= fim - ini <= 180:
                return self._enviar(400, json.dumps({"ok": False, "msg": "O corte precisa ter entre 5s e 3min."}))
            return self._comando({"acao": "gerar", "url": link, "ini": ini, "fim": fim})
        if url.path == "/nota":
            return self._comando({"acao": "nota", "id": q.get("id", "")[:80], "texto": q.get("texto", "")[:300]})
        if url.path == "/momento":
            return self._comando({"acao": "momento", "id": q.get("id", "")[:80], "decisao": q.get("acao", "")})
        if url.path in ("/cortar", "/gravar"):
            canal = re.sub(r"[^a-z0-9_]", "", q.get("canal", "").lower())
            if not canal:
                return self._enviar(400, json.dumps({"ok": False, "msg": "Canal inválido."}))

            def numero(nome, padrao, minimo, maximo):
                try:
                    valor = float(q.get(nome, padrao))
                    return max(minimo, min(maximo, valor)) if math.isfinite(valor) else padrao
                except ValueError:
                    return padrao
            import uuid
            cmd = {"acao": url.path[1:], "canal": canal,
                   "plat": q.get("plat") if q.get("plat") in ("twitch", "kick") else "twitch",
                   "auto": q.get("auto") == "1", "antes": numero("antes", 50, 5, 180),
                   "depois": numero("depois", 10, 0, 30), "nota": q.get("nota", "")[:300],
                   "chat": q.get("chat", "")[:800], "atraso": numero("atraso", 0, 0, 36000),
                   "ajuste_sync": numero("ajuste_sync",0,-60,60),
                   "capturado_em": numero("capturado_em",time.time(),0,1e12),
                   "frame_hash": q.get("frame_hash", "")[:16] if re.fullmatch(r"[a-fA-F0-9]{16}", q.get("frame_hash", "")) else "", "id": uuid.uuid4().hex[:10],
                   "espectadores": numero("espectadores", 0, 0, 10_000_000),
                   "resposta": queue.Queue()}
            COMANDOS.put(cmd)
            try:
                r = cmd["resposta"].get(timeout=100)
            except queue.Empty:
                r = {"ok": False, "msg": "O monitor demorou pra responder. Tente de novo."}
            return self._enviar(200, json.dumps(r, ensure_ascii=False))
        self._enviar(404, json.dumps({"ok": False}))


def enfileirar_cortes_ia(itens, espera=100):
    """Os momentos que a IA escolheu (ia_youtube.py) entram na fila do monitor como cortes."""
    cmd = {"acao": "ia_lote", "itens": list(itens), "resposta": queue.Queue()}
    COMANDOS.put(cmd)
    try:
        return cmd["resposta"].get(timeout=espera)
    except queue.Empty:
        return {"ok": False, "msg": "O monitor demorou pra responder."}


def iniciar_painel():
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORTA), Painel)
    except OSError:
        log(f"⚠ Não consegui abrir o painel na porta {PORTA} (já tem outro monitor aberto?)")
        return False
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"🖥 Painel das lives: http://localhost:{PORTA}  (a extensão do Chrome também usa ele)")
    return True


def tratar_comandos(gravacoes, cfg, agendados, fila_manual=None, fila=None):
    fila_manual = fila_manual if fila_manual is not None else []
    fila = fila if fila is not None else []
    while True:
        try:
            cmd = COMANDOS.get_nowait()
        except queue.Empty:
            return
        acao, resp = cmd["acao"], cmd["resposta"]
        if acao == "ia_lote":                         # momentos escolhidos pela IA (extensão do YouTube)
            for it in cmd["itens"]:
                adicionar(fila, {"manual": True, "prioridade": 90, "tipo": "corte", "fonte": it["url"],
                                 "inicio": it["inicio"], "fim": it["fim"], "topo": "auto", "pasta": "manual",
                                 "meta": {}, "contexto": f"Momento escolhido pela IA: {it.get('motivo', '')}"[:300]})
            resp.put({"ok": True, "msg": f"{len(cmd['itens'])} corte(s) na fila."})
            log(f"🤖 {len(cmd['itens'])} momento(s) escolhidos pela IA foram pra fila.")
            continue
        if acao == "gerar":
            adicionar(fila, {"manual": True, "prioridade": 100, "tipo": "corte", "fonte": cmd["url"], "inicio": cmd["ini"],
                                "fim": cmd["fim"], "topo": "auto", "pasta": "manual",
                                "meta": {}, "contexto": "Trecho escolhido pelo usuário."})
            resp.put({"ok": True, "msg": "Corte salvo na fila."})
            log(f"✂ corte pedido pela extensão: {cmd['url'][:60]} ({cmd['ini']:.0f}s → {cmd['fim']:.0f}s)")
            continue
        if acao == "momento":
            mid = cmd["id"]
            aplicado = False
            if cmd["decisao"] == "aprovar" and mid in PENDENTES_APROVACAO:
                agendados.append(PENDENTES_APROVACAO.pop(mid))
                STATUS_MOMENTOS[mid] = "na fila"
                log("✅ momento aprovado na extensão")
                aplicado = True
            elif cmd["decisao"] == "descartar" and STATUS_MOMENTOS.get(mid) in ("aguardando", "na fila"):
                aplicado = PENDENTES_APROVACAO.pop(mid, None) is not None
                for lista in (agendados, fila):
                    for item in list(lista):
                        if item.get('id') == mid:
                            if isinstance(lista, FilaTarefas):
                                aplicado = lista.cancelar(item['_job_id']) or aplicado
                            else:
                                try:
                                    lista.remove(item); aplicado = True
                                except ValueError:
                                    pass
                if aplicado:
                    STATUS_MOMENTOS[mid] = 'descartado'
                    log('Momento descartado na extensão')
            if isinstance(fila, FilaTarefas):
                fila.salvar_contexto("agenda", {"agendados": agendados, "aprovacoes": PENDENTES_APROVACAO, "status": STATUS_MOMENTOS})
            resp.put({"ok": aplicado, "msg": "Decisão aplicada." if aplicado else "Momento não está mais disponível."})
            continue
        if acao == "nota":
            texto = cmd["texto"].strip()
            aplicado = False
            for item in agendados:
                if item.get("id") == cmd["id"]:
                    item["nota"] = texto
                    aplicado = True
                    break
            else:
                for item in fila:
                    if item.get("id") == cmd["id"]:
                        item["contexto"] = f"O que aconteceu (segundo o usuário): {texto}. " + item.get("contexto", "")
                        if isinstance(fila, FilaTarefas):
                            fila.atualizar(item)
                        aplicado = True
                        break
            if isinstance(fila, FilaTarefas):
                fila.salvar_contexto("agenda", {"agendados": agendados, "aprovacoes": PENDENTES_APROVACAO, "status": STATUS_MOMENTOS})
            resp.put({"ok": aplicado, "msg": "Nota aplicada." if aplicado else "O corte já começou ou não foi encontrado."})
            continue

        canal, plat = cmd["canal"], cmd.get("plat", "twitch")
        chave = chave_live(canal, plat)
        g = gravacoes.get(chave)

        if acao == "chat":                       # Kick: o chat vem da extensão (Twitch já vem do IRC)
            if g and g.plataforma != "twitch":
                try:
                    with open(g.chat, "a", encoding="utf-8") as f:
                        for m in cmd["msgs"]:
                            f.write(json.dumps({"t": float(m.get("t", time.time())), "u": str(m.get("u", ""))[:40],
                                                "m": str(m.get("m", ""))[:300]}, ensure_ascii=False) + "\n")
                except (OSError, ValueError):
                    pass
            continue

        if g is None:
            if acao == "gravar" and cmd.get("auto") and not cfg.get("extensao_gravar_ao_abrir", True):
                resp.put({"ok": False, "msg": "Gravar ao abrir está desligado.", "gravando": False})
                continue
            if '_meta' not in cmd:
                def descobrir(cmd=cmd, canal=canal, plat=plat):
                    try:
                        meta = info_live(canal, url_live(canal, plat))
                        COMANDOS.put(dict(cmd, _meta=meta))
                    except Exception as e:
                        cmd['resposta'].put({'ok': False, 'msg': str(e)[:200]})
                threading.Thread(target=descobrir, daemon=True).start()
                continue
            meta = cmd['_meta']
            if meta is None:
                resp.put({"ok": False, "msg": f"{canal} não está ao vivo agora.", "gravando": False})
                continue
            g = GravacaoLive(canal, meta, cfg, plat, url_live(canal, plat))
            g.pela_extensao = canal not in cfg.get(plat, [])
            gravacoes[chave] = g
            if acao == "gravar":
                resp.put({"ok": True, "gravando": True,
                          "msg": f"🔴 Gravando {canal}. Quando rolar algo bom, é só clicar em CORTAR."})
            else:
                resp.put({"ok": True, "gravando": True,
                          "msg": f"Comecei a gravar {canal} agora — esse lance já tinha passado. "
                                 f"Deixe a aba aberta que os próximos cortes funcionam."})
            continue

        g.ultimo_sinal = time.time()
        if cmd.get("espectadores"):
            g.termometro.espectador(cmd["espectadores"])
        if acao == "gravar":
            resp.put({"ok": True, "gravando": True, "msg": f"🔴 Gravando {canal}."})
            continue
        pos = cortes.duracao_video(g.video) if g.video.exists() else 0
        if pos < 15:
            resp.put({"ok": False, "msg": "A gravação acabou de começar, espere uns segundos."})
            continue
        atraso_captura = max(0, time.time() - g.fim_relogio()) if g.segmentada else 0
        from sincronia_live import posicao
        try:
            pos = posicao(pos,cmd.get('atraso',0),atraso_captura,cmd.get('ajuste_sync',0),cmd.get('capturado_em'),time.time())
        except ValueError as e:
            resp.put({'ok':False,'msg':str(e)});continue
        antes, depois = cmd["antes"], cmd["depois"]
        agendados.append({"id": cmd["id"], "fonte": str(g.video), "pasta": g.canal,
                          "meta": {"titulo": g.meta.get("title", ""), "canal": g.canal}, "chave": chave, "ini": max(0.0, pos - antes),
                          "alvo": pos + depois, "sincronia": {"previsto":pos,"hash":cmd.get("frame_hash","")}, "nota": cmd.get("nota", ""), "chat": cmd.get("chat", ""),
                          # espera a reação acontecer e dá tempo de você mandar a nota
                          "quando": time.time() + max(depois + 2, 25)})
        if isinstance(fila, FilaTarefas):
            fila.salvar_contexto("agenda", {"agendados": agendados, "aprovacoes": PENDENTES_APROVACAO, "status": STATUS_MOMENTOS})
        g.cortes_feitos.append(pos)
        log(f"✂ CORTE MANUAL em {canal} ({cortes.fmt_tempo(pos)}, {antes:.0f}s antes + {depois:.0f}s depois)")
        resp.put({"ok": True, "id": cmd["id"],
                  "msg": f"✂ Corte marcado em {cortes.fmt_tempo(pos)}! Fica pronto em alguns minutos."})


def processar_agendados(gravacoes, cfg, agendados, fila):
    for ag in list(agendados):
        if time.time() < ag["quando"]:
            continue
        agendados.remove(ag)
        g = gravacoes.get(ag.get("chave", ag.get("canal")))
        fonte = g.video if g else Path(ag.get("fonte", ""))
        if not fonte.is_file():
            STATUS_MOMENTOS[ag["id"]] = "erro: gravação não encontrada"
            continue
        dur_total = cortes.duracao_video(fonte)
        fim = min(dur_total - 1, ag["alvo"])
        ini = ag.get("ini", max(0.0, fim - cfg.get("duracao_corte_seg", 60)))
        contexto = ("Momento detectado automaticamente na live (" + ", ".join(ag.get("motivos", [])) + ")."
                    if ag.get("auto") else "Corte pedido pelo usuário: é um momento importante.")
        if ag.get("nota"):
            contexto += f" O que aconteceu (segundo o usuário): {ag['nota']}."
        if ag.get("chat"):
            contexto += f" Chat nesse momento: {ag['chat']}"
        adicionar(fila, prioridade=ag.get("prioridade", 100), tarefa={"tipo": "corte", "fonte": str(fonte), "inicio": ini, "fim": fim,
                        "_job_id": "momento:" + ag["id"], "sincronia":ag.get("sincronia"),
                        "refinar": bool(ag.get("refinar")), "foco": ag.get("foco"), "auto": bool(ag.get("auto")),
                        "topo": "frame", "pasta": g.canal if g else ag.get("pasta", "recuperados"), "id": ag.get("id"),
                        "meta": ({"titulo": g.meta.get("title", ""),
                                  "canal": g.meta.get("author") or g.canal} if g else ag.get("meta", {})),
                        "contexto": contexto})


STATUS_MOMENTOS: dict[str, str] = {}      # id do momento → detectado / aguardando / na fila / pronto / descartado
PENDENTES_APROVACAO: dict[str, dict] = {}  # momentos esperando você aprovar na extensão


INTERVALO_TEMPO_REAL = 30


def tempo_real(g, cfg, agendados):
    """Roda a cada ~30s por live: lê o chat/áudio novos e agenda o corte de cada momento detectado."""
    if time.time() - g.ultimo_termometro < INTERVALO_TEMPO_REAL:
        return
    g.ultimo_termometro = time.time()
    tm = g.termometro
    tm.sensibilidade = cfg.get("sensibilidade_canal", {}).get(g.canal, cfg.get("sensibilidade", "media"))
    tm.diagnostico = cfg.get("modo_diagnostico", False)
    tm.ler_chat(g.chat)
    if g.video.exists() and g.tamanho() > 2_000_000:
        if not getattr(g, '_audio_lendo', False):
            g._audio_lendo = True
            def ler_audio():
                try:
                    tm.ler_audio(g.video, fim=g.fim_relogio())
                finally:
                    g._audio_lendo = False
            threading.Thread(target=ler_audio, daemon=True).start()
    for mom in tm.avaliar():
        if FILA_ATIVA is not None and len(FILA_ATIVA) >= int(cortes.carregar_config().get("max_tarefas_pendentes", 100)):
            mom["status"] = "fila cheia"
            continue
        if len(g.cortes_feitos) >= cfg["max_cortes_por_live"]:
            log(f"   (momento em {g.canal} ignorado: já tem {cfg['max_cortes_por_live']} cortes nessa live)")
            mom["status"] = "limite"
            continue
        dur_total = cortes.duracao_video(g.video) if g.video.exists() else 0
        inicio_real = g.fim_relogio() - dur_total if dur_total else 0
        pos = mom["t_ini"] - inicio_real              # onde o chat começou a reagir, na gravação
        if pos < 20:
            continue
        dur = cfg["duracao_corte_seg"]
        # trecho LARGO em volta do lance (história antes + reação depois); a IA escolhe o pedaço exato
        # na mesma chamada que já faz a pergunta/legenda — sem IA a mais. Sem IA: corta pelas pausas.
        antes, depois = max(75.0, dur * 1.15), max(30.0, dur * 0.5)
        ini_l = max(0.0, pos - antes)
        ag = {"id": mom["id"], "fonte": str(g.video), "pasta": g.canal,
              "meta": {"titulo": g.meta.get("title", ""), "canal": g.canal}, "chave": chave_live(g.canal, g.plataforma),
              "ini": ini_l, "alvo": pos + depois, "refinar": True, "foco": round(pos - ini_l, 2),
              "chat": mom.get("chat", ""), "auto": True, "prioridade": 90,
              "motivos": mom["motivos"], "quando": time.time() + depois + 8}
        g.cortes_feitos.append(pos)
        log(f"⚡ MOMENTO em {g.canal} às {mom['hora']} (nota {mom['nota']:g}): {', '.join(mom['motivos'])}")
        if cfg.get("tempo_real_aprovar"):
            ag["expira"] = time.time() + 600
            PENDENTES_APROVACAO[mom["id"]] = ag
            STATUS_MOMENTOS[mom["id"]] = "aguardando"
            log("   aguardando sua aprovação na extensão (10 min)")
        else:
            agendados.append(ag)
            STATUS_MOMENTOS[mom["id"]] = "na fila"

    if FILA_ATIVA is not None:
        FILA_ATIVA.salvar_contexto('agenda', {'agendados':agendados, 'aprovacoes':PENDENTES_APROVACAO, 'status':STATUS_MOMENTOS})


def expirar_pendentes():
    for mid, ag in list(PENDENTES_APROVACAO.items()):
        if time.time() > ag.get("expira", 0):
            PENDENTES_APROVACAO.pop(mid, None)
            STATUS_MOMENTOS[mid] = "expirou"


def atualizar_estado(gravacoes, fila, ocupado):
    ESTADO_PAINEL["aprovacoes"] = [{"id":mid, "canal":ag.get("pasta", ""), "motivos":ag.get("motivos", [])} for mid,ag in PENDENTES_APROVACAO.items()]
    ESTADO_PAINEL["gravando"] = {c: {"titulo": g.meta.get("title", ""), "cortes": len(g.cortes_feitos)}
                                 for c, g in gravacoes.items() if g.plataforma == "twitch"}
    ESTADO_PAINEL["lives"] = {c: {"canal": g.canal, "plataforma": g.plataforma, "desde": g.desde,
                                  "cortes": len(g.cortes_feitos), "pela_extensao": g.pela_extensao,
                                  "titulo": g.meta.get("title", ""), "calor": g.termometro.calor_pct(),
                                  "video_id": (g.meta.get("id") or "") if g.plataforma == "youtube" else "",
                                  "url": g.url,
                                  "sensibilidade": g.termometro.sensibilidade,
                                  "momentos": [{"id": m["id"], "hora": m["hora"], "motivos": m["motivos"],
                                                "nota": m["nota"],
                                                "status": STATUS_MOMENTOS.get(m["id"], m.get("status", ""))}
                                               for m in g.termometro.eventos[-6:]]}
                              for c, g in gravacoes.items()}
    if isinstance(fila, FilaTarefas):
        ESTADO_PAINEL["tarefas"] = fila.resumo()
        ESTADO_PAINEL["historico_tarefas"] = fila.listar()
    ESTADO_PAINEL["fila"] = len(fila) + (1 if ocupado.get("v") else 0)


def usa_chat(g):
    """Twitch sempre; Kick quando a extensão mandou chat suficiente."""
    if g.plataforma == "twitch":
        return True
    try:
        return g.chat.exists() and g.chat.stat().st_size > 8000
    except OSError:
        return False


def na_madrugada(cfg, agora=None):
    agora = agora or datetime.now()
    try:
        hi, mi = (int(x) for x in cfg["madrugada_inicio"].split(":"))
        hf, mf = (int(x) for x in cfg["madrugada_fim"].split(":"))
    except (ValueError, KeyError):
        return True
    a, ini, fim = agora.hour * 60 + agora.minute, hi * 60 + mi, hf * 60 + mf
    return ini <= a < fim if ini <= fim else (a >= ini or a < fim)


def proxima_tarefa(fila, cfg):
    """A próxima tarefa que pode rodar agora. No modo madrugada, as automáticas esperam o horário;
    as manuais (extensão, painel, Corte) rodam sempre."""
    if isinstance(fila, FilaTarefas):
        return fila.proxima(bool(cfg.get("modo_madrugada") and not na_madrugada(cfg)))
    if not fila:
        return None
    if not cfg.get("modo_madrugada") or na_madrugada(cfg):
        try:
            return fila.pop(0)
        except IndexError:
            return None
    for i, t in enumerate(list(fila)):
        if t.get("prioridade", 0) >= 100 or t.get("manual"):
            try:
                fila.remove(t)
                return t
            except ValueError:
                return None
    return None


def verificar_tendencias(cfg, estado, fila):
    """Uma vez a cada 6h: pega os vídeos mais em alta (que você ainda não cortou) e manda achar
    os melhores momentos. Limite por dia em 'tendencias_por_dia'."""
    reg = estado.setdefault("tendencias", {"ultima": 0, "feitos": [], "dia": "", "hoje": 0})
    if reg.get("rodando") and time.time() - reg.get("ultima", 0) > 1800:
        reg["rodando"] = False              # sobrou de uma execução que foi fechada no meio
    if time.time() - reg["ultima"] < 6 * 3600:
        return
    reg["ultima"] = time.time()
    hoje = datetime.now().strftime("%Y-%m-%d")
    if reg["dia"] != hoje:
        reg["dia"], reg["hoje"] = hoje, 0
    vagas = cfg["tendencias_por_dia"] - reg["hoje"]
    if vagas <= 0:
        return
    if reg.get("rodando"):
        return
    reg["rodando"] = True
    # a busca leva 1-2 min: roda em paralelo pra não travar a extensão nem os outros canais
    threading.Thread(target=_buscar_tendencias, args=(cfg, reg, fila, vagas), daemon=True).start()


def _buscar_tendencias(cfg, reg, fila, vagas):
    log("🔥 procurando vídeos em alta no YouTube...")
    try:
        videos = tendencias.radar(cfg["tendencias_nichos"], cfg.get("tendencias_periodo", "semana"),
                                  detalhar=10, modo=cfg.get("tendencias_modo", "assunto"), filtros=cfg.get("tendencias_filtros"), log=lambda t: None)
    except Exception as e:
        log(f"   ⚠ radar de tendências falhou: {str(e)[:150]}")
        reg["rodando"] = False
        return
    if not videos:
        log("   (nenhum vídeo em alta encontrado agora)")
    for v in videos:
        if vagas <= 0:
            break
        if (isinstance(fila, FilaTarefas) and fila.origem_agendada(v["url"])) or "✔ você já cortou" in v.get("motivos", []):
            continue
        reg["hoje"] += 1
        vagas -= 1
        log(f"   🔥 em alta: {v['titulo'][:60]} ({', '.join(v.get('motivos', [])[:2])})")
        base = {"tipo": "corte", "fonte": v["url"], "topo": cfg["topo_youtube"],
                "pasta": v.get("canal") or "tendencias", "meta": {"titulo": v["titulo"], "canal": v.get("canal", "")}}
        adicionar(fila, {"_job_id": "youtube:" + v["id"], "tipo": "yt_transcricao", "url": v["url"], "base": base}, prioridade=20)
    reg["feitos"] = reg["feitos"][-300:]
    reg["rodando"] = False


def verificar_compilacao(cfg, estado, fila):
    agora = datetime.now()
    if not cfg.get("compilacao_auto") or agora.weekday() != 6 or agora.hour < 20:
        return
    semana = agora.strftime("%Y-%W")
    if estado.get("ultima_compilacao") == semana:
        return
    estado["ultima_compilacao"] = semana
    log("🎬 domingo: compilação da semana na fila")
    adicionar(fila, {"tipo": "compilacao"}, prioridade=-2)


EXT_VIDEO = (".mp4", ".mkv", ".mov", ".ts", ".webm", ".avi", ".flv")


def verificar_pasta_vigiada(cfg, estado, fila):
    """Vídeos novos na pasta vigiada viram tarefa (acha os momentos e corta, como um vídeo do YouTube).
    Só pega arquivo que parou de crescer há 1 minuto (não corta vídeo ainda sendo copiado)."""
    pasta = Path(str(cfg.get("pasta_vigiada") or "").strip())
    if not str(pasta) or str(pasta) == "." or not pasta.is_dir():
        return
    feitos = estado.setdefault("vigiada_feitos", [])
    for arq in sorted(pasta.iterdir()):
        if arq.suffix.lower() not in EXT_VIDEO or not arq.is_file():
            continue
        chave = f"{arq.resolve()}|{arq.stat().st_size}"
        if chave in feitos or time.time() - arq.stat().st_mtime < 60:
            continue
        feitos.append(chave)
        log(f"📂 vídeo novo na pasta vigiada: {arq.name}")
        meta = {"titulo": arq.stem, "canal": ""}
        base = {"tipo": "corte", "fonte": str(arq), "topo": "frame", "pasta": "pasta_vigiada", "meta": meta}
        adicionar(fila, {"_job_id": "arquivo:" + chave, "tipo": "yt_transcricao", "url": str(arq), "base": base},
                  prioridade=30)
    estado["vigiada_feitos"] = feitos[-500:]
    salvar_estado(estado)


_NUMEROS = {"ultima": 0.0, "rodando": False}


def verificar_numeros():
    """A cada 3h puxa as views do YouTube sozinho (em segundo plano). É isso que faz o
    aprendizado e o horário inteligente terem a medição de 24–30h de cada vídeo."""
    if _NUMEROS["rodando"] or time.time() - _NUMEROS["ultima"] < 3 * 3600:
        return
    if not cortes.carregar_config().get("atualizar_numeros_auto", True):
        return
    try:
        import postagem
        if not postagem.perfis_conectados():
            return
    except Exception:
        return
    _NUMEROS.update(ultima=time.time(), rodando=True)

    def rodar():
        try:
            import resultados
            msgs = []
            resultados.atualizar_youtube(log=msgs.append)
            resultados.gerar_aprendizado()
            log("📊 números do YouTube atualizados sozinho" + (f" — {msgs[-1][:80]}" if msgs else ""))
        except Exception as e:
            log(f"   ⚠ não consegui atualizar os números: {str(e)[:120]}")
        finally:
            _NUMEROS["rodando"] = False
    threading.Thread(target=rodar, daemon=True).start()


def talvez_desligar(cfg, gravacoes, fila, ocupado):
    """Modo madrugada + 'desligar quando terminar': acabou o que tinha pra fazer de madrugada → desliga."""
    if not (cfg.get("modo_madrugada") and cfg.get("desligar_pc_ao_terminar")) or os.name != "nt":
        return False
    if fila or ocupado.get("v") or gravacoes or not ocupado.get("madrugada_feitos") or not na_madrugada(cfg):
        return False
    log("💤 terminei os cortes da madrugada — desligando o PC em 2 minutos "
        "(pra cancelar: abra o Executar e digite  shutdown /a )")
    subprocess.run(["shutdown", "/s", "/t", "120", "/c", "Gerador de Cortes: terminei a fila da madrugada."])
    ocupado["madrugada_feitos"] = 0
    return True


def main():
    cortes.checar_ffmpeg()
    cfg = carregar_config()
    estado = carregar_estado()
    gravacoes: dict[str, GravacaoLive] = {}
    agendados: list[dict] = []
    if not iniciar_painel():
        return
    import baixador                     # YouTube muda toda semana: yt-dlp em dia (a cada 3 dias, em segundo plano)
    threading.Thread(target=baixador.manter_atualizado, kwargs={"log": log}, daemon=True).start()
    global FILA_ATIVA
    fila = FilaTarefas(BASE / "fila_tarefas.sqlite3")
    FILA_ATIVA = fila
    salvo = fila.carregar_contexto("agenda", {})
    agendados.extend(salvo.get("agendados", []))
    PENDENTES_APROVACAO.update(salvo.get("aprovacoes", {}))
    STATUS_MOMENTOS.update(salvo.get("status", {}))
    ultima_verificacao = 0.0
    ultima_cfg = time.time()
    sondando = threading.Event()
    resultados_sondagem = queue.Queue()
    ARQ_PARAR.unlink(missing_ok=True)

    # os cortes rodam numa linha separada: o monitor continua respondendo a extensão
    # (gravar, cortar, chat) mesmo enquanto um corte está sendo montado
    parar = threading.Event()
    ocupado = {"v": False}

    def trabalhador():
        avisou_espera = False
        while not parar.is_set():
            cfg_t = carregar_config()
            tarefa = proxima_tarefa(fila, cfg_t)
            if tarefa is None:
                if fila and not avisou_espera:
                    log(f"🌙 modo madrugada: {len(fila)} corte(s) automático(s) esperando "
                        f"{cfg_t['madrugada_inicio']} (os manuais rodam na hora)")
                    avisou_espera = True
                time.sleep(2)
                continue
            avisou_espera = False
            ocupado["v"] = True
            ocupado["madrugada_feitos"] = ocupado.get("madrugada_feitos", 0) + (0 if tarefa.get("prioridade", 0) >= 100 else 1)
            try:
                executar(tarefa, cfg_t, fila)
            finally:
                ocupado["v"] = False
    linha_cortes = threading.Thread(target=trabalhador, daemon=True)
    linha_cortes.start()

    log(f"Monitor iniciado — Twitch: {', '.join(cfg['twitch']) or '-'} | "
        f"Kick: {', '.join(cfg['kick']) or '-'} | YouTube: {len(cfg['youtube'])} canal(is) | "
        f"Lives YouTube: {len(cfg['youtube_lives'])}")
    try:
        while True:
            if ARQ_PARAR.exists():                 # a interface pediu pra parar
                ARQ_PARAR.unlink(missing_ok=True)
                raise KeyboardInterrupt
            if time.time() - ultima_cfg > 15:
                cfg = carregar_config()
                ultima_cfg = time.time()
            # Consultas de rede ficam fora do ciclo que atende a extensão.
            while not resultados_sondagem.empty():
                descobertas, estado_rede = resultados_sondagem.get()
                for chave, canal, plat, url, meta in descobertas:
                    if chave not in gravacoes and meta:
                        try:
                            gravacoes[chave] = GravacaoLive(canal, meta, cfg, plat, url)
                        except Exception as e:
                            log(f"Não consegui iniciar {canal}: {e}")
                for k in ('youtube', 'pendentes', 'clips'):
                    if k in estado_rede:
                        estado[k] = estado_rede[k]
                salvar_estado(estado)
            if time.time() - ultima_verificacao >= cfg["verificar_a_cada_min"] * 60 and not sondando.is_set() and len(fila) < int(cortes.carregar_config().get("max_tarefas_pendentes", 100)):
                ultima_verificacao = time.time()
                sondando.set()
                snapshot = json.loads(json.dumps(estado))
                cfg_rede, ativos = dict(cfg), set(gravacoes)
                def consultar(cfg_rede=cfg_rede, ativos=ativos, snapshot=snapshot):
                    descobertas, checar = [], []
                    try:
                        for plat in ('twitch', 'kick'):
                            for canal in cfg_rede[plat]:
                                chave = chave_live(canal, plat)
                                if chave not in ativos:
                                    checar.append((chave, canal, plat, url_live(canal, plat)))
                        for url_canal in cfg_rede['youtube_lives']:
                            canal = url_canal.rstrip('/').split('/')[-1].lstrip('@')
                            url = url_canal if url_canal.endswith('/live') else url_canal+'/live'
                            chave = 'ytlive:'+canal
                            if chave not in ativos:
                                checar.append((chave, canal, 'youtube', url))
                        # cada checagem leva ~6 s (abre o streamlink): 4 de cada vez em vez de uma por uma
                        descobertas = [(*c, m) for c, m in zip(checar, checar_lives(checar))]
                        if cfg_rede.get('clips_twitch'):
                            for canal in cfg_rede['twitch']:
                                verificar_clips_twitch(canal, cfg_rede, snapshot, fila)
                        for url in cfg_rede['youtube']:
                            verificar_youtube(url, cfg_rede, snapshot)
                        processar_pendentes_youtube(cfg_rede, snapshot, fila)
                        resultados_sondagem.put((descobertas, snapshot))
                    except Exception as e:
                        log(f'Sondagem de canais: {e}')
                    finally:
                        sondando.clear()
                threading.Thread(target=consultar, daemon=True).start()
                if cfg.get('tendencias_auto'):
                    verificar_tendencias(cfg, estado, fila)
                verificar_compilacao(cfg, estado, fila)
                verificar_numeros()
                try:
                    verificar_pasta_vigiada(cfg, estado, fila)
                except OSError as e:
                    log(f"   ⚠ pasta vigiada: {e}")
                from recursos import limpar_gravacoes
                try:
                    removidas = limpar_gravacoes(PASTA_GRAVACOES, float(cortes.carregar_config().get('retencao_gravacoes_dias', 0)),
                                                 [g.pasta for g in gravacoes.values()], fila.fonte_em_uso)
                    if removidas: log(f'Retenção: {len(removidas)} gravações antigas removidas.')
                except (OSError, ValueError) as e:
                    log(f'Retenção: {e}')
                try:                                   # projetos de edição antigos, restos e aviso de disco
                    import desempenho
                    desempenho.limpeza_automatica(log=log)
                except OSError as e:
                    log(f'Limpeza: {e}')
                salvar_estado(estado)
                talvez_desligar(cfg, gravacoes, fila, ocupado)

            manuais: list[dict] = []
            tratar_comandos(gravacoes, cfg, agendados, manuais, fila)
            for t in reversed(manuais):
                adicionar(fila, dict(t, manual=True), prioridade=100)
            processar_agendados(gravacoes, cfg, agendados, fila)

            for chave, g in list(gravacoes.items()):
                limite = cfg.get("extensao_parar_sem_sinal_min", 10) * 60
                if g.ativa() and g.pela_extensao and time.time() - g.ultimo_sinal > limite:
                    log(f"⏹ a aba de {g.canal} foi fechada — parando a gravação")
                    g.parar()
                from recursos import verificar_disco
                try:
                    verificar_disco(BASE, float(cortes.carregar_config().get('min_disco_gb', 2)))
                except RuntimeError as e:
                    if g.ativa():
                        log(str(e)); g.parar()
                if not g.ativa():
                    log(f"⚫ live de {g.canal} terminou — analisando o final")
                    g.parar()
                    if usa_chat(g):
                        analisar_gravacao(g, cfg, fila, final=True)
                    else:
                        analisar_por_audio(g, cfg, fila, final=True)
                    if cfg["apagar_gravacao_depois"]:
                        adicionar(fila, {"tipo": "apagar", "pasta": str(g.pasta)}, prioridade=-1)
                    del gravacoes[chave]
                elif cfg.get("tempo_real", True) and usa_chat(g):
                    try:
                        tempo_real(g, cfg, agendados)
                    except Exception as e:
                        log(f"   ⚠ detector de {g.canal}: {str(e)[:150]}")
                elif time.time() - g.ultima_analise >= cfg["analisar_live_a_cada_min"] * 60:
                    g.ultima_analise = time.time()
                    if usa_chat(g):
                        log(f"🔎 analisando o chat de {g.canal}...")
                        analisar_gravacao(g, cfg, fila)
                    else:
                        log(f"🔎 analisando o áudio da live de {g.canal}...")
                        analisar_por_audio(g, cfg, fila)

            expirar_pendentes()
            fila.salvar_contexto("agenda", {"agendados": agendados, "aprovacoes": PENDENTES_APROVACAO, "status": STATUS_MOMENTOS})
            atualizar_estado(gravacoes, fila, ocupado)
            time.sleep(1)
    except KeyboardInterrupt:
        log("Parando... (gravações em andamento ficam salvas na pasta 'gravacoes')")
        for g in gravacoes.values():
            g.parar()
        salvar_estado(estado)
        fila.salvar_contexto("agenda", {"agendados": agendados, "aprovacoes": PENDENTES_APROVACAO, "status": STATUS_MOMENTOS})
        parar.set()
        if ocupado["v"]:
            log("Esperando o corte que está sendo montado terminar...")
            linha_cortes.join(timeout=900)


if __name__ == "__main__":
    main()
