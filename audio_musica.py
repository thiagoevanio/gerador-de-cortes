"""Detector de música de fundo (3.13), sem IA e sem internet.

Música com direitos autorais tocando no fundo de uma live (rádio, playlist, trilha de jogo) é o que
mais faz o YouTube mutar, bloquear ou tirar a monetização de um corte. O detector olha o áudio nos
intervalos entre as falas (os tempos vêm da transcrição): se ali continua havendo som alto e tonal
(notas sustentadas), é sinal de música. Ruído de sala, chiado e silêncio não são tonais; a fala some
nesses intervalos. É uma estimativa: serve pra avisar e você conferir antes de postar.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

TAXA = 16000
JANELA = 1024            # 64 ms
PASSO = 512              # 32 ms
MARGEM_FALA = 0.10       # segundos em volta de cada palavra que ainda contam como fala
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ler_audio(video: Path, taxa=TAXA):
    """Áudio mono em float32 (-1..1) direto do ffmpeg, sem arquivo temporário."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(taxa),
                        "-f", "s16le", "-"], capture_output=True, creationflags=SEM_JANELA)
    if r.returncode != 0 or not r.stdout:
        return None
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def medidas(audio, taxa=TAXA):
    """Por quadro de 64 ms: volume (dB), planura espectral (0 = tonal, 1 = ruído) e estabilidade
    (o quanto o espectro se parece com o do quadro anterior: nota sustentada fica alta)."""
    import numpy as np
    n = 1 + max(0, (len(audio) - JANELA) // PASSO)
    if len(audio) < JANELA:
        return np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0)
    idx = np.arange(JANELA)[None, :] + PASSO * np.arange(n)[:, None]
    quadros = audio[idx] * np.hanning(JANELA)[None, :].astype(np.float32)
    rms = np.sqrt((audio[idx] ** 2).mean(axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    espectro = np.abs(np.fft.rfft(quadros, axis=1)) ** 2
    freqs = np.fft.rfftfreq(JANELA, 1 / taxa)
    banda = espectro[:, (freqs >= 150) & (freqs <= 5000)] + 1e-12
    planura = np.exp(np.log(banda).mean(axis=1)) / banda.mean(axis=1)
    log_esp = np.log(banda)
    log_esp = log_esp - log_esp.mean(axis=1, keepdims=True)
    norma = np.linalg.norm(log_esp, axis=1) + 1e-9
    estab = np.zeros(n)
    estab[1:] = (log_esp[1:] * log_esp[:-1]).sum(axis=1) / (norma[1:] * norma[:-1])
    tempos = (np.arange(n) * PASSO + JANELA / 2) / taxa
    return tempos, db, planura, estab


def notas_sustentadas(audio, taxa=TAXA, min_quadros=12, min_picos=2):
    """Fração do tempo com 2+ picos de frequência parados por 0,4s ou mais (nota sustentada).
    A voz muda de tom o tempo todo e não fica assim; instrumento e trilha ficam. Vale até por baixo da fala."""
    quadros = quadros_com_notas(audio, taxa, min_quadros, min_picos)
    return float(quadros.mean()) if len(quadros) else 0.0


def quadros_com_notas(audio, taxa=TAXA, min_quadros=12, min_picos=2):
    """Por quadro de 64 ms (os mesmos de medidas()): True onde há nota sustentada."""
    import numpy as np
    n = 1 + (len(audio) - JANELA) // PASSO if len(audio) >= JANELA else 0
    if n < min_quadros:
        return np.zeros(max(0, n), dtype=bool)
    idx = np.arange(JANELA)[None, :] + PASSO * np.arange(n)[:, None]
    esp = np.abs(np.fft.rfft(audio[idx] * np.hanning(JANELA)[None, :].astype(np.float32), axis=1)) ** 2
    freqs = np.fft.rfftfreq(JANELA, 1 / taxa)
    e = 10 * np.log10(esp[:, (freqs >= 100) & (freqs <= 2500)] + 1e-12)
    picos = (e[:, 1:-1] > e[:, :-2]) & (e[:, 1:-1] > e[:, 2:]) & (e[:, 1:-1] > np.median(e, axis=1, keepdims=True) + 12)
    picos = np.pad(picos, ((0, 0), (1, 1)))
    alargado = picos | np.roll(picos, 1, axis=1) | np.roll(picos, -1, axis=1)     # tolera ±1 faixa
    seguidos = np.zeros(alargado.shape, dtype=np.int32)
    for i in range(1, n):
        seguidos[i] = np.where(alargado[i], seguidos[i - 1] + 1, 0)
    return ((seguidos >= min_quadros) & picos).sum(axis=1) >= min_picos


def avaliar(audio, palavras, taxa=TAXA, limiar=0.45, limiar_notas=0.10):
    """{'provavel', 'confianca', 'fracao', 'notas', 'trechos': [(ini, fim)], 'motivo'}.
    Dois sinais: som tonal contínuo nos intervalos entre as falas e notas sustentadas no áudio todo."""
    import numpy as np
    tempos, db, planura, estab = medidas(audio, taxa)
    if len(tempos) == 0:
        return {"provavel": False, "confianca": "sem áudio", "fracao": 0.0, "notas": 0.0, "trechos": [],
                "motivo": "sem áudio"}
    com_notas = quadros_com_notas(audio, taxa)
    notas = round(float(com_notas.mean()), 3) if len(com_notas) else 0.0
    fala = np.zeros(len(tempos), dtype=bool)
    for p in palavras or []:
        try:
            a, b = float(p["ini"]) - MARGEM_FALA, float(p["fim"]) + MARGEM_FALA
        except (KeyError, TypeError, ValueError):
            continue
        fala |= (tempos >= a) & (tempos <= b)
    if fala.sum() >= 10:
        ref = float(np.median(db[fala]))                     # volume típico da fala
    else:
        ref = float(np.percentile(db, 90))
    vao = ~fala
    alto = db > max(ref - 24.0, -50.0)                       # som de verdade, não chiado/silêncio
    tonal = planura < 0.30
    sustentado = estab > 0.80
    musical = vao & alto & tonal & sustentado
    fracao = float(musical.sum() / vao.sum()) if vao.sum() >= 25 else 0.0   # menos de ~1s sem fala: não conta
    # onde: quadros com nota sustentada ou som musical entre as falas, juntando buracos de até 0,6s
    onde = musical | (com_notas if len(com_notas) == len(tempos) else False)
    trechos, ini, ultimo = [], None, None
    for t, m in zip(tempos, onde):
        if m:
            if ini is None or t - ultimo > 0.6:
                if ini is not None and ultimo - ini >= 1.5:
                    trechos.append((round(ini, 1), round(ultimo, 1)))
                ini = t
            ultimo = t
    if ini is not None and ultimo - ini >= 1.5:
        trechos.append((round(ini, 1), round(ultimo, 1)))
    provavel = fracao >= limiar or notas >= limiar_notas
    confianca = ("alta" if fracao >= 0.65 or notas >= 0.30 else "média") if provavel else "baixa"
    if provavel:
        motivo = (f"notas sustentadas em {notas:.0%} do tempo e som tonal em {fracao:.0%} dos intervalos entre as "
                  "falas (cara de música de fundo)")
    else:
        motivo = f"sem sinal claro de música (notas sustentadas em {notas:.0%} do tempo)"
    return {"provavel": provavel, "confianca": confianca, "fracao": round(fracao, 3), "notas": notas,
            "trechos": trechos[:8], "motivo": motivo}


def detectar(video: Path, palavras):
    """Atalho: lê o áudio do vídeo e avalia. Nunca levanta erro (devolve None se não der)."""
    try:
        audio = ler_audio(video)
        if audio is None or len(audio) < TAXA:
            return None
        return avaliar(audio, palavras)
    except Exception:
        return None
