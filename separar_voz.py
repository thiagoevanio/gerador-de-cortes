"""🎵 Tirar a música de fundo da fonte (Demucs, IA de separação de voz e música — roda no PC).

Pra que serve: corte de live com música tocando. A música com direitos autorais faz o TikTok tirar o
som do vídeo e o YouTube bloquear/desmonetizar. A IA separa a VOZ do resto e o corte segue só com a voz
(a música de fundo do próprio programa, se ligada, entra depois, por cima).

É pesado: baixa ~1 GB uma vez (a IA + o motor dela) e, num i5 sem placa de vídeo, leva alguns minutos
por corte. Por isso é opcional (⚙ Qualidade) e, se algo falhar, o corte segue com o som original.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
import wave
from pathlib import Path

import cortes

INDICE_TORCH = "https://download.pytorch.org/whl/cpu"       # motor só de processador (bem menor)
MODELO = "htdemucs"
_modelo = None


def instalado() -> bool:
    return all(importlib.util.find_spec(m) is not None for m in ("torch", "demucs"))


def _python():
    return sys.executable.replace("pythonw.exe", "python.exe")


def instalar(log=print) -> bool:
    """Baixa o motor (torch, versão só processador) e o Demucs. Uma vez só."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    passos = [["-m", "pip", "install", "--disable-pip-version-check", "-q", "torch", "torchaudio",
               "--index-url", INDICE_TORCH],
              ["-m", "pip", "install", "--disable-pip-version-check", "-q", "demucs"]]
    for i, args in enumerate(passos, 1):
        log(f"🎵 Instalando a IA que separa voz e música ({i}/2, pode levar alguns minutos)...")
        r = subprocess.run([_python(), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=3600, creationflags=flags)
        if r.returncode != 0:
            log("⚠ Não consegui instalar: " + (r.stderr or r.stdout)[-400:])
            return False
    importlib.invalidate_caches()
    log("✅ IA de separar voz e música instalada.")
    return True


def _carregar():
    global _modelo
    if _modelo is None:
        import os
        os.environ.setdefault("HF_HUB_VERBOSITY", "error")     # sem aviso técnico de "token" no log
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        import torch
        from demucs.pretrained import get_model
        torch.set_num_threads(max(1, int(cortes.carregar_config().get("cpu_threads", 4))))
        cortes.log("Carregando a IA que separa voz e música (na 1ª vez ela baixa ~80 MB)...")
        _modelo = get_model(MODELO)
        _modelo.cpu().eval()
    return _modelo


def _ler(caminho: Path):
    import numpy as np
    with wave.open(str(caminho), "rb") as w:
        n, canais = w.getnframes(), w.getnchannels()
        a = np.frombuffer(w.readframes(n), np.int16).astype("float32") / 32768
    return a.reshape(-1, canais).T                       # (canais, amostras)


def _salvar(caminho: Path, audio, sr):
    import numpy as np
    dados = (np.clip(audio.T, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(dados.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(dados.tobytes())


def so_a_voz(audio, modelo=None):
    """audio (canais, amostras) a 44,1 kHz estéreo → só a voz, mesmo formato."""
    import torch
    from demucs.apply import apply_model
    modelo = modelo or _carregar()
    x = torch.from_numpy(audio)
    ref = x.mean(0)
    media, desvio = ref.mean(), ref.std() + 1e-8
    with torch.no_grad():
        fontes = apply_model(modelo, ((x - media) / desvio)[None], device="cpu", shifts=0, split=True,
                             overlap=0.25, progress=False)[0]
    voz = fontes[modelo.sources.index("vocals")] * desvio + media
    return voz.numpy()


def tirar_musica(video: Path, pasta: Path, log=print):
    """Vídeo novo com o som só da voz (o vídeo em si não é recomprimido). None se não der — aí o corte
    segue com o som original, nunca para por causa disso."""
    if not instalado():
        log("   ⚠ 'Tirar a música' está ligado, mas a IA não está instalada (⚙ Qualidade) — som original.")
        return None
    try:
        t0 = time.time()
        log("Separando a voz da música (IA, no processador)...")
        bruto = pasta / "som_original_44k.wav"
        cortes.rodar(["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "2", "-ar", "44100", str(bruto)])
        voz = so_a_voz(_ler(bruto))
        so_voz = pasta / "so_voz.wav"
        _salvar(so_voz, voz, 44100)
        saida = pasta / f"{Path(video).stem}_so_voz.mp4"
        cortes.rodar(["ffmpeg", "-y", "-i", str(video), "-i", str(so_voz), "-map", "0:v:0", "-map", "1:a:0",
                      "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", str(saida)])
        print(f"   🎵 música tirada: ficou só a voz ({time.time() - t0:.0f}s).")
        return saida
    except Exception as e:                               # noqa: BLE001 - nunca derruba o corte
        log(f"   ⚠ não consegui separar a voz ({str(e)[:160]}) — seguindo com o som original.")
        return None


# ------------------------------------------------------------------ 🎙 voz limpa (RNNoise, leve, ligado por padrão)
def _rodar_rnnoise(entrada: Path, saida: Path, tentativas=3) -> bool:
    """RNNoise num processo só dele, com nova tentativa: o filtro arnndn deste FFmpeg às vezes trava
    no FECHAMENTO (o arquivo já saiu inteiro — medido: 4 a 24% das vezes). Dentro do render final isso
    derrubaria o corte; aqui é só conferir o arquivo e tentar de novo."""
    filtro = cortes.filtro_limpeza_voz().lstrip(",")
    if "arnndn" not in filtro:
        return False
    esperado = _duracao_wav(entrada)
    for _ in range(tentativas):
        saida.unlink(missing_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-nostdin", "-i", str(entrada), "-af", filtro,
                        "-ar", "48000", str(saida)], capture_output=True, timeout=600,
                       creationflags=cortes.SEM_JANELA)
        if saida.exists() and abs(_duracao_wav(saida) - esperado) < 0.15:
            return True
    return False


def _duracao_wav(caminho: Path) -> float:
    try:
        with wave.open(str(caminho), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (OSError, wave.Error, EOFError):
        return -1.0


def parte_que_some(original: Path, limpo: Path, alto_db=-35.0, queda_db=10.0) -> float:
    """Dos segundos com som alto, quantos quase SOMEM na limpeza (0 a 1). Conversa: 0 a 2% (medido);
    vídeo de jogo: 60% (explosão, tiro, música do jogo não são voz). Alto = é jogo/música: não limpa."""
    import numpy as np

    def por_segundo(p):
        a = _ler(p).mean(0)
        sr = 48000
        n = len(a) // sr
        return 20 * np.log10(np.sqrt((a[: n * sr].reshape(n, sr) ** 2).mean(1)) + 1e-9)
    o, d = por_segundo(original), por_segundo(limpo)
    n = min(len(o), len(d))
    alto = o[:n] > alto_db
    if alto.sum() < 3:
        return 0.0
    return float(((o[:n] - d[:n])[alto] > queda_db).mean())


def limpar_voz(video: Path, pasta: Path, log=print, limite=0.4):
    """🎙 Vídeo novo com a voz limpa pela IA (ventoinha, teclado, chiado, barulho de rua; risada fica) —
    no começo do corte, então a transcrição também ouve melhor. None = mantém o som original (IA
    desligada, vídeo de jogo/música, ou deu erro). O vídeo em si não é recomprimido."""
    if not cortes.carregar_config().get("limpar_voz_ia", True) or not cortes.tem_audio(video):
        return None
    try:
        bruto, limpo = pasta / "voz_original48k.wav", pasta / "voz_limpa48k.wav"
        cortes.rodar(["ffmpeg", "-y", "-i", str(video), "-vn", "-ar", "48000", str(bruto)])
        if not _rodar_rnnoise(bruto, limpo):
            log("   ⚠ a limpeza de voz não rodou agora — seguindo com o som original.")
            return None
        some = parte_que_some(bruto, limpo)
        if some >= limite:
            print(f"   🎮 som alto que não é voz em {some:.0%} do vídeo (jogo/música) — mantendo o som original.")
            return None
        saida = pasta / f"{Path(video).stem}_voz_limpa.mp4"
        cortes.rodar(["ffmpeg", "-y", "-i", str(video), "-i", str(limpo), "-map", "0:v:0", "-map", "1:a:0",
                      "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", str(saida)])
        print("   🎙 voz limpa com IA (ruído de fundo tirado).")
        return saida
    except Exception as e:                               # noqa: BLE001 - nunca derruba o corte
        log(f"   ⚠ não consegui limpar a voz ({str(e)[:160]}) — seguindo com o som original.")
        return None
