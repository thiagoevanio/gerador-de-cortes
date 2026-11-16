"""
Acha os melhores momentos de um vídeo pra virar corte — gastando o mínimo de IA.

Como funciona (do mais barato pro mais caro):
  1. YouTube com gráfico "mais repetidos": usa direto o que o público mais reviu.
     Não gasta IA nem processamento.
  2. Sem gráfico: mede o volume/energia do áudio no PC e separa ~8 trechos candidatos
     (gritos, risadas, discussão, empolgação). Transcreve SÓ esses trechos.
  3. A IA lê só esses candidatos (não o vídeo inteiro) e escolhe os melhores,
     ajustando início e fim pra não cortar no meio da frase.
"""
from __future__ import annotations

import re
import math
import shutil
import tempfile
from pathlib import Path

import cortes

N_CANDIDATOS = 8


def _info_url(url):
    import yt_dlp
    import baixador
    with yt_dlp.YoutubeDL(baixador.opcoes_ytdlp(skip_download=True)) as y:
        return y.extract_info(url, download=False)


def picos_grafico(heatmap, duracao, dur, n):
    """Trechos de 'dur' segundos com mais replays. Devolve segundos de início."""
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
    ignorar = max(30, duracao * 0.03)
    escolhidos = []
    for s in sorted(range(len(janelas)), key=lambda k: -janelas[k]):
        if len(escolhidos) >= n:
            break
        if s >= ignorar and all(abs(s - e) >= dur for e in escolhidos):
            escolhidos.append(s)
    return escolhidos


def _baixar_audio(fonte, pasta: Path, log):
    """Devolve um .wav 16 kHz mono do vídeo inteiro."""
    wav = pasta / "inteiro16k.wav"
    if re.match(r"^https?://", str(fonte)):
        import yt_dlp
        log("   baixando só o áudio do vídeo...")
        import baixador          # pedidos de 10 MB + desafio do YouTube resolvido: não estrangula
        with yt_dlp.YoutubeDL(baixador.opcoes_ytdlp(format="bestaudio[ext=m4a]/bestaudio/best",
                                                    outtmpl=str(pasta / "audio.%(ext)s"))) as y:
            y.download([fonte])
        origem = next(pasta.glob("audio.*"))
    else:
        origem = Path(fonte)
    cortes.extrair_audio(origem, wav)
    return wav


def _energia_por_segundo(audio):
    import numpy as np
    seg = 16000
    n = len(audio) // seg
    if n == 0:
        return np.zeros(0)
    blocos = audio[: n * seg].reshape(n, seg)
    return np.sqrt((blocos.astype("float32") ** 2).mean(axis=1))


def candidatos_por_audio(audio, dur, n=N_CANDIDATOS):
    """Janelas com mais 'agito' no áudio: volume alto, picos e variação (grito, risada, briga)."""
    import numpy as np
    rms = _energia_por_segundo(audio)
    total = len(rms)
    if total < dur + 10:
        return [(0, total)]
    base = np.median(rms) + 1e-6
    rel = rms / base
    janela = int(dur * 1.5)                      # folga pra IA ajustar início/fim
    pontos = []
    for s in range(0, total - janela, 5):
        trecho = rel[s:s + janela]
        topo = np.sort(trecho)[-max(5, janela // 4):].mean()      # partes mais altas
        picos = (trecho > 2.2).sum()                               # explosões de volume
        variacao = trecho.std()                                    # conversa animada
        fala = (trecho > 0.6).mean()                               # tem gente falando?
        meio_j = max(1, janela // 2)
        contraste_reacao = max(0.0, float(trecho[meio_j:].mean() - trecho[:meio_j].mean())) * 0.35
        pontos.append(((topo * 1.0 + picos * 0.08 + variacao * 0.8 + contraste_reacao) * (0.4 + fala), s))
    ignorar_ini, ignorar_fim = max(20, total * 0.03), total - max(10, total * 0.02)
    escolhidos = []
    for nota, s in sorted(pontos, reverse=True):
        if s < ignorar_ini or s + janela > ignorar_fim:
            continue
        if all(abs(s - e) >= janela for e, _ in escolhidos):
            escolhidos.append((s, s + janela))
        if len(escolhidos) >= n:
            break
    return escolhidos


def _transcrever_frases(audio, trechos, log, dica=None):
    """Transcreve os candidatos (modelo base, rápido) guardando INÍCIO e FIM de cada frase.
    Devolve (textos, frases): textos = [[(t, texto)]] (formato antigo) e frases = [[(ini, fim, texto)]]."""
    modelo = cortes.carregar_whisper("base")
    textos, frases = [], []
    for i, (a, b) in enumerate(trechos, 1):
        log(f"   transcrevendo candidato {i}/{len(trechos)} ({cortes.fmt_tempo(a)})...")
        segs, _ = modelo.transcribe(audio[int(a * 16000):int(b * 16000)], language="pt",
                                    vad_filter=True, beam_size=1, initial_prompt=dica)
        fr = [(round(a + s.start, 2), round(a + s.end, 2), s.text.strip()) for s in segs if s.text.strip()]
        frases.append(fr)
        textos.append([(x, t) for x, _, t in fr])
    return textos, frases


def _transcrever_trechos(audio, trechos, log):
    return _transcrever_frases(audio, trechos, log)[0]


def encaixar(a, b, frases, minimo=10.0, maximo=180.0):
    """Ajusta o corte pras bordas das frases (o momento EXATO): começa um pouquinho antes da
    1ª frase e termina logo depois da última, sem pegar pedaço da frase vizinha."""
    todas = sorted(f for f in frases if f[1] > f[0])
    if not todas:
        return a, b
    # frase onde o corte começa: a que contém 'a' ou a primeira que começa depois
    ini_f = next((f for f in todas if f[0] <= a < f[1]), None) or next((f for f in todas if f[0] >= a - 0.5), None)
    fim_f = next((f for f in reversed(todas) if f[0] < b <= f[1] + 0.3), None) or \
        next((f for f in reversed(todas) if f[1] <= b + 0.5), None)
    if not ini_f or not fim_f or fim_f[1] <= ini_f[0]:
        return a, b
    i0, i1 = todas.index(ini_f), todas.index(fim_f)
    anterior = todas[i0 - 1][1] if i0 > 0 else None
    seguinte = todas[i1 + 1][0] if i1 + 1 < len(todas) else None
    novo_a = ini_f[0] - 0.25
    if anterior is not None:
        novo_a = max(novo_a, (anterior + ini_f[0]) / 2)        # no meio da pausa, nunca na frase anterior
    novo_b = fim_f[1] + 0.45
    if seguinte is not None:
        novo_b = min(novo_b, (fim_f[1] + seguinte) / 2)
    novo_a = max(0.0, round(novo_a, 2))
    novo_b = round(novo_b, 2)
    if not minimo <= novo_b - novo_a <= maximo:
        return a, b
    return novo_a, novo_b


def candidatos_por_texto(segmentos, total, dur, n=5):
    """Diversidade textual complementa energia; não é previsão de viralização."""
    from editorial import termos
    pontos = []
    anterior = set()
    for a, b, texto in segmentos:
        atual = termos(texto)
        novidade = len(atual-anterior)/max(1, len(atual))
        sinais = sum(p in texto.lower() for p in ('por quê', 'porque', 'problema', 'descobri', 'aconteceu', 'explicar', 'verdade'))
        pontos.append((novidade + min(2, len(atual)/12) + sinais + ('?' in texto), a))
        anterior = atual
    escolhidos = []
    for _, a in sorted(pontos, reverse=True):
        ini, fim = max(0, a-10), min(total, a+dur+15)
        if fim-ini >= 10 and all(abs(ini-x) >= dur for x, _ in escolhidos):
            escolhidos.append((ini, fim))
        if len(escolhidos) >= n:
            break
    return escolhidos


def achar_momentos(fonte, n=3, dur=60, log=print, contexto_titulo="", completo=False, chat_arquivo=None):
    """
    Devolve (lista de momentos, meta). Cada momento: {"inicio", "fim", "motivo"}.
    'fonte' pode ser link (YouTube/Twitch VOD) ou arquivo de vídeo do PC.
    completo=False (robô / aba Corte): econômico — usa o gráfico "mais repetidos" de graça quando
    existe e no máximo 8 candidatos. completo=True (Central de edição): análise detalhada.
    """
    cfg = cortes.carregar_config()
    completo = completo or cfg.get("analise_ampla", False)
    inicios = []
    info = {}
    meta = {"titulo": contexto_titulo or Path(str(fonte)).stem, "canal": ""}
    if re.match(r"^https?://", str(fonte)):
        log("Lendo informações do vídeo...")
        info = _info_url(fonte)
        meta = {"titulo": info.get("title", ""), "canal": info.get("uploader", "")}
        duracao = info.get("duration") or 0
        inicios = picos_grafico(info.get("heatmap"), duracao, dur, n)
        if inicios and not completo and not cfg.get("analise_heatmap_ia", False):
            log("📈 Usando o gráfico de 'mais repetidos' do YouTube (sem gastar IA).")
            return [{"inicio": s, "fim": s + dur, "motivo": "trecho mais repetido pelo público",
                     "evidencias": {"motivo": "gráfico de mais repetidos do YouTube", "candidato": [s, s + dur]}}
                    for s in sorted(inicios)], meta
        if inicios:
            log("📈 Replays encontrados; verificando contexto antes de escolher o corte.")

    pasta = Path(tempfile.mkdtemp(prefix="momentos_"))
    try:
        # ---- chat da live antiga (VOD da Twitch / live do YouTube / arquivo ao lado do vídeo) ----
        import chat_vod
        chat = None
        if chat_arquivo:
            chat = chat_vod.ler_arquivo(chat_arquivo)
            log(f"💬 Chat do arquivo: {len(chat)} mensagens.")
        elif cfg.get("usar_chat_vod", True):
            if re.match(r"^https?://", str(fonte)):
                chat = chat_vod.baixar(fonte, pasta, info, log)
            else:
                ao_lado = chat_vod.chat_ao_lado(fonte)
                if ao_lado:
                    chat = chat_vod.ler_arquivo(ao_lado)
                    log(f"💬 Achei o chat ao lado do vídeo ({ao_lado.name}): {len(chat)} mensagens.")
        wav = _baixar_audio(fonte, pasta, log)
        audio = cortes.ler_wav(wav)
        log("Medindo a energia do áudio pra achar os trechos mais agitados...")
        trechos = candidatos_por_audio(audio, dur)
        total = len(audio) / 16000
        meta["duracao"] = total
        resumo_chat = {}
        if chat:
            picos_chat = chat_vod.picos(chat, total, dur, n=max(n + 3, 6))
            if picos_chat:
                log(f"   💬 {len(picos_chat)} momentos em que o chat explodiu.")
                do_chat = [(p["ini"], p["fim"]) for p in picos_chat]
                resumo_chat = {(p["ini"], p["fim"]): p["resumo"] for p in picos_chat}
                # o chat vem primeiro (é o sinal mais forte); o áudio completa sem repetir trecho
                trechos = do_chat + [t for t in trechos if all(t[1] <= a or t[0] >= b for a, b in do_chat)]
        if cortes.carregar_config().get('analise_ampla', False):
            log('Análise ampla: transcrevendo o áudio para procurar mudanças e acontecimentos.')
            segs, _ = cortes.carregar_whisper('base').transcribe(audio, language='pt', vad_filter=True, beam_size=1)
            segmentos = [(round(s.start, 2), round(s.end, 2), s.text.strip()) for s in segs if s.text.strip()]
            meta['transcricao_completa'] = segmentos
            textuais = candidatos_por_texto(segmentos, total, dur)
            trechos = textuais + [t for t in trechos if all(abs(t[0]-a) >= dur*0.6 for a,_ in textuais)]
        # Replays são candidatos, e não uma decisão final. Inclui margens de contexto.
        sementes = [(max(0, x - 12), min(total, x + dur + 18)) for x in inicios]
        # Amostragem de cobertura permite encontrar falas calmas além dos picos de volume.
        cobertura = [(max(0, total * fracao - dur / 2), min(total, total * fracao + dur))
                     for fracao in (0.2, 0.5, 0.8)]
        for candidato in sementes + cobertura:
            if candidato[1] - candidato[0] >= 10 and all(abs(candidato[0] - a) >= dur * 0.6 for a, _ in trechos):
                trechos.append(candidato)
        trechos = trechos[:16 if completo else 8]
        log(f"   {len(trechos)} candidatos encontrados.")
        textos, frases = _transcrever_frases(audio, trechos, log, dica=cortes.dica_transcricao(meta))
    finally:
        shutil.rmtree(pasta, ignore_errors=True)

    chats = [resumo_chat.get(t, "") for t in trechos]
    return _ranquear(trechos, textos, meta, n, dur, log, completo, frases=frases, chats=chats), meta


def _ranquear(trechos, textos, meta, n, dur, log, completo=False, frases=None, chats=None):
    from inteligencia_editorial import avaliar, versoes
    # monta um texto curto só com os candidatos (é isso que economiza tokens)
    frases = frases or [[(t, t, txt) for t, txt in falas] for falas in textos]
    chats = chats or [""] * len(trechos)
    numeradas = []                      # F1, F2... (todas as frases, de todos os candidatos)
    blocos = []
    for i, ((a, b), fr, ct) in enumerate(zip(trechos, frases, chats), 1):
        partes = []
        for x, y, txt in fr:
            numeradas.append((x, y, txt, i - 1))
            partes.append(f"[F{len(numeradas)} {x:.0f}s] {txt}")
        corpo = " ".join(partes) or "(sem fala)"
        extra = f"\n  chat reagindo: {ct}" if ct else ""
        blocos.append(f"C{i} ({a:.0f}s a {b:.0f}s): {corpo}{extra}")
    lim_min, lim_max = (max(15, dur * 0.5), max(90, dur * 1.6))
    prompt = (f'Você é editor de cortes virais brasileiros. Vídeo: "{meta["titulo"]}" '
              f'(canal "{meta["canal"]}"). Abaixo estão trechos candidatos; cada frase tem um número '
              f'(F1, F2...) e o segundo em que começa.\n\n'
              + "\n\n".join(blocos) +
              f"\n\nEscolha os {n} melhores pra corte de uns {dur}s (entre {lim_min:.0f} e {lim_max:.0f}s): "
              f"engraçado, polêmico, revelação, briga ou história que faça sentido sozinha. "
              f"O MOMENTO EXATO importa: o corte tem que começar na frase que já prende (sem enrolação "
              f"antes) e terminar logo depois do desfecho/reação (sem cortar a frase no meio). "
              f'Diga isso com "frase_inicio" e "frase_fim" (os números F das frases, do mesmo candidato). '
              f"Priorize uma história completa; não confunda volume alto com qualidade. "
              f'Dê também "nota" de 0 a 10 pra chance de cada um prender quem não conhece o vídeo '
              f"(9-10: algo forte logo no começo, entende sem contexto e tem desfecho; 5-6: interessante mas "
              f"depende de contexto; 0-3: conversa sem pico). Seja exigente. ")
    detalhado = completo or cortes.carregar_config().get("avaliacao_editorial", False)
    if detalhado:      # resposta bem maior (mais tokens): só na Central de edição ou se você ligar
        prompt += ("Avalie separadamente gancho, contexto, desenvolvimento e conclusão. "
              'Responda APENAS JSON: {"momentos": [{"frase_inicio": 12, "frase_fim": 20, "inicio": segundos, "fim": segundos, '
              '"nota": 7, "motivo": "bem curto", "avaliacao": {"gancho": {"nota": 0, "evidencia": "citação literal"}, '
              '"contexto": {"nota": 0, "evidencia": "citação literal"}, "desenvolvimento": {"nota": 0, "evidencia": "citação literal"}, '
              '"conclusao": {"nota": 0, "evidencia": "citação literal"}}, '
              '"versoes": {"direta": {"inicio": 0,"fim": 0,"justificativa":"ideia principal"}, '
              '"contexto": {"inicio":0,"fim":0,"justificativa":"premissa necessária"}, '
              '"historia": {"inicio":0,"fim":0,"justificativa":"história completa"}}}]}. '
              'Use notas de 0 a 10 e citações presentes na transcrição. Cada versão deve ter bordas narrativas próprias, dentro do candidato, sem inventar falas.')
    else:
        prompt += ('Responda APENAS JSON: {"momentos": [{"frase_inicio": 12, "frase_fim": 20, '
                   '"inicio": segundos, "fim": segundos, "nota": 7, "motivo": "bem curto"}]}')

    def frase_n(v):
        try:
            k = int(str(v).upper().lstrip("F"))
            return numeradas[k - 1] if 1 <= k <= len(numeradas) else None
        except (TypeError, ValueError):
            return None

    momentos = []
    if cortes.IA_PRINCIPAL != "nenhuma":
        log("IA escolhendo os melhores entre os candidatos...")
        import ia_motor
        with ia_motor.rotulo("momentos"):
            resp = cortes.ia_json(prompt) or {}
        if isinstance(resp, list):                   # alguns modelos devolvem só a lista
            resp = {"momentos": resp}
        for m in (resp.get("momentos", []) if isinstance(resp, dict) and isinstance(resp.get("momentos", []), list) else [])[:max(0, n)]:
            if not isinstance(m, dict):
                continue
            f0, f1 = frase_n(m.get("frase_inicio")), frase_n(m.get("frase_fim"))
            if f0 and f1 and f0[3] == f1[3] and f1[1] > f0[0]:
                a, b = f0[0], f1[1]                      # pelas frases (o jeito preciso)
            else:
                try:
                    a, b = float(m["inicio"]), float(m["fim"])
                except (KeyError, TypeError, ValueError):
                    continue
            cand = next(((x, y) for x, y in trechos if x - 1 <= a < b <= y + 1), None)
            if cand and math.isfinite(a) and math.isfinite(b):
                fr_c = next((fr for (x, y), fr in zip(trechos, frases) if (x, y) == cand), [])
                a, b = encaixar(max(a, cand[0]), min(b, cand[1]), fr_c, 10, max(120, lim_max * 1.2))
                a, b = max(a, cand[0]), min(b, cand[1])
            if (math.isfinite(a) and math.isfinite(b) and a >= 0 and 10 <= b - a <= max(120, lim_max * 1.2)
                    and any(x <= a < b <= y for x, y in trechos)
                    and all(b <= x["inicio"] or a >= x["fim"] for x in momentos)):
                try:
                    nota_ia = float(m.get("nota"))
                    nota_ia = nota_ia if math.isfinite(nota_ia) and 0 <= nota_ia <= 10 else None
                except (TypeError, ValueError):
                    nota_ia = None
                momentos.append({"inicio": a, "fim": b, "motivo": str(m.get("motivo", ""))[:300], "avaliacao_ia":m.get("avaliacao"), "versoes_ia":m.get("versoes"), "nota_ia": nota_ia})
        notas = [x["nota_ia"] for x in momentos if x.get("nota_ia") is not None]
        if notas and max(notas) >= 4:                # trecho claramente fraco nem chega a ser baixado
            fracos = [x for x in momentos if x.get("nota_ia") is not None and x["nota_ia"] < 4]
            if fracos:
                log(f"   (IA) {len(fracos)} momento(s) fraco(s) (nota abaixo de 4) ficaram de fora.")
                momentos = [x for x in momentos if x not in fracos]
    if not momentos:                     # sem IA: pega os candidatos mais agitados
        log("   (sem IA) usando os trechos com mais reação do chat/áudio.")
        ordenados = sorted(zip(trechos, textos, chats, frases),
                           key=lambda x: (bool(x[2]), avaliar(" ".join(txt for _, txt in x[1]))["nota"]), reverse=True)
        for (a,b), falas, _ct, fr_c in ordenados:
            meio = (a + b) / 2
            tamanho = min(dur, b - a)
            if tamanho <= 0:
                continue
            x,y=max(a,meio-tamanho/2),min(b,meio+tamanho/2)
            x, y = encaixar(x, y, fr_c, 10, max(120, dur * 2))
            if len(momentos)>=n:break
            if any(x<m["fim"] and y>m["inicio"] for m in momentos):continue
            momentos.append({"inicio": x, "fim": y,
                             "motivo": "o chat explodiu aqui" if _ct else "trecho mais agitado"})
    for m in momentos:
        log(f"   ✂ {cortes.fmt_tempo(m['inicio'])} → {cortes.fmt_tempo(m['fim'])}  {m['motivo']}"
            + (f"  (nota {m['nota_ia']:g})" if m.get("nota_ia") is not None else ""))
    # Evidências locais e alternativas preservam a origem e os limites do candidato.
    for m in momentos:
        candidato = next(((a, b) for a, b in trechos if a <= m["inicio"] < m["fim"] <= b), (m["inicio"], m["fim"]))
        a, b = candidato
        m["transcricao"] = " ".join(txt for (x, y), falas in zip(trechos, textos) if x == a and y == b for t, txt in falas)
        falas = next((fs for (x,y),fs in zip(trechos,textos) if x==a and y==b), [])
        m['transcricao_candidato']=m['transcricao']
        m['transcricao']=' '.join(txt for t,txt in falas if m['inicio']<=t<m['fim'])
        avaliacao=avaliar(m['transcricao'],m.pop('avaliacao_ia',None))
        m['evidencias'] = dict(motivo=m['motivo'], candidato=[a,b], limites_validados=True,
                               revisao_humana=True, avaliacao_completa=avaliacao['verificavel'], avaliacao=avaliacao)
        m['versoes'] = versoes(falas,m['inicio'],m['fim'],(a,b),m.pop('versoes_ia',None))

    return sorted(momentos, key=lambda m: m["inicio"])


def momentos_do_trecho(arquivo, ini, fim, n=2, dur=60, meta=None, log=print):
    """Pra lives sem chat (Kick, YouTube): acha os melhores momentos de um pedaço da gravação."""
    meta = meta or {"titulo": "", "canal": ""}
    pasta = Path(tempfile.mkdtemp(prefix="trecho_"))
    try:
        wav = pasta / "trecho.wav"
        cortes.rodar(["ffmpeg", "-y", "-ss", str(ini), "-i", str(arquivo), "-t", str(fim - ini),
                      "-vn", "-ac", "1", "-ar", "16000", str(wav)])
        audio = cortes.ler_wav(wav)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    trechos = candidatos_por_audio(audio, dur, n=5)
    if not trechos:
        return []
    textos, frases = _transcrever_frases(audio, trechos, log, dica=cortes.dica_transcricao(meta))
    achados = _ranquear(trechos, textos, meta, n, dur, log, frases=frases)
    return [deslocar_momento(m, ini) for m in achados]


def deslocar_momento(momento, deslocamento):
    m = {**momento, 'inicio': momento['inicio']+deslocamento, 'fim': momento['fim']+deslocamento}
    if momento.get('versoes'):
        m['versoes'] = {nome: dict(v, inicio=v['inicio']+deslocamento, fim=v['fim']+deslocamento) for nome,v in momento['versoes'].items()}
    if momento.get('evidencias'):
        m['evidencias'] = dict(momento['evidencias'])
        if 'candidato' in m['evidencias']:
            m['evidencias']['candidato'] = [x+deslocamento for x in m['evidencias']['candidato']]
    return m


