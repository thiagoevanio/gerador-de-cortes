"""🎞 Supercut: os N melhores lances de um vídeo/live num corte só, em contagem (#5, #4 … #1), com
"whoosh" e um flash em cada virada.

Como funciona:
  1. acha os momentos (o mesmo achar_momentos do corte automático: gráfico de mais repetidos, chat,
     energia do áudio e IA);
  2. de cada momento pega só a parte mais agitada (a janela de 'seg' segundos com mais energia no som —
     risada, grito, reação), começando e terminando num respiro (não corta palavra no meio);
  3. junta os pedaços em ordem crescente: o mais fraco abre, o #1 fecha o vídeo (segura até o fim);
  4. passa o vídeo junto pelo corte de sempre (legenda, template, rosto, IA, pergunta), marcando onde
     cada lance começa. As marcas viajam nas palavras da transcrição, então continuam certas depois
     de tirar silêncio, é/tipo/né e abertura enrolada.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

import cortes

MIN_LANCES = 3


# ------------------------------------------------------------------ escolher e recortar os lances
def nota_do(m) -> float:
    """A nota do momento (IA ou avaliação local). Sem nota = 0."""
    if m.get("nota_ia") is not None:
        try:
            return float(m["nota_ia"])
        except (TypeError, ValueError):
            pass
    try:
        return float(m["evidencias"]["avaliacao"]["nota"])
    except (KeyError, TypeError, ValueError):
        return 0.0


def escolher(momentos, n):
    """Os n melhores, na ordem da contagem: do mais fraco pro mais forte (o #1 fecha o vídeo).
    Empate: na ordem em que aparecem no vídeo."""
    melhores = sorted(enumerate(momentos), key=lambda x: (-nota_do(x[1]), x[0]))[:n]
    return [m for _, m in sorted(melhores, key=lambda x: (nota_do(x[1]), x[0]))]


def melhor_janela(audio, seg, sr=16000, ajuste=0.8):
    """(a, b) em segundos: os 'seg' segundos com mais energia no som, com as pontas puxadas pro respiro
    mais próximo (até 'ajuste' s), pra não cortar palavra no meio. Pedaço curto: ele inteiro."""
    import numpy as np
    total = len(audio) / sr
    if total <= seg + 0.5:
        return 0.0, round(total, 2)
    passo = int(sr * 0.05)                                       # energia a cada 50 ms
    blocos = np.asarray(audio[: len(audio) // passo * passo], dtype="float32").reshape(-1, passo)
    energia = np.sqrt((blocos ** 2).mean(1))
    n = int(seg / 0.05)
    soma = np.convolve(energia, np.ones(n), mode="valid")
    i = int(soma.argmax())

    def respiro(k):
        lo, hi = max(0, k - int(ajuste / 0.05)), min(len(energia) - 1, k + int(ajuste / 0.05))
        return lo + int(energia[lo:hi + 1].argmin())
    a, b = respiro(i), respiro(min(len(energia) - 1, i + n))
    if b - a < n * 0.6:                                          # o respiro encolheu demais: janela crua
        a, b = i, min(len(energia), i + n)
    return round(a * 0.05, 2), round(min(total, b * 0.05), 2)


def juntar(pecas, destino: Path):
    """pecas = [(video, a, b)]. Um vídeo só com os pedaços em sequência (mesmo tamanho e fps do 1º,
    micro-fade no som de cada virada). Devolve (destino, [início de cada pedaço no vídeo junto])."""
    import render
    w, h = cortes.info_video(pecas[0][0])
    fps = render.fps_saida(pecas[0][0])
    entradas, filtro, rotulos, marcas, t = [], [], [], [], 0.0
    for k, (video, a, b) in enumerate(pecas):
        d = b - a
        entradas += ["-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", str(video)]
        filtro.append(f"[{k}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
                      f"setsar=1,fps={fps},format=yuv420p,setpts=PTS-STARTPTS[v{k}]")
        filtro.append(f"[{k}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                      f"asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.04,afade=t=out:st={max(0.0, d - 0.06):.3f}:d=0.06[a{k}]")
        rotulos.append(f"[v{k}][a{k}]")
        marcas.append(round(t, 3))
        t += d
    filtro.append(f"{''.join(rotulos)}concat=n={len(pecas)}:v=1:a=1[v][a]")
    cortes.rodar(["ffmpeg", "-y", *entradas, "-filter_complex", ";".join(filtro), "-map", "[v]", "-map", "[a]",
                  *cortes.args_encoder_video(intermediario=True), "-c:a", "aac", "-b:a", "256k",
                  str(destino)], progresso=("Juntando os lances", t))
    return destino, marcas


# ------------------------------------------------------------------ marcas e contagem (usadas pelo cortes.py)
def marcar_palavras(palavras, marcas):
    """Põe em cada lance a marca na 1ª palavra dele: 'supercut' = nº do lance (1 = o primeiro do vídeo)
    e 'supercut_dt' = quanto tempo depois do começo do lance ela é dita. As palavras são o que todo
    corte de tempo do programa mantém em sincronia, então a marca acompanha qualquer corte."""
    for k, t in enumerate(marcas):
        fim = marcas[k + 1] if k + 1 < len(marcas) else float("inf")
        p = next((p for p in palavras if t - 0.05 <= p["ini"] < fim), None)
        if p is not None and "supercut" not in p:
            p["supercut"] = k + 1
            p["supercut_dt"] = round(max(0.0, min(1.5, p["ini"] - t)), 2)
            p["quebra"] = True              # a legenda não junta a última fala de um lance com a 1ª do outro
    return palavras


def viradas(palavras):
    """[(nº do lance, segundo em que ele começa no vídeo final)], na ordem."""
    saida, anterior = [], 0.0
    for i, p in enumerate(palavras):
        if p.get("supercut"):
            antes = palavras[i - 1]["fim"] if i > 0 else 0.0
            t = 0.0 if p["supercut"] == 1 else max(antes, p["ini"] - p.get("supercut_dt", 0.15))
            if not saida or t > anterior:
                saida.append((p["supercut"], round(t, 2)))
                anterior = t
    return saida


def contagem(palavras, total, duracao, depois_do_gancho=0.0, y=270):
    """Selo '#N' no canto de cima, durante o lance inteiro (o 1º lance só depois da pergunta do
    gancho, pra não encavalar). Devolve (textos_extra, segundos das viradas pro whoosh/flash)."""
    vs = viradas(palavras)
    textos, tempos = [], []
    for j, (k, t) in enumerate(vs):
        fim = vs[j + 1][1] if j + 1 < len(vs) else duracao
        ini = max(t, depois_do_gancho) if k == 1 else t
        if fim - ini < 0.8:
            continue
        num = total - k + 1
        cor = "&H0000E6FF&" if num == 1 else "&H00FFFFFF&"
        textos.append((round(ini, 2), round(fim, 2),
                       "{\\an7\\pos(56,%d)\\fs118\\bord9\\c%s}#%d" % (y, cor, num), "Aviso"))
        if k > 1:
            tempos.append(t)
    return textos, tempos


# ------------------------------------------------------------------ o supercut inteiro
@contextmanager
def _ligado(marcas, total):
    token = cortes._supercut.set({"marcas": list(marcas), "total": total})
    try:
        yield
    finally:
        cortes._supercut.reset(token)


def completar(fonte, achados, n, dur, pasta: Path, log=print):
    """A IA escolhe trecho que funciona SOZINHO como corte e às vezes aprova só 1 ou 2. No supercut um
    lance curto e agitado (risada, grito, reação) já vale: completa com os mais agitados do áudio, sem
    repetir trecho. Eles entram com nota 0 (abrem a contagem; os da IA ficam pro fim)."""
    import momentos as mod_momentos
    log(f"   a IA aprovou {len(achados)} — completando com os trechos mais agitados do áudio...")
    audio = cortes.ler_wav(mod_momentos._baixar_audio(fonte, pasta, log))
    saida = list(achados)
    for a, b in agitados(audio, dur):
        if len(saida) >= n:
            break
        if all(b <= m["inicio"] - 1 or a >= m["fim"] + 1 for m in saida):
            saida.append({"inicio": float(a), "fim": float(b), "motivo": "trecho mais agitado (áudio)"})
    return saida


def agitados(audio, dur, sr=16000):
    """Janelas de 'dur' s do áudio, da mais agitada pra menos (média das partes mais altas), sem
    repetir trecho. Serve até pra vídeo curto (o buscador geral pula o começo/fim e usa janela maior)."""
    import numpy as np
    n = len(audio) // sr
    if n < 3:
        return []
    rms = np.sqrt((np.asarray(audio[: n * sr], dtype="float32").reshape(n, sr) ** 2).mean(1))
    dur = max(3, min(int(dur), n))
    pontos = []
    for s in range(0, n - dur + 1, 2):
        janela = np.sort(rms[s:s + dur])
        pontos.append((float(janela[-max(2, dur // 3):].mean()), s))
    escolhidos = []
    for _, s in sorted(pontos, reverse=True):
        if all(s + dur <= a or s >= b for a, b in escolhidos):
            escolhidos.append((s, s + dur))
    return escolhidos


def gerar(fonte, n=5, seg=12, log=print, **opcoes):
    """Faz o supercut de 'fonte' (link ou arquivo do PC). Devolve o caminho do corte pronto."""
    import momentos as mod_momentos
    n = max(MIN_LANCES, min(8, int(n)))
    seg = max(6.0, min(20.0, float(seg)))
    link = bool(re.match(r"^https?://", str(fonte)))
    log(f"🎞 Supercut: procurando os {n} melhores lances...")
    dur_busca = max(20, int(seg * 2))
    achados, meta = mod_momentos.achar_momentos(fonte, n + 2, dur_busca, log=log,
                                                chat_arquivo=opcoes.pop("chat_arquivo", None))
    raiz = Path(opcoes.get("pasta_saida") or cortes.PASTA_SAIDA) / "_trabalho"
    raiz.mkdir(parents=True, exist_ok=True)
    pasta = Path(tempfile.mkdtemp(prefix="supercut_", dir=raiz))
    try:
        if len(achados) < n:
            achados = completar(fonte, achados, n, dur_busca, pasta, log)
        lances = escolher(achados, n)
        if len(lances) < MIN_LANCES:
            raise ValueError(f"Achei só {len(lances)} lance(s) — o supercut precisa de pelo menos {MIN_LANCES} "
                             "(o vídeo é curto demais ou quase sem som).")
        pecas = []
        for i, m in enumerate(lances, 1):
            log(f"   lance {i} de {len(lances)}: {cortes.fmt_tempo(m['inicio'])} → {cortes.fmt_tempo(m['fim'])}")
            sub = pasta / f"lance{i}"
            sub.mkdir()
            if link:
                video, _ = cortes.baixar_trecho(fonte, m["inicio"], m["fim"], sub)
            else:
                video, _ = cortes.recortar_local(fonte, m["inicio"], m["fim"], sub, meta)
            if not cortes.tem_audio(video):
                log("   (sem som — fica de fora)")
                continue
            audio = cortes.ler_wav(cortes.extrair_audio(video, sub / "audio.wav"))
            a, b = melhor_janela(audio, seg)
            if b - a >= 3:
                pecas.append((video, a, b))
        if len(pecas) < MIN_LANCES:
            raise ValueError("Não sobraram lances suficientes pro supercut (precisa de 3 com som).")
        junto, marcas = juntar(pecas, pasta / "supercut.mp4")
        k = len(pecas)
        titulo = meta.get("titulo") or Path(str(fonte)).stem
        contexto = (f"SUPERCUT: os {k} melhores lances de \"{titulo}\" em sequência, em contagem (#{k} até o #1, "
                    f"o melhor no fim). A pergunta e o título devem prometer o TOP {k} (ex.: 'OS {k} MOMENTOS MAIS "
                    f"INSANOS DA LIVE'). {opcoes.pop('contexto', '') or ''}").strip()
        opcoes.setdefault("nota_minima", 0)
        with _ligado(marcas, k):
            return cortes.gerar_corte(str(junto), 0, cortes.duracao_video(junto), contexto=contexto,
                                      meta={**meta, "titulo": f"TOP {k} — {titulo}", "supercut": k}, **opcoes)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
