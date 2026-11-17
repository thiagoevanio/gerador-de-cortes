"""
Efeitos que deixam o corte mais dinâmico — tudo roda no processador, sem placa de vídeo:
  - remover_silencios / intervalos_sem_silencio: corta pausas longas sem re-encodar à toa
  - tirar_vicios / intervalos_sem_vicios: corta "é…", "tipo,", "né?", "hum" com corte suave
  - aplicar_remocao_em_mantidos: junta todos os cortes temporais numa passada única de FFmpeg
  - trajetoria_rosto / trajetoria_de: acha onde está o rosto com filtragem bidirecional suave
  - expr_crop_x: movimento de câmera com curva ease-in-out (smoothstep) pro ffmpeg
  - gerar_boom / gerar_whoosh / gerar_pop: efeitos sonoros de estúdio sintetizados em estéreo
"""
from __future__ import annotations

import re
import subprocess
import wave
from pathlib import Path

import cortes


# ---------------- utilitários de intervalos (zero re-encode) ----------------
def unir_intervalos(intervalos):
    """Une intervalos [(a, b), ...] sobrepostos ou colados."""
    uniao = []
    for a, b in sorted(intervalos or []):
        if b <= a:
            continue
        if uniao and a <= uniao[-1][1] + 1e-4:
            uniao[-1] = (uniao[-1][0], max(uniao[-1][1], b))
        else:
            uniao.append((float(a), float(b)))
    return uniao


def inverter_intervalos(duracao: float, remover, minimo=0.05):
    """Transforma intervalos a remover [(a, b), ...] nos intervalos a manter [(a, b), ...]."""
    manter, pos = [], 0.0
    for a, b in unir_intervalos(remover):
        a, b = max(0.0, a), min(float(duracao), b)
        if a > pos:
            manter.append((pos, a))
        pos = max(pos, b)
    if pos < duracao:
        manter.append((pos, float(duracao)))
    return [(round(a, 4), round(b, 4)) for a, b in manter if b - a > minimo]


def aplicar_remocao_em_mantidos(manter, remover, minimo=0.05):
    """Projeta intervalos 'remover' (medidos na linha do tempo virtual já cortada)
    de volta para os intervalos 'manter' no tempo do vídeo original.
    Permite acumular silêncios + vícios + revisor de frase em UMA única passada de vídeo."""
    if not manter:
        return []
    if not remover:
        return list(manter)
    dur_virtual = sum(b - a for a, b in manter)
    virt_manter = inverter_intervalos(dur_virtual, remover, minimo=minimo)
    if not virt_manter:
        return list(manter)
    novo_manter = []
    acc = 0.0
    for orig_a, orig_b in manter:
        seg_len = orig_b - orig_a
        seg_ini, seg_fim = acc, acc + seg_len
        for va, vb in virt_manter:
            ov_a = max(seg_ini, va)
            ov_b = min(seg_fim, vb)
            if ov_b - ov_a > minimo:
                novo_manter.append((round(orig_a + (ov_a - seg_ini), 4),
                                    round(orig_a + (ov_b - seg_ini), 4)))
        acc = seg_fim
    return novo_manter or list(manter)


def ajustar_zero_crossing(amostras, t: float, sr=16000, janela_ms=12):
    """Ajusta o instante 't' para o ponto de cruzamento por zero (ou menor amplitude)
    mais próximo dentro de ±janela_ms, evitando estalos secos no corte de áudio."""
    if amostras is None or len(amostras) == 0:
        return t
    import numpy as np
    idx = max(0, min(len(amostras) - 1, int(round(t * sr))))
    delta = max(1, int(round(sr * janela_ms / 1000.0)))
    i0 = max(0, idx - delta)
    i1 = min(len(amostras) - 1, idx + delta)
    if i1 <= i0 + 1:
        return t
    trecho = amostras[i0:i1 + 1]
    sinais = np.signbit(trecho[:-1]) != np.signbit(trecho[1:])
    if np.any(sinais):
        cruzamentos = np.where(sinais)[0] + i0
        escolhido = int(cruzamentos[np.argmin(np.abs(cruzamentos - idx))])
    else:
        escolhido = int(i0 + np.argmin(np.abs(trecho)))
    return round(escolhido / sr, 4)


def recortar_wav_mantidos(wav_entrada: Path, wav_saida: Path, manter, fade_ms=16):
    """Recorta um arquivo .wav (16 kHz mono) mantendo apenas os intervalos 'manter',
    ajustando os cortes no zero-crossing e aplicando micro-crossfade cosseno nas emendas.
    Roda em milissegundos na memória, sem precisar recodificar vídeo antes do Whisper."""
    import numpy as np
    amostras = cortes.ler_wav(wav_entrada)
    sr = 16000
    n_total = len(amostras)
    if n_total == 0 or not manter:
        cortes.rodar(["ffmpeg", "-y", "-i", str(wav_entrada), str(wav_saida)])
        return wav_saida
    fade_n = max(4, int(round(sr * fade_ms / 1000.0)))
    ramp_in = (0.5 * (1.0 - np.cos(np.pi * np.arange(fade_n, dtype=np.float32) / fade_n))).astype(np.float32)
    ramp_out = ramp_in[::-1]
    partes = []
    for k, (a, b) in enumerate(manter):
        ta = ajustar_zero_crossing(amostras, a, sr) if a > 0.01 else max(0.0, a)
        tb = ajustar_zero_crossing(amostras, b, sr) if b < (n_total / sr) - 0.01 else min(n_total / sr, b)
        i0 = max(0, min(n_total, int(round(ta * sr))))
        i1 = max(i0, min(n_total, int(round(tb * sr))))
        if i1 - i0 < 8:
            continue
        seg = amostras[i0:i1].copy()
        if len(seg) >= fade_n * 2:
            if k > 0:
                seg[:fade_n] *= ramp_in
            if k < len(manter) - 1:
                seg[-fade_n:] *= ramp_out
        partes.append(seg)
    final = np.concatenate(partes) if partes else amostras
    pcm = np.clip(final * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(wav_saida), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return wav_saida


# ---------------- silêncios ----------------
def achar_silencios(video: Path, limiar_db=-32, minimo=0.55):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-af",
                        f"silencedetect=noise={limiar_db}dB:d={minimo}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=cortes.SEM_JANELA)
    inicios = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    fins = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(inicios, fins + [None] * (len(inicios) - len(fins))))


def tempo_sem_silencio(t, mantidos):
    """Onde o segundo 't' do vídeo original foi parar depois de tirar os silêncios."""
    if not mantidos:
        return t
    novo = 0.0
    for a, b in mantidos:
        if t <= a:
            break
        novo += min(b, t) - a
    return novo


def momento_do_trecho(palavras, foco, alvo=60.0):
    """Sem IA: o melhor pedaço em volta do lance (foco), começando numa pausa/frase e terminando
    depois da reação. Devolve (índice da 1ª palavra, índice da última) ou None."""
    if len(palavras) < 6 or foco is None:
        return None
    def comeca_frase(j):
        return j == 0 or palavras[j]["ini"] - palavras[j - 1]["fim"] >= 0.6 or \
            FIM_FRASE.search(palavras[j - 1]["t"]) is not None
    def termina_frase(j):
        return j == len(palavras) - 1 or palavras[j + 1]["ini"] - palavras[j]["fim"] >= 0.6 or \
            FIM_FRASE.search(palavras[j]["t"]) is not None
    alvo_ini, alvo_fim = foco - alvo * 0.6, foco + alvo * 0.35
    inis = [j for j in range(len(palavras)) if comeca_frase(j) and foco - alvo * 0.9 <= palavras[j]["ini"] <= foco - 6]
    fins = [j for j in range(len(palavras)) if termina_frase(j) and foco + 4 <= palavras[j]["fim"] <= foco + alvo * 0.6]
    i0 = min(inis, key=lambda j: abs(palavras[j]["ini"] - alvo_ini)) if inis else \
        min(range(len(palavras)), key=lambda j: abs(palavras[j]["ini"] - max(0, alvo_ini)))
    i1 = min(fins, key=lambda j: abs(palavras[j]["fim"] - alvo_fim)) if fins else \
        min(range(len(palavras)), key=lambda j: abs(palavras[j]["fim"] - alvo_fim))
    if i1 <= i0 or palavras[i1]["fim"] - palavras[i0]["ini"] < 15:
        return None
    return i0, i1


def intervalos_sem_silencio(video: Path, folga=0.12, dur=None):
    """Calcula os intervalos (manter, removidos, segundos_removidos) das pausas longas
    sem recodificar o vídeo."""
    dur = float(dur if dur is not None else cortes.duracao_video(video))
    silencios = achar_silencios(video)
    manter, removidos, pos = [], [], 0.0
    for ini, fim in silencios:
        fim = dur if fim is None else fim
        corte_ini = ini + folga
        corte_fim = fim - folga
        if corte_fim > corte_ini + 0.08:
            if corte_ini > pos:
                manter.append((pos, corte_ini))
            removidos.append((max(pos, corte_ini), corte_fim))
            pos = max(pos, corte_fim)
    if pos < dur:
        manter.append((pos, dur))
    manter = [(round(a, 4), round(b, 4)) for a, b in manter if b - a > 0.08]
    removido = dur - sum(b - a for a, b in manter)
    global ULTIMOS_MANTIDOS
    ULTIMOS_MANTIDOS = None
    if removido < 1.0 or not manter:
        return [(0.0, round(dur, 4))], [], 0.0
    return manter, removidos, round(removido, 3)


def remover_silencios(video: Path, pasta: Path, folga=0.12):
    """Devolve um vídeo novo sem as pausas (ou o mesmo, se não valer a pena)."""
    manter, _, removido = intervalos_sem_silencio(video, folga=folga)
    if removido < 1.0 or len(manter) <= 1 and manter and manter[0][0] == 0.0 and abs(manter[0][1] - cortes.duracao_video(video)) < 0.1:
        return video, 0.0
    saida = cortar_intervalos_mantidos(video, pasta, manter, "sem_silencio.mp4")
    return saida, removido


# ---------------- rosto ----------------
MODELO_ROSTO = Path(__file__).resolve().parent / "modelos" / "face_detection_yunet_2023mar.onnx"


def _criar_detector():
    """YuNet (preciso e leve, vem junto do projeto). Se não der, tenta o Haar clássico."""
    import cv2
    if MODELO_ROSTO.exists() and hasattr(cv2, "FaceDetectorYN"):
        try:
            yunet = cv2.FaceDetectorYN.create(str(MODELO_ROSTO), "", (480, 270), 0.7, 0.3, 50)

            def detectar(img):
                yunet.setInputSize((img.shape[1], img.shape[0]))
                _, faces = yunet.detect(img)
                return [] if faces is None else [tuple(f[:4]) for f in faces]
            return detectar
        except Exception:
            pass
    try:
        haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if haar.empty():
            return None

        def detectar(img):
            cinza = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
            return list(haar.detectMultiScale(cinza, 1.15, 5, minSize=(28, 28)))
        return detectar
    except Exception:
        return None


def _suavizar_segmento_camera(valores, zona_morta=0.055, alfa=0.32, passo_max=0.14):
    """Filtro passa-baixa bidirecional (ida + volta) com zona morta, rejeição de falsos picos
    isolados (despiking) e limitador de velocidade máxima (slew-rate):
    elimina o efeito de 'robô dando tranco' mantendo a câmera centrada na pessoa."""
    if len(valores) <= 2:
        return list(valores)
    limpos = list(valores)
    for i in range(1, len(limpos) - 1):
        viz_media = (limpos[i - 1] + limpos[i + 1]) * 0.5
        if abs(limpos[i - 1] - limpos[i + 1]) < 0.08 and abs(limpos[i] - viz_media) > 0.22:
            limpos[i] = viz_media
    ida, atual = [], limpos[0]
    for c in limpos:
        if abs(c - atual) > zona_morta:
            delta = (c - atual) * alfa
            if abs(delta) > passo_max:
                delta = passo_max if delta > 0 else -passo_max
            atual += delta
        ida.append(atual)
    volta, atual = [0.0] * len(ida), ida[-1]
    for i in range(len(ida) - 1, -1, -1):
        atual = ida[i] * 0.65 + atual * 0.35
        volta[i] = round(atual, 4)
    return volta


def amostras_video(cap, passo):
    """Percorre o vídeo EM SEQUÊNCIA e devolve (índice, quadro) a cada `passo` segundos.
    grab() só avança (barato); retrieve() converte só os quadros usados. Pular com
    CAP_PROP_POS_FRAMES obrigava a decodificar de novo desde o último quadro-chave a cada amostra
    (5x mais lento num PC de 2 núcleos)."""
    import cv2
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    salto = max(1, int(round(fps * passo)))
    idx = 0
    while cap.grab():
        if idx % salto == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            yield idx, frame
        idx += 1


def trajetoria_rosto(video: Path, passo=0.5):
    """Lista de (segundo, centro_x de 0 a 1) do maior rosto. None se quase não achar rosto."""
    try:
        import cv2
    except ImportError:
        print("   ⚠ OpenCV não instalado — sem enquadramento no rosto.")
        return None
    detectar = _criar_detector()
    if not detectar:
        return None
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    pontos, achou = [], 0
    try:
        for idx, frame in amostras_video(cap, passo):
            h, w = frame.shape[:2]
            pequeno = cv2.resize(frame, (480, int(480 * h / w)))
            rostos = detectar(pequeno)
            if len(rostos):
                x, y, rw, rh = max(rostos, key=lambda r: r[2] * r[3])
                pontos.append((idx / fps, (x + rw / 2) / 480))
                achou += 1
            else:
                pontos.append((idx / fps, None))
    except Exception as e:
        print(f"   ⚠ detecção de rosto falhou ({e}) — usando o centro.")
        return None
    finally:
        cap.release()
    if not pontos or achou < len(pontos) * 0.3:
        return None
    ultimo = next(c for _, c in pontos if c is not None)
    cheios = []
    for t, c in pontos:
        ultimo = c if c is not None else ultimo
        cheios.append((t, ultimo))
    xs = _suavizar_segmento_camera([c for _, c in cheios])
    return [(t, x) for (t, _), x in zip(cheios, xs)]


def expr_crop_x(trajetoria, largura_escalada, largura_saida=cortes.LARGURA, chaves=1.0):
    """Expressão do ffmpeg pro 'x' do crop, interpolando a trajetória ao longo do tempo
    com curva suave ease-in-out (smoothstep u²*(3-2*u)) em vez de reta dura."""
    folga = largura_escalada - largura_saida
    if folga <= 0 or not trajetoria:
        return "0"
    pts, prox = [], -1.0
    for t, c in trajetoria:
        if t >= prox:
            pts.append((t, min(folga, max(0, c * largura_escalada - largura_saida / 2))))
            prox = t + chaves
    if len(pts) == 1:
        return f"{pts[0][1]:.1f}"
    expr = f"{pts[-1][1]:.1f}"
    for (t0, x0), (t1, x1) in reversed(list(zip(pts, pts[1:]))):
        dx = x1 - x0
        dt = max(0.05, t1 - t0)
        if abs(dx) < 1.5:
            seg = f"{x0:.1f}"
        else:
            # Smoothstep ease-in-out: u = (t-t0)/dt -> u*u*(3 - 2*u)
            u = f"((t-{t0:.2f})/{dt:.2f})"
            seg = f"{x0:.1f}+{dx:.1f}*{u}*{u}*(3-2*{u})"
        expr = f"if(lt(t,{t1:.2f}),{seg},{expr})"
    return f"if(lt(t,{pts[0][0]:.2f}),{pts[0][1]:.1f},{expr})"


# ---------------- som (síntese multicamada de estúdio, sem direitos autorais) ----------------
def _salvar_wav_estereo(destino: Path, esq, dir_, sr=44100):
    import numpy as np
    est = np.empty(len(esq) * 2, dtype=np.int16)
    est[0::2] = np.clip(esq * 32767.0, -32768, 32767).astype(np.int16)
    est[1::2] = np.clip(dir_ * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(est.tobytes())
    return destino


def gerar_boom(pasta: Path):
    """Cria efeito sonoro de impacto cinematográfico ('sub-drop + punch' encorpado em estéreo),
    substituindo a senoide simples por síntese multicamada com harmônicos e ataque limpo."""
    destino = pasta / "boom.wav"
    try:
        import numpy as np
        sr = 44100
        dur = 1.15
        t = np.linspace(0, dur, int(sr * dur), endpoint=False, dtype=np.float32)
        # Camada 1: Sub-bass profundo com queda exponencial de fase (145 Hz -> 35 Hz)
        freq_sub = 35.0 + 110.0 * np.exp(-8.5 * t)
        fase_sub = 2.0 * np.pi * np.cumsum(freq_sub) / sr
        sub = np.sin(fase_sub) * np.exp(-3.6 * t)
        # Camada 2: Segundo harmônico quente + leve saturação suave (tanh)
        harm = np.sin(2.0 * fase_sub + 0.3) * 0.38 * np.exp(-6.0 * t)
        # Camada 3: Punch inicial (transiente de peito 220 Hz -> 50 Hz nos primeiros 120ms)
        fase_punch = 2.0 * np.pi * np.cumsum(50.0 + 170.0 * np.exp(-28.0 * t)) / sr
        punch = np.sin(fase_punch) * 0.55 * np.exp(-18.0 * t)
        # Camada 4: Textura grave filtrada no ataque (sem chiado agudo)
        rng = np.random.default_rng(42)
        ruido = rng.standard_normal(len(t)).astype(np.float32)
        kernel = np.ones(48, dtype=np.float32) / 48.0
        thump_ar = np.convolve(ruido, kernel, mode="same") * 0.35 * np.exp(-22.0 * t)
        ataque = np.minimum(1.0, t / 0.006)
        corpo = np.tanh((sub + harm + punch + thump_ar) * 1.45) * ataque * 0.92
        # Alargamento estéreo sutil nas frequências médias do impacto
        atraso = int(0.0006 * sr)
        dir_ = np.concatenate([ np.zeros(atraso, dtype=np.float32), corpo[:-atraso] ]) * 0.96 + sub * 0.04
        return _salvar_wav_estereo(destino, corpo, dir_, sr=sr)
    except Exception:
        cortes.rodar(["ffmpeg", "-y", "-f", "lavfi", "-i",
                      "aevalsrc='0.95*sin(2*PI*(48+110*exp(-9*t))*t)*exp(-4.5*t)':s=44100:d=1.1",
                      "-ac", "2", str(destino)])
        return destino


def gerar_whoosh(pasta: Path, duracao=0.55):
    """Efeito 'whoosh' cinematográfico em estéreo (varredura de filtro + pan estéreo),
    usado na transição do gancho inicial e nos cartões da compilação."""
    destino = pasta / f"whoosh_{int(round(duracao * 100)):03d}.wav"
    if destino.exists():
        return destino
    try:
        import numpy as np
        sr = 44100
        n = max(1024, int(sr * duracao))
        t = np.linspace(0.0, 1.0, n, endpoint=False, dtype=np.float32)
        rng = np.random.default_rng(108)
        ruido = rng.standard_normal(n).astype(np.float32)
        # Suavização em duas bandas + tom de vento Doppler (120 Hz -> 380 Hz -> 95 Hz)
        k1 = np.hanning(36).astype(np.float32); k1 /= k1.sum()
        k2 = np.hanning(140).astype(np.float32); k2 /= k2.sum()
        banda_alta = np.convolve(ruido, k1, mode="same")
        banda_grave = np.convolve(ruido, k2, mode="same")
        env = np.sin(np.pi * (t ** 0.85)) ** 2.2
        freq_vento = 90.0 + 260.0 * env
        fase = 2.0 * np.pi * np.cumsum(freq_vento) / sr
        sopro = (banda_alta * (0.35 + 0.65 * env) + banda_grave * 0.8 + np.sin(fase) * 0.28) * env
        sopro = np.tanh(sopro * 1.3) * 0.65
        pan_e = np.clip(1.0 - 0.45 * t, 0.4, 1.0)
        pan_d = np.clip(0.55 + 0.45 * t, 0.4, 1.0)
        return _salvar_wav_estereo(destino, sopro * pan_e, sopro * pan_d, sr=sr)
    except Exception:
        cortes.rodar(["ffmpeg", "-y", "-f", "lavfi", "-i",
                      f"aevalsrc='0.4*sin(2*PI*(120+240*sin(PI*t/{duracao:.2f}))*t)*sin(PI*t/{duracao:.2f})':s=44100:d={duracao:.2f}",
                      "-ac", "2", str(destino)])
        return destino


def gerar_pop(pasta: Path):
    """Efeito curto e limpo ('pop' de estúdio) para aparição de elementos visuais."""
    destino = pasta / "pop.wav"
    if destino.exists():
        return destino
    import numpy as np
    sr = 44100
    dur = 0.14
    t = np.linspace(0, dur, int(sr * dur), endpoint=False, dtype=np.float32)
    freq = 280.0 + 620.0 * (1.0 - np.exp(-32.0 * t))
    fase = 2.0 * np.pi * np.cumsum(freq) / sr
    onda = np.sin(fase) * np.exp(-24.0 * t) * np.minimum(1.0, t / 0.003) * 0.55
    return _salvar_wav_estereo(destino, onda, onda, sr=sr)


def correcao_exposicao(video: Path, alvo=62):
    """Mede o brilho médio do vídeo (1 quadro a cada 3 s); se for escuro (gameplay noturno, podcast
    mal iluminado), devolve um levantamento SUAVE de gama pro render. Vídeo bem exposto: ''."""
    import re as _re
    import statistics
    import subprocess

    def medir(args, filtro=""):
        r = subprocess.run(["ffmpeg", "-v", "info", "-nostdin", *args, "-i", str(video), "-vf",
                            filtro + "scale=160:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                            "-fps_mode", "passthrough", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180, creationflags=cortes.SEM_JANELA)
        return [float(v) for v in _re.findall(r"YAVG=([0-9.]+)", r.stderr)]
    try:
        valores = medir(["-skip_frame", "nokey"])  # só os quadros-chave: mede em ~1 s
        if len(valores) < 3:                       # arquivo com poucos quadros-chave: mede decodificando
            valores = medir([], "fps=1,")
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    if len(valores) < 3:                           # vídeo curto demais pra medir com confiança
        return ""
    mediana = statistics.median(valores)           # mediana: umas cenas escuras não disparam o ajuste
    if mediana >= alvo:
        return ""
    gama = min(1.22, 1 + (alvo - mediana) / 160)
    brilho = min(0.04, (alvo - mediana) / 900)
    return f",eq=gamma={gama:.2f}:brightness={brilho:.3f}"


# ---------------- cortar trechos (com micro-fade de áudio e alta nitidez) ----------------
def cortar_intervalos_mantidos(video: Path, pasta: Path, manter, nome="editado.mp4"):
    """Recorta o vídeo mantendo exatamente a lista de intervalos [(a, b), ...] em UMA única passada.
    Ajusta os pontos de corte do áudio no zero-crossing quando possível para evitar estalos."""
    manter = [(float(a), float(b)) for a, b in manter if b - a > 0.05]
    if not manter:
        return video
    dur = cortes.duracao_video(video)
    if len(manter) == 1 and manter[0][0] <= 0.05 and manter[0][1] >= dur - 0.05:
        return video
    saida = pasta / nome
    if len(manter) == 1:
        a, b = manter[0]
        d = max(0.06, b - a)
        cmd = ["ffmpeg", "-y", "-ss", f"{a:.4f}", "-i", str(video), "-t", f"{d:.4f}"]
        if cortes.tem_audio(video):
            af = f"afade=t=in:st=0:d=0.015,afade=t=out:st={max(0.0, d - 0.02):.4f}:d=0.02"
            cmd += ["-af", af, "-c:a", "aac", "-b:a", "192k"]
        cmd += [*cortes.args_encoder_video(intermediario=True), "-avoid_negative_ts", "make_zero", str(saida)]
        cortes.rodar(cmd)
        return saida
    sel = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in manter)
    fim_max = manter[-1][1] + 0.15
    ate_args = ["-to", f"{fim_max:.3f}"] if dur and fim_max < dur - 0.5 else []
    if cortes.tem_audio(video) and 1 < len(manter) <= 160:
        # cada pedaço de áudio ganha um micro-fade de 12 ms na entrada e na saída: as emendas
        # (silêncio/vício cortado) ficam sem "estalo"
        f = 0.012
        partes = [f"[0:v]select='{sel}',setpts=N/FRAME_RATE/TB[v]", f"[0:a]asplit={len(manter)}" +
                  "".join(f"[s{i}]" for i in range(len(manter)))]
        for i, (a, b) in enumerate(manter):
            d = b - a
            fd = min(f, d / 3)
            partes.append(f"[s{i}]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS,"
                          f"afade=t=in:st=0:d={fd:.4f},afade=t=out:st={max(0.0, d - fd):.4f}:d={fd:.4f}[a{i}]")
        partes.append("".join(f"[a{i}]" for i in range(len(manter))) + f"concat=n={len(manter)}:v=0:a=1[a]")
        cmd = ["ffmpeg", "-y", *ate_args, "-i", str(video), "-filter_complex", ";".join(partes), "-map", "[v]", "-map", "[a]",
               "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd = ["ffmpeg", "-y", *ate_args, "-i", str(video), "-vf", f"select='{sel}',setpts=N/FRAME_RATE/TB"]
        if cortes.tem_audio(video):
            dur_final = max(0.1, sum(b - a for a, b in manter))
            af = (f"aselect='{sel}',asetpts=N/SR/TB,"
                  f"afade=t=in:st=0:d=0.015,afade=t=out:st={max(0.0, dur_final - 0.02):.3f}:d=0.02")
            cmd += ["-af", af, "-c:a", "aac", "-b:a", "192k"]
    cmd += [*cortes.args_encoder_video(intermediario=True), str(saida)]
    cortes.rodar(cmd)
    return saida


def cortar_intervalos(video: Path, pasta: Path, remover, nome="editado.mp4"):
    """Remove os intervalos [(a, b), ...] do vídeo. Devolve o vídeo novo."""
    dur = cortes.duracao_video(video)
    manter = inverter_intervalos(dur, remover, minimo=0.05)
    return cortar_intervalos_mantidos(video, pasta, manter, nome=nome)


def mapear_tempo(t, removidos):
    """Novo tempo de 't' depois de tirar os intervalos 'removidos'."""
    uniao = unir_intervalos(removidos)
    return max(0, t - sum(min(b, t) - a for a, b in uniao if a < t))


# ---------------- vícios de linguagem ----------------
VICIOS_SEMPRE = {"hum", "hmm", "hm", "hã", "ahn", "ãh", "ãã", "éé", "ééé", "éééé", "eeh", "ehh",
                 "eh", "uh", "uhm", "umm"}


def _limpa(t):
    return re.sub(r"[^\wáéíóúâêôãõç]", "", t.lower())


def eh_vicio(palavra, anterior=None):
    """Conservador: 'é' só conta quando arrastado ('ééé', ou falado devagar); 'tipo' e 'né'
    só quando soltos (com vírgula/interrogação). Assim não estraga 'ele é louco'."""
    bruto = palavra["t"].strip()
    limpo = _limpa(bruto)
    if not limpo:
        return False
    dur = palavra["fim"] - palavra["ini"]
    if limpo in VICIOS_SEMPRE or re.fullmatch(r"é{2,}|e{3,}|a{3,}|hu+m+", limpo):
        return True
    if limpo in ("é", "e") and (dur >= 0.55 or "..." in bruto):
        return True
    if limpo == "tipo" and (bruto.endswith((",", "...")) or (anterior and anterior["t"].endswith(","))):
        return True
    if limpo == "né" and bruto.endswith(("?", ",", "...")):
        return True
    return False


def intervalos_sem_vicios(palavras):
    """Calcula os intervalos de vícios a remover e devolve
    (novas_palavras, indices_mantidos, intervalos_remover, segundos_removidos) sem recodificar vídeo."""
    if len(palavras) < 4:
        return palavras, list(range(len(palavras))), [], 0.0
    remover, manter = [], []
    for i, p in enumerate(palavras):
        if eh_vicio(p, palavras[i - 1] if i else None):
            a = max(p["ini"] - 0.03, palavras[i - 1]["fim"] if i else 0.0)
            b = min(p["fim"] + 0.03, palavras[i + 1]["ini"] if i + 1 < len(palavras) else p["fim"] + 0.03)
            if b - a > 0.08:
                remover.append((a, b))
                continue
        manter.append(i)
    if not remover or len(manter) < len(palavras) * 0.6:
        return palavras, list(range(len(palavras))), [], 0.0
    total = sum(b - a for a, b in remover)
    novas = [{**palavras[i], "ini": round(mapear_tempo(palavras[i]["ini"], remover), 2),
              "fim": round(mapear_tempo(palavras[i]["fim"], remover), 2)} for i in manter]
    return novas, manter, remover, round(total, 3)


def tirar_vicios(video: Path, pasta: Path, palavras):
    """Corta 'é…', 'tipo,', 'né?', 'hum'… Devolve (vídeo, palavras sem os vícios e com tempos
    ajustados, índices mantidos, segundos removidos)."""
    novas, manter, remover, total = intervalos_sem_vicios(palavras)
    if not remover:
        return video, palavras, manter, 0.0
    novo = cortar_intervalos(video, pasta, remover, "sem_vicios.mp4")
    return novo, novas, manter, total


# ---------------- gancho no começo ----------------
def janela_gancho(palavras, gancho_t, maximo=3.0):
    """Trecho de ~2s a partir do gancho, terminando no fim de uma palavra."""
    a = max(0.0, gancho_t - 0.35)
    b = a + 2.0
    for p in palavras:
        if p["ini"] >= gancho_t and p["fim"] >= gancho_t + 1.4:
            b = p["fim"] + 0.12
            break
    return a, min(b, a + maximo)


def prefixar_gancho(video: Path, pasta: Path, a, b):
    """Coloca o trecho [a, b] no começo do vídeo (prévia do momento mais forte),
    com micro-fade de áudio e efeito sonoro 'whoosh' na transição para o início."""
    saida = pasta / "com_gancho.mp4"
    dur_gancho = max(0.2, b - a)
    if cortes.tem_audio(video):
        whoosh = gerar_whoosh(pasta, duracao=0.45)
        ms_w = max(0, int((dur_gancho - 0.22) * 1000))
        filtro = (f"[0:v]split[v1][v2];[0:a]asplit[a1][a2];"
                  f"[v1]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[gv];"
                  f"[a1]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d=0.02,afade=t=out:st={max(0, dur_gancho - 0.12):.3f}:d=0.12[ga];"
                  f"[v2]setpts=PTS-STARTPTS[rv];"
                  f"[a2]asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.03[ra];"
                  f"[gv][ga][rv][ra]concat=n=2:v=1:a=1[v][ac];"
                  f"[1:a]adelay={ms_w}|{ms_w},volume=0.55[aw];"
                  f"[ac][aw]amix=inputs=2:duration=first:normalize=0[a]")
        entradas_extra = ["-i", str(whoosh)]
        mapa = ["-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    else:
        filtro = (f"[0:v]split[v1][v2];[v1]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[gv];"
                  f"[v2]setpts=PTS-STARTPTS[rv];[gv][rv]concat=n=2:v=1:a=0[v]")
        entradas_extra = []
        mapa = ["-map", "[v]"]
    cortes.rodar(["ffmpeg", "-y", "-i", str(video), *entradas_extra, "-filter_complex", filtro, *mapa,
                  *cortes.args_encoder_video(intermediario=True), str(saida)])
    return saida


# ================================================================
# Rostos, layouts automáticos (podcast / jogo+facecam) e quem fala
# ================================================================
def analisar_rostos(video: Path, passo=0.5, largura=640):
    """UMA passada pelo vídeo: todos os rostos de cada amostra (normalizados 0-1).
    Serve pra seguir o rosto, escolher o layout e tirar legenda/faixa de cima dos rostos."""
    try:
        import cv2
    except ImportError:
        return None
    detectar = _criar_detector()
    if not detectar:
        return None
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    amostras, cortes_cena, anterior_cena = [], [], None
    try:
        for idx, frame in amostras_video(cap, passo):
            h, w = frame.shape[:2]
            alt = int(largura * h / w)
            peq = cv2.resize(frame, (largura, alt))
            mini = cv2.resize(cv2.cvtColor(peq, cv2.COLOR_BGR2GRAY), (32, 18))
            if anterior_cena is not None and float(cv2.absdiff(mini, anterior_cena).mean()) > 40:
                cortes_cena.append(idx / fps)
            anterior_cena = mini
            rostos = []
            for (x, y, rw, rh) in detectar(peq):
                rostos.append(((x + rw / 2) / largura, (y + rh / 2) / alt, rw / largura, rh / alt))
            amostras.append((idx / fps, rostos))
    except Exception as e:
        print(f"   ⚠ análise de rostos falhou ({e})")
        return None
    finally:
        cap.release()
    return {"w": W, "h": H, "amostras": amostras, "cortes_cena": cortes_cena}


def trajetoria_de(analise):
    """Caminho suave do maior rosto (pra câmera acompanhar) a partir da análise,
    com suavização bidirecional entre cortes de cena."""
    if not analise or not analise["amostras"]:
        return None
    pontos, anterior = [], None
    cortes_cena = analise.get("cortes_cena", [])
    for t, rostos in analise["amostras"]:
        mudou = any(abs(t - c) < 0.25 for c in cortes_cena)
        if mudou:
            anterior = None
        if not rostos:
            pontos.append((t, None))
            continue
        maior = max(rostos, key=lambda f: f[2] * f[3])
        escolhido = maior
        if anterior is not None:
            proximo = min(rostos, key=lambda f: abs(f[0] - anterior[0]) + abs(f[1] - anterior[1]))
            if abs(proximo[0] - anterior[0]) < 0.2 and proximo[2] * proximo[3] >= maior[2] * maior[3] * 0.5:
                escolhido = proximo
        anterior = escolhido
        pontos.append((t, escolhido[0]))
    if sum(1 for _, c in pontos if c is not None) < len(pontos) * 0.3:
        return None
    ultimo = next(c for _, c in pontos if c is not None)
    blocos, bloco_atual = [], []
    for t, c in pontos:
        ultimo = c if c is not None else ultimo
        if bloco_atual and any(abs(t - cc) < 0.25 for cc in cortes_cena):
            blocos.append(bloco_atual)
            bloco_atual = []
        bloco_atual.append((t, ultimo))
    if bloco_atual:
        blocos.append(bloco_atual)
    suave = []
    for bl in blocos:
        xs = _suavizar_segmento_camera([c for _, c in bl])
        suave.extend((t, x) for (t, _), x in zip(bl, xs))
    return suave


def _mediana_box(boxes):
    import statistics as st
    return tuple(st.median(b[i] for b in boxes) for i in range(4))


def detectar_layout(analise):
    """'podcast' (2 pessoas lado a lado), 'jogo' (câmera pequena num canto) ou 'normal'."""
    if not analise or len(analise["amostras"]) < 6:
        return "normal", None
    am = analise["amostras"]
    dois, cantos, grandes_centro = [], [], 0
    for t, rostos in am:
        bons = sorted([f for f in rostos if f[2] >= 0.05], key=lambda f: -f[2] * f[3])[:2]
        if len(bons) == 2 and abs(bons[0][0] - bons[1][0]) >= 0.22 and \
                min(b[2] for b in bons) / max(b[2] for b in bons) > 0.45:
            dois.append(sorted(bons, key=lambda f: f[0]))
        for f in rostos:
            cx, cy, bw, bh = f
            if bw >= 0.16:
                grandes_centro += 1
                break
        for f in rostos:
            cx, cy, bw, bh = f
            if bw <= 0.13 and (cx < 0.33 or cx > 0.67) and (cy < 0.42 or cy > 0.58):
                cantos.append(f)
                break
    n = len(am)
    if len(dois) >= 0.45 * n:
        return "podcast", {"A": _mediana_box([d[0] for d in dois]), "B": _mediana_box([d[1] for d in dois])}
    if len(cantos) >= 0.5 * n and grandes_centro < 0.3 * n:
        cam = _mediana_box(cantos)
        perto = sum(1 for f in cantos if abs(f[0] - cam[0]) < 0.08 and abs(f[1] - cam[1]) < 0.08)
        if perto >= 0.7 * len(cantos):                # câmera parada num lugar = facecam
            return "jogo", {"cam": cam}
    return "normal", None


def recorte(box, W, H, aspecto, zoom=3.0, sobe=0.10):
    """Retângulo (w, h, x, y) em pixels com a proporção do painel, centrado no rosto."""
    cx, cy, bw, bh = box
    ch = min(H, max(bh * H * zoom, H * 0.28))
    cw = ch * aspecto
    if cw > W:
        cw, ch = W, W / aspecto
    x = min(max(0, cx * W - cw / 2), W - cw)
    y = min(max(0, cy * H - ch / 2 + sobe * ch), H - ch)
    return int(cw) // 2 * 2, int(ch) // 2 * 2, int(x), int(y)


def recorte_centro(W, H, aspecto):
    ch = H
    cw = ch * aspecto
    if cw > W:
        cw, ch = W, W / aspecto
    return int(cw) // 2 * 2, int(ch) // 2 * 2, int((W - cw) / 2), int((H - ch) / 2)


def falantes(video: Path, boxA, boxB, fps_analise=5, minimo=0.8, palavras=None):
    """Quem está falando, pelo movimento da boca de cada um. Devolve [(ini, fim, 'A'|'B'), ...]."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    passo = max(1, int(round(fps / fps_analise)))

    def boca(frame, box):
        cx, cy, bw, bh = box
        x0, x1 = int((cx - bw * 0.3) * W), int((cx + bw * 0.3) * W)
        y0, y1 = int((cy + bh * 0.05) * H), int((cy + bh * 0.55) * H)
        reg = frame[max(0, y0):max(1, y1), max(0, x0):max(1, x1)]
        if reg.size == 0:
            return None
        return cv2.resize(cv2.cvtColor(reg, cv2.COLOR_BGR2GRAY), (32, 20)).astype("float32")

    tempos, mA, mB, antes = [], [], [], (None, None)
    i = 0
    try:
        while True:
            if not cap.grab():
                break
            if i % passo == 0:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                a, b = boca(frame, boxA), boca(frame, boxB)
                if antes[0] is not None and a is not None and b is not None:
                    tempos.append(i / fps)
                    mA.append(float(np.abs(a - antes[0]).mean()))
                    mB.append(float(np.abs(b - antes[1]).mean()))
                antes = (a, b)
            i += 1
    finally:
        cap.release()
    if len(tempos) < 5:
        return []
    k = 7
    sA = np.convolve(mA, np.ones(k) / k, mode="same")
    sB = np.convolve(mB, np.ones(k) / k, mode="same")
    from identificacao_falante import vetores_voz, associar
    import tempfile
    mascara = [palavras is not None and any(p['ini'] - .1 <= t <= p['fim'] + .1 for p in palavras) for t in tempos]
    try:
        with tempfile.TemporaryDirectory(prefix='voz_pessoa_') as temp:
            wav = Path(temp) / 'voz.wav'
            cortes.extrair_audio(video, wav)
            vetores = vetores_voz(cortes.ler_wav(wav), tempos)
        quem, relatorio = associar(vetores, sA[:len(tempos)], sB[:len(tempos)], mascara)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as e:
        quem = [None] * len(tempos)
        relatorio = dict(confiavel=False, motivo=str(e)[:200])
    if not relatorio.get('confiavel'):
        # Voz inconclusiva: volta pro método simples (quem mexe mais a boca), que funciona bem
        # na maioria dos podcasts. Só marca quando um lado mexe claramente mais que o outro.
        atual, quem = "A" if sA[0] >= sB[0] else "B", []
        for va, vb in zip(sA, sB):
            if va > vb * 1.15:
                atual = "A"
            elif vb > va * 1.15:
                atual = "B"
            quem.append(atual)
        quem = quem[:len(tempos)]
        relatorio = dict(relatorio, metodo_usado='movimento_da_boca')
    from infraestrutura import salvar_json
    salvar_json(Path(video).parent / 'falantes_av.json', relatorio)
    segs = []
    ini = tempos[0]
    for j in range(1, len(quem)):
        if quem[j] != quem[j - 1]:
            segs.append([ini, tempos[j], quem[j - 1]])
            ini = tempos[j]
    segs.append([ini, tempos[-1] + 1.0, quem[-1]])
    # junta trocas curtas demais (pisca-pisca)
    limpos = []
    for s in segs:
        if limpos and (s[2] == limpos[-1][2] or (s[1] - s[0] < minimo and limpos[-1][2] is not None)):
            limpos[-1][1] = s[1]
        else:
            limpos.append(s)
    limpos[0][0] = 0.0
    return [(a, b, q if b - a >= minimo else None) for a, b, q in limpos]


def foco_podcast(segs, minimo_solo=3.5):
    """Identifica trechos longos onde um único falante domina a palavra (≥ minimo_solo segundos)
    para aplicar zoom/foco dinâmico ou alternância de câmera no modo podcast."""
    foco_a, foco_b = [], []
    for a, b, q in segs or []:
        if b - a >= minimo_solo:
            if q == "A":
                foco_a.append((round(a, 2), round(b, 2)))
            elif q == "B":
                foco_b.append((round(a, 2), round(b, 2)))
    return {"foco_top": foco_a, "foco_bot": foco_b}


def quem_fala(segs, t):
    for a, b, q in segs or []:
        if a <= t < b:
            return q
    return None


# ================================================================
# Revisor sem IA: frase completa e legenda longe dos rostos
# ================================================================
FIM_FRASE = re.compile(r"[.!?…]\s*$")


def ajustar_frase(palavras, textos, duracao):
    """Se o corte começa/termina no meio de uma frase, acha o ponto certo perto da borda.
    Devolve (corta_inicio, corta_fim) em segundos (0 = não mexe)."""
    if len(palavras) < 8 or duracao < 25:
        return 0.0, 0.0
    ini_corte = fim_corte = 0.0
    # entrou falando no meio da frase: 1ª palavra colada no início E em minúscula (o Whisper
    # escreve início de frase com maiúscula) — ou marcado explicitamente como incompleto
    primeira = palavras[0]["t"].lstrip("\"'¿¡-— ")
    meio = palavras[0]["ini"] < 0.3 and primeira[:1].islower()
    if palavras[0].get("inicio_incompleto", meio):
        for i in range(1, len(palavras)):
            if palavras[i]["ini"] > 4.5:
                break
            if FIM_FRASE.search(textos[i - 1]) and palavras[i]["ini"] - 0.15 > 0.5:
                ini_corte = palavras[i]["ini"] - 0.15
                break
    ult = palavras[-1]
    if ult.get("fim_incompleto", duracao - ult["fim"] < 0.45) and not FIM_FRASE.search(textos[-1]):   # saiu falando
        for i in range(len(palavras) - 2, -1, -1):
            if palavras[i]["fim"] < duracao - 6:
                break
            if FIM_FRASE.search(textos[i]):
                fim_corte = duracao - (palavras[i]["fim"] + 0.35)
                break
    if duracao - ini_corte - fim_corte < 20:
        return 0.0, 0.0
    return round(ini_corte, 2), round(max(0.0, fim_corte), 2)


def margem_legenda_segura(rostos_px, margem, tamanho, altura_tela=1920, minimo=60):
    """rostos_px = [(y_topo, y_base), ...] dos rostos na tela final. Se a legenda cair em cima
    de um rosto em boa parte do vídeo, devolve uma margem nova (embaixo ou em cima do rosto)."""
    if not rostos_px:
        return margem
    faixa_ini = altura_tela - margem - tamanho * 1.35
    faixa_fim = altura_tela - margem
    batem = [r for r in rostos_px if r[0] < faixa_fim and r[1] > faixa_ini]
    if len(batem) < 0.3 * len(rostos_px):
        return margem
    base = sorted(r[1] for r in batem)[int(len(batem) * 0.8) - 1 if len(batem) > 1 else 0]
    topo = sorted(r[0] for r in batem)[int(len(batem) * 0.2)]
    abaixo = altura_tela - (base + tamanho * 1.45)
    if abaixo >= minimo:
        return int(abaixo)
    acima = altura_tela - topo + 25
    return int(min(acima, altura_tela - 1000))
