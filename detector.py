"""
Detector de momentos em TEMPO REAL pra lives — o "termômetro".

A cada ~30s ele lê só as mensagens novas do chat (e os últimos segundos do áudio) e calcula,
segundo a segundo, uma nota de "calor" somando vários sinais:

  • PESSOAS DIFERENTES falando (não a quantidade de mensagens → spam e bot não enganam)
  • RISADA / CHOQUE no chat (KKKK, KEKW, ???, "MEU DEUS"...)
  • LINKS DE CLIP no chat (os próprios viewers clipando = lance bom de verdade)
  • PICO DE VOLUME no áudio da live (grito, risada alta)
  • SALTO NO NÚMERO DE ESPECTADORES (vem da extensão do Chrome)

Tudo comparado com o "normal" daquele canal nos últimos minutos (cada canal tem o seu).

Falsos picos ignorados: comandos (!sorteio, !pix), bots (Nightbot, StreamElements...),
copypasta repetida, trem de sub/gift, sorteio, e os primeiros minutos (enquanto aprende o normal).

No modo diagnóstico, anota tudo num arquivo pra calibrar a sensibilidade depois.
"""
from __future__ import annotations

import json
import re
import statistics
import subprocess
import time
import uuid
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).resolve().parent
PASTA_DIAG = PASTA / "diagnostico"

LIMIAR = {"baixa": 70.0, "media": 50.0, "alta": 35.0}          # menor = corta mais
JANELA = 15                    # segundos de cada "janela" de chat
AQUECIMENTO = 180              # segundos aprendendo o normal antes de detectar
ESPERA_ENTRE = 75              # segundos mínimos entre dois momentos

BOTS = {"nightbot", "streamelements", "streamlabs", "moobot", "fossabot", "wizebot", "botrixoficial",
        "kickbot", "sery_bot", "soundalerts", "commanderroot", "pokemoncommunitygame", "own3d",
        "streamcaptainbot", "blerp", "kofistreambot", "tangiabot", "lolrankbot"}
RISADA = re.compile(r"(k{4,}|kekw|lul|omegalul|icant|lmao|haha|hehe|rsrs|\?{2,}|!{3,}|caralho|meu deus|"
                    r"mds|nooo+|pog|wtf|a{4,}|😂|🤣|💀|😱|😳|🔥)", re.I)
CLIP = re.compile(r"(clips\.twitch\.tv/|twitch\.tv/\w+/clip/|kick\.com/\w+/clips?/|kick\.com/\w+\?clip=)", re.I)
RUIDO = re.compile(r"(sorteio|giveaway|gifted|presenteou|deu \d+ sub|subscribed|se inscreveu|resub|"
                   r"bits|cheer\d+|pix|primeiro|first|oi chat|boa noite|bom dia|boa tarde)", re.I)


def _norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[^\wà-ú ]", "", t.lower())).strip()


class Termometro:
    def __init__(self, canal, plataforma="twitch", sensibilidade="media", diagnostico=False):
        self.canal, self.plataforma = canal, plataforma
        self.sensibilidade = sensibilidade if sensibilidade in LIMIAR else "media"
        self.diagnostico = diagnostico
        self.offset_chat = 0
        self.inicio = time.time()
        self.seg = {}                       # segundo → {"u": set, "n": int, "r": int, "c": int}
        self.ultimo_avaliado = 0
        self.textos = deque(maxlen=600)     # (t, user, texto) pro contexto da IA
        self.repeticoes = deque(maxlen=400)  # (t, texto normalizado) pra pegar copypasta
        self.audio_lock = threading.Lock()
        self.audio = {}                     # segundo → volume
        self.espectadores = deque(maxlen=40)
        self.historico_u = deque(maxlen=60)  # pessoas por janela (o "normal" do canal)
        self.evento = None
        self.ultimo_evento_fim = 0
        self.eventos = []                   # momentos detectados
        self.calor = 0.0
        self.ultimos_sinais = {}

    @property
    def limiar(self):
        return LIMIAR[self.sensibilidade]

    # ---------- entradas ----------
    def ler_chat(self, arquivo: Path):
        """Lê só as linhas novas do chat.jsonl (desde a última leitura)."""
        try:
            with open(arquivo, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self.offset_chat)
                linhas = f.readlines()
                self.offset_chat = f.tell()
        except OSError:
            return 0
        n = 0
        for l in linhas:
            try:
                m = json.loads(l)
                self.mensagem(float(m["t"]), str(m.get("u", "")), str(m.get("m", "")))
                n += 1
            except (ValueError, KeyError, json.JSONDecodeError):
                continue
        return n

    def mensagem(self, t, usuario, texto):
        texto = texto.strip()
        if not texto:
            return
        u = (usuario or "").lower()
        if u in BOTS or u.endswith("bot") or texto.startswith(("!", "/")):
            return
        clip = bool(CLIP.search(texto))
        if not clip and RUIDO.search(texto) and not RISADA.search(texto):
            return
        norm = _norm(texto)
        if len(norm) > 35:                  # copypasta: o mesmo textão repetido conta uma vez só
            iguais = sum(1 for tt, x in self.repeticoes if x == norm and t - tt < 40)
            self.repeticoes.append((t, norm))
            if iguais >= 1:
                return
        s = int(t)
        b = self.seg.setdefault(s, {"u": set(), "n": 0, "r": 0, "c": 0})
        if u:
            b["u"].add(u)  # Sem autor conhecido, conta volume, nunca inventa pessoas.
        b["n"] += 1
        if RISADA.search(texto):
            b["r"] += 1
        if clip:
            b["c"] += 1
        self.textos.append((t, u, texto[:200]))

    def ler_audio(self, video: Path, segundos=45, fim=None):
        """Volume por segundo dos últimos ~45s da gravação (leve: só decodifica o áudio)."""
        try:
            import numpy as np
            fim = fim or time.time()          # (a data do arquivo não atualiza no Windows enquanto grava)
            dur = _duracao(video)
            if dur < segundos + 5:
                return
            r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur - segundos:.2f}", "-i", str(video),
                                "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True,
                               timeout=60, creationflags=_SEM_JANELA)
            a = np.frombuffer(r.stdout, dtype=np.int16).astype("float32")
            n = len(a) // 8000
            if n < 5:
                return
            rms = np.sqrt((a[: n * 8000].reshape(n, 8000) ** 2).mean(axis=1))
            with self.audio_lock:
                for i, v in enumerate(rms):
                    self.audio[int(fim - n + i)] = float(v)
        except Exception:
            pass

    def espectador(self, n, t=None):
        if n and n > 0:
            self.espectadores.append((t or time.time(), int(n)))

    # ---------- cálculo ----------
    def _janela(self, s):
        u, n, r, c = set(), 0, 0, 0
        for x in range(s - JANELA, s):
            b = self.seg.get(x)
            if b:
                u |= b["u"]
                n += b["n"]
                r += b["r"]
        for x in range(s - 60, s):           # clips: olha o último minuto
            b = self.seg.get(x)
            if b:
                c += b["c"]
        return len(u), n, r, c

    def _audio_ratio(self, s):
        with self.audio_lock:
            audio = dict(self.audio)
        recentes = [audio[x] for x in range(s - JANELA, s) if x in audio]
        if len(recentes) < 5:
            return None
        base = [v for k, v in audio.items() if s - 600 <= k < s - JANELA]
        if len(base) < 60:
            return None
        normal = statistics.median(base) or 1.0
        return max(recentes) / normal

    def _salto_espectadores(self, s):
        agora = [n for t, n in self.espectadores if s - 90 <= t <= s]
        antes = [n for t, n in self.espectadores if s - 420 <= t <= s - 240]
        if not agora or not antes:
            return 0.0
        return max(0.0, max(agora) / max(1, statistics.median(antes)) - 1.08)

    def nota(self, s):
        u, n, r, c = self._janela(s)
        normal_u = statistics.median(self.historico_u) if len(self.historico_u) >= 8 else max(3.0, u)
        s_chat = max(0.0, u / max(3.0, normal_u) - 1.0)
        frac_risada = r / n if n else 0.0
        audio = self._audio_ratio(s)
        s_audio = max(0.0, audio - 1.6) if audio else 0.0
        s_view = self._salto_espectadores(s)
        nota = (32 * min(s_chat, 4.0) * (0.55 + 0.9 * frac_risada) + 16 * min(c, 3) +
                12 * min(s_audio, 4.0) + 60 * min(s_view, 0.6))
        if u < 6 and c == 0 and s_audio < 1.5:       # chat pequenininho: precisa de outro sinal
            nota *= 0.5
        sinais = {"pessoas": u, "normal": round(normal_u, 1), "risada": round(frac_risada, 2), "clips": c,
                  "audio": round(audio, 2) if audio else None, "espectadores": round(s_view, 2)}
        return nota, sinais

    @staticmethod
    def motivos(sinais):
        m = []
        if sinais["normal"] and sinais["pessoas"] >= sinais["normal"] * 1.8:
            m.append(f"chat explodiu ({sinais['pessoas']} pessoas, normal {sinais['normal']:g})")
        if sinais["risada"] >= 0.35:
            m.append(f"risada/choque ({int(sinais['risada'] * 100)}% das msgs)")
        if sinais["clips"]:
            m.append(f"{sinais['clips']} clip(s) criados")
        if sinais["audio"] and sinais["audio"] >= 2.5:
            m.append(f"pico de volume ({sinais['audio']:.1f}x)")
        if sinais["espectadores"] >= 0.15:
            m.append(f"+{int(sinais['espectadores'] * 100)}% espectadores")
        return m or ["movimento acima do normal"]

    def avaliar(self, agora=None):
        """Avalia os segundos novos. Devolve a lista de momentos que FECHARAM agora."""
        agora = int(agora or time.time()) - 3          # 3s de folga pra mensagens atrasadas
        if not self.ultimo_avaliado:
            self.ultimo_avaliado = agora - 1
        novos = []
        maior = (0.0, None, None)
        for s in range(self.ultimo_avaliado + 1, agora + 1):
            if s % 5 == 0:                               # atualiza o "normal" a cada 5s
                u, *_ = self._janela(s)
                if u or self.historico_u:
                    self.historico_u.append(u)
            nota, sinais = self.nota(s)
            self.calor = nota
            if nota > maior[0]:
                maior = (nota, s, sinais)
            aquecendo = s - self.inicio < AQUECIMENTO
            if aquecendo:
                continue
            ev = self.evento
            if ev is None:
                if nota >= self.limiar and s - self.ultimo_evento_fim >= ESPERA_ENTRE:
                    self.evento = {"ini": s, "pico": s, "nota": nota, "sinais": sinais, "abaixo": 0}
            else:
                if nota > ev["nota"]:
                    ev.update(pico=s, nota=nota, sinais=sinais)
                ev["abaixo"] = ev["abaixo"] + 1 if nota < self.limiar * 0.7 else 0
                if ev["abaixo"] >= 5 or s - ev["ini"] >= 25:
                    novos.append(self._fechar(ev))
                    self.evento = None
                    self.ultimo_evento_fim = s
        self.ultimo_avaliado = agora
        self.ultimos_sinais = maior[2] or self.ultimos_sinais
        # limpeza
        for k in [k for k in self.seg if k < agora - 900]:
            del self.seg[k]
        with self.audio_lock:
            for k in [k for k in self.audio if k < agora - 900]:
                del self.audio[k]
        if self.diagnostico:
            self._diag({"tipo": "minuto", "t": agora, "hora": datetime.fromtimestamp(agora).strftime("%H:%M:%S"),
                        "nota_max": round(maior[0], 1), "limiar": self.limiar,
                        "aquecendo": agora - self.inicio < AQUECIMENTO, "sinais": maior[2]})
        return novos

    def _fechar(self, ev):
        mom = {"id": uuid.uuid4().hex[:10], "t": ev["pico"], "t_ini": ev["ini"], "nota": round(ev["nota"], 1),
               "hora": datetime.fromtimestamp(ev["pico"]).strftime("%H:%M:%S"),
               "motivos": self.motivos(ev["sinais"]), "sinais": ev["sinais"],
               "chat": " | ".join(x for t, u, x in self.textos if ev["pico"] - 20 <= t <= ev["pico"] + 8)[-700:],
               "status": "detectado"}
        self.eventos.append(mom)
        self.eventos = self.eventos[-30:]
        if self.diagnostico:
            self._diag(dict(mom, tipo="MOMENTO", limiar=self.limiar))
        return mom

    def calor_pct(self):
        return int(min(100, self.calor / self.limiar * 100)) if self.limiar else 0

    def _diag(self, dados):
        try:
            PASTA_DIAG.mkdir(exist_ok=True)
            arq = PASTA_DIAG / f"{self.plataforma}_{self.canal}_{datetime.now():%Y%m%d}.jsonl"
            with open(arq, "a", encoding="utf-8") as f:
                f.write(json.dumps(dados, ensure_ascii=False) + "\n")
        except OSError:
            pass


# ---------- utilidades ----------
try:
    _SEM_JANELA = subprocess.CREATE_NO_WINDOW
except AttributeError:
    _SEM_JANELA = 0


def _duracao(video):
    if Path(video).suffix.lower() == '.m3u8' and Path(video).is_file():
        from gravacao_segmentada import duracao
        return duracao(video)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                        "default=nw=1:nk=1", str(video)], capture_output=True, text=True,
                       timeout=30, creationflags=_SEM_JANELA)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def resumo_diagnostico(arquivo: Path):
    """Texto curto com o que o diagnóstico viu (pra você ou pra me mandar)."""
    momentos, notas, quase = [], [], 0
    limiar = None
    for l in Path(arquivo).read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(l)
        except json.JSONDecodeError:
            continue
        if d.get("tipo") == "MOMENTO":
            momentos.append(d)
        elif d.get("tipo") == "minuto" and not d.get("aquecendo"):
            notas.append(d.get("nota_max", 0))
            limiar = d.get("limiar", limiar)
            if limiar and limiar * 0.7 <= d.get("nota_max", 0) < limiar:
                quase += 1
    if not notas:
        return "Ainda sem dados suficientes."
    linhas = [f"{len(momentos)} momento(s) detectado(s), {quase} quase-momento(s).",
              f"Nota típica: {statistics.median(notas):.0f} | maior: {max(notas):.0f} | limiar: {limiar:g}"]
    if len(notas) > 60 and len(momentos) == 0:
        linhas.append("→ Nenhum momento em bastante tempo: talvez aumentar a sensibilidade.")
    elif len(momentos) > len(notas) / 20:
        linhas.append("→ Muitos momentos: talvez diminuir a sensibilidade.")
    for m in momentos[-8:]:
        linhas.append(f"  {m['hora']}  nota {m['nota']:g}  — {', '.join(m['motivos'])}")
    return "\n".join(linhas)
