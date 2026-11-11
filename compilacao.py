"""
Compilação semanal — junta os melhores cortes da semana num vídeo HORIZONTAL (1920x1080)
pro YouTube normal, que paga bem mais por view que o Shorts.

  Intro dinâmica "TOP N DA SEMANA" (1,8s com som de transição e zoom suave) → #N → ... → #1,
  cada corte com transição sonora (sem silêncio morto), barra de progresso no rodapé,
  áudio nivelado entre clipes, título, descrição e capítulos (minutagem).
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import textwrap
from pathlib import Path

import cortes
import efeitos
import resultados

W, H = 1920, 1080
DURACAO_INTRO = 1.8


def escolher(dias=7, n=5, canal=None, alvo_seg=None, maximo=15):
    """Os melhores cortes do período. Com 'alvo_seg', vai somando cortes (até 'maximo') até o vídeo
    chegar no tamanho alvo (ex.: 8 min = mais horas assistidas). 'canal' = só de um streamer."""
    limite = dt.datetime.now() - dt.timedelta(days=dias)
    cand = []
    for mp4, f in resultados.fichas():
        if f.get("idioma", "pt") != "pt" or f.get("variante") == "B" or f.get("tipo") in ("compilacao", "longo"):
            continue
        if canal and (f.get("canal") or "").lower() != canal.lower():
            continue
        if f.get("parte") == 2:                   # série: a parte 1 já representa o lance
            continue
        quando = resultados.data_post(f)
        if quando and quando >= limite:
            cand.append((resultados.views_de(f), f.get("nota") or 0, mp4, f))
    # quem tem views ganha; sem views ainda, vale a nota da IA
    cand.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if not alvo_seg:
        return cand[:n]
    escolhidos, total = [], 0.0
    for c in cand:
        if len(escolhidos) >= maximo or (total >= alvo_seg and len(escolhidos) >= n):
            break
        escolhidos.append(c)
        total += float(c[3].get("duracao") or 60) + 18          # + contexto/cartões
    return escolhidos


def _longos_por_curto():
    """Mapa: corte curto → a versão longa (16:9) dele, se você gerou."""
    mapa = {}
    for mp4, f in resultados.fichas():
        if f.get("tipo") == "longo" and f.get("curto"):
            mapa[Path(f["curto"]).name] = mp4
    return mapa


def _rodape(posicao, titulo, canal, destino: Path):
    """Faixa embaixo (estilo telejornal) com o número e o título, pros trechos deitados."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 200, W, H - 70], fill=(12, 12, 16, 195))
    d.rectangle([0, H - 204, W, H - 200], fill=(255, 214, 0, 235))
    d.rectangle([0, H - 200, 230, H - 70], fill=(217, 15, 15, 255))
    fn = cortes._fonte_rasgada(110)
    d.text((40, H - 196), f"#{posicao}", font=fn, fill=(255, 214, 0), stroke_width=5, stroke_fill=(0, 0, 0))
    ft = cortes._fonte_rasgada(62)
    linha = textwrap.shorten(titulo.upper(), 48, placeholder="...")
    d.text((270, H - 178), linha, font=ft, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    if canal:
        d.text((272, H - 112), canal.upper(), font=cortes.fonte(34), fill=(255, 214, 0))
    img.save(destino)
    return destino


def _filtro_audio_segmento(entrada_audio: str, whoosh_idx: int | None = None):
    """Nivela o áudio de cada segmento da compilação e mistura o 'whoosh' de entrada sem estalos."""
    base = (f"{entrada_audio}highpass=f=75{cortes.filtro_chiado()},"
            "acompressor=threshold=-20dB:ratio=2.5:attack=10:release=200:makeup=1.5,"
            "afade=t=in:st=0:d=0.06,"
            "aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo")
    if whoosh_idx is None:
        return f"{base}[a]"
    return (f"{base}[av];"
            f"[{whoosh_idx}:a]aresample=48000,"
            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,volume=0.45[aw];"
            "[av][aw]amix=inputs=2:duration=first:normalize=0,"
            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a]")


def _segmento_deitado(mp4: Path, rodape: Path, destino: Path, ini=0.0, dur=None):
    """Trecho horizontal (fonte original ou corte longo) com o rodapé animado, barra de tempo
    nos primeiros 6s e efeito sonoro 'whoosh' na transição."""
    tem_audio = cortes.tem_audio(mp4)
    whoosh = efeitos.gerar_whoosh(destino.parent, duracao=0.50)
    filtro = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
              "setsar=1,fade=t=in:st=0:d=0.18[base];"
              "[1:v]format=rgba,fade=t=in:st=0:d=0.20:alpha=1,fade=t=out:st=5.6:d=0.4:alpha=1[r];"
              "[base][r]overlay=0:0:shortest=1:enable='lt(t,6)',"
              f"drawbox=x=0:y={H - 70}:w='iw*(t/6.0)':h=6:color=0xFFD600@0.95:t=fill:enable='lt(t,6)',"
              "format=yuv420p[v]")
    cmd = ["ffmpeg", "-y", "-ss", f"{ini:.2f}", "-i", str(mp4), "-loop", "1", "-i", str(rodape)]
    if tem_audio:
        cmd += ["-i", str(whoosh)]
        filtro += ";" + _filtro_audio_segmento("[0:a]", whoosh_idx=2)
        mapa_a = "[a]"
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        mapa_a = "2:a"
    if dur:
        cmd += ["-t", f"{dur:.2f}"]
    cmd += ["-filter_complex", filtro, "-map", "[v]", "-map", mapa_a,
            "-shortest", "-r", "30", *cortes.args_encoder_video(intermediario=False),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(destino)]
    cortes.rodar(cmd)
    return destino


def _fonte_deitada(f, tmp: Path, i):
    """Tenta o trecho ORIGINAL (horizontal) do corte, com 6s de contexto antes e 4s depois."""
    fonte = f.get("fonte") or ""
    try:
        ini, fim = float(f.get("inicio")), float(f.get("fim"))
    except (TypeError, ValueError):
        return None
    a, b = max(0.0, ini - 6), fim + 4
    pasta = tmp / f"fonte{i}"
    pasta.mkdir(exist_ok=True)
    try:
        if fonte.startswith(("http://", "https://")):
            video, _ = cortes.baixar_trecho(fonte, a, b, pasta)
        elif fonte and Path(fonte).exists():
            video, _ = cortes.recortar_local(fonte, a, b, pasta)
        else:
            return None
        w, h = cortes.info_video(video)
        return video if w > h else None                 # fonte em pé não ganha nada aqui
    except Exception:
        return None


def _cartao(texto_grande, texto_pequeno, destino: Path, fundo=(22, 22, 26)):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), fundo)
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 26, W, H], fill=(255, 214, 0))
    d.rectangle([0, 0, W, 18], fill=(217, 15, 15))
    f1 = cortes._fonte_rasgada(190)
    f2 = cortes.fonte(54)
    w1 = d.textlength(texto_grande, font=f1)
    d.text(((W - w1) / 2, 330), texto_grande, font=f1, fill=(255, 255, 255), stroke_width=8, stroke_fill=(0, 0, 0))
    w2 = d.textlength(texto_pequeno, font=f2)
    d.text(((W - w2) / 2, 600), texto_pequeno, font=f2, fill=(255, 214, 0))
    img.save(destino)
    return destino


def _lateral(posicao, titulo, canal, destino: Path):
    """PNG transparente com o número grande e o título dos dois lados do vídeo em pé."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fn = cortes._fonte_rasgada(330)
    num = f"#{posicao}"
    d.text((90, 300), num, font=fn, fill=(255, 214, 0), stroke_width=12, stroke_fill=(0, 0, 0))
    ft = cortes._fonte_rasgada(78)
    y = 330
    for linha in textwrap.wrap(titulo.upper(), 16)[:5]:
        d.text((1300, y), linha, font=ft, fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
        y += 92
    if canal:
        fc = cortes.fonte(40)
        d.rounded_rectangle([1300, y + 24, 1300 + d.textlength(canal.upper(), font=fc) + 50, y + 90],
                            radius=14, fill=(217, 15, 15))
        d.text((1325, y + 34), canal.upper(), font=fc, fill=(255, 255, 255))
    img.save(destino)
    return destino


def _segmento_cartao(png: Path, segundos, destino: Path):
    """Cartão de abertura curto (~1.8s) com zoom suave e efeito sonoro (whoosh + sub-drop)
    em vez de silêncio absoluto que derruba a retenção."""
    segundos = float(segundos)
    whoosh = efeitos.gerar_whoosh(destino.parent, duracao=min(0.8, segundos))
    boom = efeitos.gerar_boom(destino.parent)
    fade_out = max(0.1, segundos - 0.25)
    filtro = (f"[0:v]scale=w='{W}*(1+0.04*(t/{segundos:.2f}))':h='{H}*(1+0.04*(t/{segundos:.2f}))':eval=frame,"
              f"crop={W}:{H},fade=t=in:st=0:d=0.18,fade=t=out:st={fade_out:.2f}:d=0.22,"
              f"drawbox=x=0:y={H - 26}:w='iw*(t/{segundos:.2f})':h=26:color=0xD90F0F@0.9:t=fill,"
              "format=yuv420p[v];"
              "[1:a]aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,volume=0.65[aw];"
              "[2:a]aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
              "adelay=120|120,volume=0.55[ab];"
              f"[3:a][aw][ab]amix=inputs=3:duration=first:normalize=0,"
              f"afade=t=out:st={fade_out:.2f}:d=0.22,"
              "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a]")
    cortes.rodar(["ffmpeg", "-y", "-loop", "1", "-i", str(png),
                  "-i", str(whoosh), "-i", str(boom),
                  "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                  "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
                  "-t", f"{segundos:.2f}", "-r", "30", *cortes.args_encoder_video(intermediario=False),
                  "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                  "-shortest", str(destino)])
    return destino


def _segmento_corte(mp4: Path, lateral: Path, destino: Path):
    tem_audio = cortes.tem_audio(mp4)
    whoosh = efeitos.gerar_whoosh(destino.parent, duracao=0.50)
    filtro = ("[0:v]split[a][b];"
              f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,"
              "eq=brightness=-0.12[fundo];"
              f"[b]scale=-2:{H}[frente];"
              "[fundo][frente]overlay=(W-w)/2:0[v1];"
              "[v1][1:v]overlay=0:0,fade=t=in:st=0:d=0.16,format=yuv420p[v]")
    cmd = ["ffmpeg", "-y", "-i", str(mp4), "-loop", "1", "-i", str(lateral)]
    if tem_audio:
        cmd += ["-i", str(whoosh)]
        filtro += ";" + _filtro_audio_segmento("[0:a]", whoosh_idx=2)
        mapa_a = "[a]"
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        mapa_a = "2:a"
    cmd += ["-filter_complex", filtro, "-map", "[v]", "-map", mapa_a,
            "-shortest", "-r", "30", *cortes.args_encoder_video(intermediario=False),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(destino)]
    cortes.rodar(cmd)
    return destino


def gerar_compilacao(dias=7, n=5, log=print, canal=None, minutos=None, deitado=None):
    """Compilação horizontal. minutos = tamanho alvo (padrão do config: 8 min → mais horas assistidas).
    deitado=True usa o trecho ORIGINAL horizontal (ou o corte longo, se existir) em tela cheia; se não
    der, cai no estilo antigo (corte em pé no meio com fundo desfocado)."""
    cfg = cortes.carregar_config()
    minutos = float(minutos if minutos is not None else cfg.get("compilacao_minutos", 8))
    deitado = cfg.get("compilacao_deitada", True) if deitado is None else deitado
    escolhidos = escolher(dias, n, canal=canal, alvo_seg=minutos * 60 if minutos else None)
    if len(escolhidos) < 3:
        log(f"❌ Preciso de pelo menos 3 cortes dos últimos {dias} dias (achei {len(escolhidos)}).")
        return None
    pasta_saida = cortes.PASTA_PROJETO / "cortes_prontos" / "_compilacoes"
    pasta_saida.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="compilacao_"))
    try:
        hoje = dt.date.today()
        ini = hoje - dt.timedelta(days=dias)
        periodo = f"{ini:%d/%m} a {hoje:%d/%m}"
        total = len(escolhidos)
        log(f"Montando a compilação TOP {total} ({periodo})...")
        cabeca = f"MELHORES DE {canal.upper()}" if canal else f"TOP {total} DA SEMANA"
        partes = [_segmento_cartao(_cartao(cabeca, periodo, tmp / "intro.png"), DURACAO_INTRO, tmp / "00.mp4")]
        longos = _longos_por_curto() if deitado else {}
        capitulos = ["0:00 Intro"]
        tempo = DURACAO_INTRO
        for i, (views, nota, mp4, f) in enumerate(reversed(escolhidos)):
            pos = total - i
            log(f"   #{pos}: {f.get('titulo', '')[:60]}")
            seg = None
            if deitado:
                rod = _rodape(pos, f.get("pergunta") or f.get("titulo", ""), f.get("canal", ""), tmp / f"rod{pos}.png")
                origem = longos.get(mp4.name) or _fonte_deitada(f, tmp, i)
                if origem:
                    try:
                        seg = _segmento_deitado(Path(origem), rod, tmp / f"{i + 1:02d}.mp4")
                    except Exception as e:
                        log(f"      (trecho deitado falhou: {str(e)[:80]} — uso o corte em pé)")
                        seg = None
            if seg is None:
                lat = _lateral(pos, f.get("pergunta") or f.get("titulo", ""), f.get("canal", ""), tmp / f"lat{pos}.png")
                seg = _segmento_corte(mp4, lat, tmp / f"{i + 1:02d}.mp4")
            m, s = divmod(int(round(tempo)), 60)
            capitulos.append(f"{m}:{s:02d} #{pos} — {f.get('titulo', '')[:70]}")
            tempo += cortes.duracao_video(seg)
        partes += sorted(tmp.glob("[0-9][0-9].mp4"))[1:]
        lista = tmp / "lista.txt"
        lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in partes), encoding="utf-8")
        destino = pasta_saida / (f"{cortes.nome_seguro(canal, 30)}_semana_{hoje:%Y-%m-%d}.mp4" if canal
                                 else f"Top{total}_semana_{hoje:%Y-%m-%d}.mp4")
        cortes.rodar(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy",
                      "-movflags", "+faststart", str(destino)])
        canais = sorted({f.get("canal") for _, _, _, f in escolhidos if f.get("canal")})
        titulo = (f"MELHORES MOMENTOS DE {canal.upper()} NA SEMANA ({periodo})" if canal else
                  f"TOP {total} MOMENTOS MAIS INSANOS DA SEMANA ({periodo})")
        descricao = ("Os melhores cortes da semana!\n\n" + "\n".join(capitulos) +
                     ("\n\nCanais: " + ", ".join(canais) if canais else "") + "\n\n#cortes #melhoresmomentos")
        ficha = {"tipo": "compilacao", "titulo": titulo, "descricao": descricao, "hashtags": ["#cortes"],
                 "perfil": "Padrão", "criado": dt.datetime.now().isoformat(timespec="seconds"),
                 "status": "novo", "itens": [str(m.name) for _, _, m, _ in escolhidos]}
        destino.with_suffix(".json").write_text(json.dumps(ficha, indent=2, ensure_ascii=False), encoding="utf-8")
        destino.with_suffix(".txt").write_text(titulo + "\n\n" + descricao, encoding="utf-8")
        log(f"✅ Compilação pronta: {destino.name} ({int(tempo // 60)} min) — está na Galeria.")
        return destino
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
