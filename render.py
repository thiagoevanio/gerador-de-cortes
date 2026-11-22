"""Render final do corte 9:16 com ffmpeg (enquadramento, efeitos, legenda, extras e áudio).
Saiu do cortes.py na 3.13.

As configurações continuam morando no cortes.py: aqui elas são lidas como `cortes.NOME` na hora de
usar, então trocar de perfil/config vale na mesma hora.
"""
from infraestrutura import exclusividade, salvar_json
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys


class _Cortes:
    """Acesso tardio ao módulo cortes (evita importação circular). Ler e gravar passam pelo cortes."""

    @staticmethod
    def _modulo():
        import importlib
        return sys.modules.get("cortes") or importlib.import_module("cortes")

    def __getattr__(self, nome):
        return getattr(self._modulo(), nome)

    def __setattr__(self, nome, valor):
        setattr(self._modulo(), nome, valor)


cortes = _Cortes()


def renderizar(video: Path, topo: Path, legenda: Path | None, saida: Path, modo: str,
               faixa: Path | None = None, y_faixa: int = 0, expr_x: str | None = None,
               gancho_t: float | None = None, boom: Path | None = None, layout: dict | None = None,
               extras: list | None = None, estilo_render: dict | None = None,
               previa: tuple | None = None):
    """Monta o 9:16. layout = {'top': (w,h,x,y), 'bot': (w,h,x,y), 'escurecer_top': [...],
    'escurecer_bot': [...]} troca a foto de cima por vídeo (podcast / jogo+facecam).
    extras = [{'png', 'x', 'y', 'ini', 'fim'}] (emojis, selo de parte, 'continua na parte 2').
    estilo_render (template de edição) = {'cor': filtros, 'ritmo': [(a,b)], 'ritmo_int': 0.05,
    'barra': '#hex', 'flash': [t], 'sfx': [{'arquivo','t','vol'}], 'musica': {'arquivo','vol'},
    'enfase': [t], 'enfase_int': 0.08, 'zoom_lento': 0.05}.
    previa = (a, b): o trecho [a, b] (o momento mais forte) entra repetido no começo, DENTRO desta
    montagem — sem re-encode intermediário. As legendas/efeitos já chegam na linha do tempo final."""
    import templates_edicao as te
    er = estilo_render or {}
    destino_final = Path(saida).resolve()
    saida = video.parent / ("exportacao_" + __import__("uuid").uuid4().hex + ".mp4")
    cortes.log("Montando o vídeo 9:16 (leva uns minutos)...")
    d_previa = max(0.0, previa[1] - previa[0]) if previa else 0.0
    dur_total = _duracao_util(video) + d_previa
    fps = fps_saida(video)
    entradas = ["-i", video.name]
    idx = 1
    zoom = ""
    cor = er.get("cor") or ""
    cheio = topo is None and not layout           # estilo clean: o vídeo ocupa a tela toda (sem foto/faixa)
    alt_v = cortes.ALTURA if cheio else cortes.ALTURA_VIDEO
    vsrc, pre = "[0:v]", ""
    if previa:                                    # prévia do gancho: emenda dentro do grafo. A prévia é
        a, b = previa                             # uma 2ª leitura do MESMO arquivo com -ss (seek rápido),
        entradas = ["-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", video.name, "-i", video.name]
        idx = 2                                   # pra não decodificar o vídeo inteiro duas vezes
        pre = ("[0:v]setpts=PTS-STARTPTS[pgv];[1:v]setpts=PTS-STARTPTS[prv];"
               "[pgv][prv]concat=n=2:v=1:a=0[vcat];")
        vsrc = "[vcat]"
    fator = []
    if gancho_t is not None and not layout:      # "soco" de zoom: sobe até 14% e volta em ~0,7s
        z = f"max(0,1-abs(t-{gancho_t + 0.15:.2f})/0.45)"
        fator.append(f"(1+0.14*{z})")
    if er.get("ritmo") and er.get("ritmo_int") and not layout:   # jump-cut: zoom alternado por frase
        fator.append(te.expr_ritmo(er["ritmo"], float(er["ritmo_int"])))
    if er.get("enfase") and er.get("enfase_int") and not layout:  # soco curto em cada palavra-chave
        import acabamento
        fator.append(acabamento.expr_enfase(er["enfase"][:6], float(er["enfase_int"])))
    if er.get("zoom_lento") and not layout:      # zoom quase imperceptível do início ao fim (retenção)
        fator.append(f"(1+{float(er['zoom_lento']):.3f}*t/{max(1.0, dur_total):.2f})")
    if fator:
        f_expr = "*".join(fator)
        zoom = (f",scale=w='{cortes.LARGURA}*{f_expr}':h='{alt_v}*{f_expr}':eval=frame:flags=bicubic,"
                f"crop={cortes.LARGURA}:{alt_v}")
    alt_topo = cortes.ALTURA_FOTO + cortes.ALTURA_FAIXA

    def escurecer(trechos):
        if not trechos:
            return ""
        cond = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in trechos[:120])
        return f",drawbox=x=0:y=0:w=iw:h=ih:color=black@0.42:t=fill:enable='{cond}'"

    def destacar_foco(trechos, w_alvo, h_alvo, cor_borda="0xFFE600"):
        if not trechos:
            return ""
        cond = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in trechos[:80])
        return (f",scale=w='if({cond},{w_alvo}*1.06,{w_alvo})':h='if({cond},{h_alvo}*1.06,{h_alvo})':eval=frame,"
                f"crop={w_alvo}:{h_alvo},"
                f"drawbox=x=0:y=0:w=10:h=ih:color={cor_borda}@0.92:t=fill:enable='{cond}'")

    if layout:
        tw, th, tx, ty = layout["top"]
        bw, bh, bx, by = layout["bot"]
        filtro = (f"{pre}{vsrc}split[va][vb];"
                  f"[va]crop={tw}:{th}:{tx}:{ty},scale={cortes.LARGURA}:{alt_topo}:flags=lanczos{cor}"
                  f"{destacar_foco(layout.get('foco_top'), cortes.LARGURA, alt_topo, '0xFFE600')},setsar=1"
                  f"{escurecer(layout.get('escurecer_top'))}[top];"
                  f"[vb]crop={bw}:{bh}:{bx}:{by},scale={cortes.LARGURA}:{cortes.ALTURA_VIDEO}:flags=lanczos{cor}"
                  f"{destacar_foco(layout.get('foco_bot'), cortes.LARGURA, cortes.ALTURA_VIDEO, '0x8FE3FF')},setsar=1"
                  f"{escurecer(layout.get('escurecer_bot'))}[vid];"
                  f"[top][vid]vstack=inputs=2:shortest=1,format=yuv420p[base]")
    else:
        if modo == "inteiro":
            parte = (f"{pre}{vsrc}split[a][b];"
                     f"[a]scale={cortes.LARGURA}:{alt_v}:force_original_aspect_ratio=increase,"
                     f"crop={cortes.LARGURA}:{alt_v},boxblur=20:2[fundo];"
                     f"[b]scale={cortes.LARGURA}:{alt_v}:force_original_aspect_ratio=decrease:flags=lanczos{cor}[frente];"
                     f"[fundo][frente]overlay=(W-w)/2:(H-h)/2{zoom},setsar=1,format=yuv420p[vid]")
        else:
            x = f":x='{expr_x}':y=0" if expr_x else ""
            parte = (f"{pre}{vsrc}scale={cortes.LARGURA}:{alt_v}:force_original_aspect_ratio=increase:flags=lanczos,"
                     f"crop={cortes.LARGURA}:{alt_v}{x}{cor}{zoom},setsar=1,format=yuv420p[vid]")
        if cheio:
            filtro = parte[:-len("[vid]")] + "[base]"
        else:
            entradas += ["-loop", "1", "-i", topo.name]
            filtro = (parte + ";"
                      f"[{idx}:v]scale={cortes.LARGURA}:{alt_topo},setsar=1,format=yuv420p[top];"
                      f"[top][vid]vstack=inputs=2:shortest=1[base]")
            idx += 1
    atual = "base"
    if faixa:
        entradas += ["-loop", "1", "-i", faixa.name]
        filtro += f";[{idx}:v]format=rgba[fx];[{atual}][fx]overlay=0:{y_faixa}:shortest=1,format=yuv420p[cfx]"
        atual = "cfx"
        idx += 1
    if er.get("flash"):                          # flash rápido (2-3 quadros) no gancho / na virada
        cond = "+".join(f"between(t,{t0:.2f},{t0 + 0.09:.2f})" for t0 in er["flash"][:6])
        filtro += f";[{atual}]eq=brightness=0.32:saturation=0.7:enable='{cond}'[flx]"
        atual = "flx"
    if legenda:
        fontes_dir = cortes.PASTA_PROJETO / "fontes"
        extra_fonte = ""
        if fontes_dir.is_dir():                   # fontes do projeto (ex.: Bangers) visíveis pro libass
            for f in fontes_dir.glob("*.[ot]tf"):
                alvo = video.parent / f.name
                if not alvo.exists():
                    try:
                        shutil.copy2(f, alvo)
                    except OSError:
                        pass
            extra_fonte = ":fontsdir=."
        filtro += f";[{atual}]ass={legenda.name}{extra_fonte}[leg]"
        atual = "leg"
    for k, ex in enumerate(extras or []):
        entradas += ["-loop", "1", "-i", Path(ex["png"]).name]
        fade = f",fade=t=in:st={ex['ini']:.2f}:d=0.15:alpha=1" if ex.get("fade", True) else ""
        filtro += (f";[{idx}:v]format=rgba{fade}[e{k}];[{atual}][e{k}]overlay={int(ex['x'])}:{int(ex['y'])}:"
                   f"shortest=1:enable='between(t,{ex['ini']:.2f},{ex['fim']:.2f})'[x{k}]")
        atual = f"x{k}"
        idx += 1
    if er.get("barra"):                          # barra de progresso no topo (segura a retenção)
        dur_barra = max(1.0, dur_total)
        cor_barra = str(er["barra"]).lstrip("#")[:6] or "FFE600"
        filtro += (f";color=c=0x{cor_barra}:s={cortes.LARGURA}x12:r={fps}[pbar];"
                   f"[{atual}][pbar]overlay=x='-w+w*t/{dur_barra:.2f}':y=0:shortest=1[pb]")
        atual = "pb"
    filtro += f";[{atual}]null[final]"
    mapa_audio = []
    if tem_audio(video):
        asrc = "[0:a]"
        if previa:                                # prévia do gancho também no áudio, com micro-fades
            filtro += (f";[0:a]asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.02,"
                       f"afade=t=out:st={max(0.0, d_previa - 0.12):.3f}:d=0.12[pga];"
                       f"[1:a]asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.03[pra];"
                       f"[pga][pra]concat=n=2:v=0:a=1[acat]")
            asrc = "[acat]"
        fonte_audio = asrc
        sons = []                                 # (arquivo, segundos, volume, filtro extra)
        if boom and gancho_t is not None:
            sons.append((Path(boom).name, gancho_t, 0.68, "lowpass=f=240,"))
        if previa:                                # 'whoosh' na virada da prévia pro início do vídeo
            import efeitos
            whoosh = efeitos.gerar_whoosh(video.parent, duracao=0.45)
            sons.append((whoosh.name, max(0.0, d_previa - 0.22), 0.55, ""))
        for s_ in (er.get("sfx") or [])[:6]:
            if s_.get("arquivo") and (video.parent / Path(s_["arquivo"]).name).exists():
                sons.append((Path(s_["arquivo"]).name, float(s_.get("t", 0)), float(s_.get("vol", 0.4)), ""))
        mus = er.get("musica") or {}
        mus_arq = (video.parent / Path(mus["arquivo"]).name) if mus.get("arquivo") else None
        if mus_arq is not None and not mus_arq.exists():
            mus_arq = None
        if sons or mus_arq:
            fmt = "aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
            filtro += f";{asrc}{fmt}[a0]"
            rotulos = ["[a0]"]
            if mus_arq:                           # música em loop, abaixando quando a voz aparece (ducking)
                dur_m = max(1.0, cortes.duracao_video(video) + d_previa)
                vol_m = max(0.0, min(0.6, float(mus.get("vol", 0.16))))
                entradas += ["-stream_loop", "-1", "-i", mus_arq.name]
                filtro += (f";[a0]asplit=2[a0v][a0sc]"
                           f";[{idx}:a]{fmt},atrim=0:{dur_m:.2f},asetpts=PTS-STARTPTS,"
                           f"afade=t=in:st=0:d={0.15 if mus.get('loop') else 0.8},"
                           f"afade=t=out:st={max(0.0, dur_m - (0.15 if mus.get('loop') else 1.8)):.2f}"
                           f":d={0.15 if mus.get('loop') else 1.8},"
                           f"volume={vol_m:.3f}[musq]"
                           f";[musq][a0sc]sidechaincompress=threshold=0.03:ratio=5:attack=20:"
                           f"release=450:makeup=1[musd]")
                rotulos = ["[a0v]", "[musd]"]
                idx += 1
            for k, (arq, t0, vol, extra) in enumerate(sons):
                entradas += ["-i", arq]
                ms = int(max(0, t0) * 1000)
                filtro += f";[{idx}:a]{fmt},{extra}adelay={ms}|{ms},volume={vol:.2f}[sf{k}]"
                rotulos.append(f"[sf{k}]")
                idx += 1
            filtro += f";{''.join(rotulos)}amix=inputs={len(rotulos)}:duration=first:normalize=0[mix]"
            fonte_audio = "[mix]"
        if cortes.AUDIO_PADRAO:
            chiado = not er.get("voz_limpa")      # voz já limpa pela IA no começo do corte: sem afftdn
            filtro += (f";{fonte_audio}{_cadeia_voz(chiado)},"
                       f"{_loudnorm_medido(video, chiado)},aresample=48000,"
                       f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aud]")
        else:
            filtro += (f";{fonte_audio}aresample=48000,"
                       f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aud]")
        mapa_audio = ["-map", "[aud]"]
    cortes.rodar(["ffmpeg", "-y", *entradas,
           "-filter_complex", filtro, "-map", "[final]", *mapa_audio,
           "-shortest", "-r", str(fps), "-g", str(fps * 2), *cortes.args_encoder_video(intermediario=False),
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
           str(saida.resolve())], cwd=video.parent, progresso=("Montando o vídeo", dur_total))
    from qualidade import inspecionar
    relatorio=inspecionar(saida,dur_total,exigir_audio=tem_audio(video),
                         aprofundar=cortes.carregar_config(cortes.PERFIL_EM_USO).get('revisao_tecnica',False))
    if not relatorio['aprovado']:
        raise RuntimeError('Revisão técnica: '+'; '.join(relatorio['erros']))
    os.replace(saida,destino_final)
    salvar_json(destino_final.with_suffix('.qualidade.json'),relatorio)
    for aviso in relatorio['avisos']:print('   Revisão: '+aviso)


def _cadeia_voz(chiado=True):
    """Filtros de voz do render (antes do nivelamento): tira grave de ambiente, dá presença e comprime.
    chiado=False quando a voz já foi limpa pelo RNNoise (o afftdn em cima só tiraria brilho)."""
    return (f"highpass=f=75{cortes.filtro_chiado() if chiado else ''},"
            f"equalizer=f=2800:t=q:w=1.2:g=2.0,"
            f"acompressor=threshold=-20dB:ratio=3:attack=8:release=220:makeup=2")


def _loudnorm_medido(video: Path, chiado=True) -> str:
    """Nivelamento de volume em 2 passadas: mede primeiro (só o áudio, rápido) e aplica de forma
    LINEAR — sem o 'bombeamento' do modo dinâmico. Se a medição falhar, volta pro modo de sempre."""
    alvo = "loudnorm=I=-14:TP=-1.5:LRA=11"
    try:
        r = subprocess.run(["ffmpeg", "-v", "info", "-nostdin", "-i", str(video), "-map", "0:a:0",
                            "-af", f"{_cadeia_voz(chiado)},{alvo}:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=240, creationflags=cortes.SEM_JANELA)
        m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
        medidos = {k: float(m[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
        if not -50 < medidos["input_i"] < 0:      # áudio quase mudo: o modo dinâmico se vira melhor
            return alvo
        return (alvo + f":measured_I={medidos['input_i']:.2f}:measured_TP={medidos['input_tp']:.2f}"
                f":measured_LRA={medidos['input_lra']:.2f}:measured_thresh={medidos['input_thresh']:.2f}"
                f":offset={medidos['target_offset']:.2f}:linear=true")
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        return alvo


def fps_saida(video: Path) -> int:
    """30 ou 60: segue a fonte quando ela é 60 fps (gameplay fica fluido), fora do Modo PC fraco."""
    if cortes.MODO_PC_FRACO or not cortes.carregar_config().get("fps_auto", True):
        return 30
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=avg_frame_rate", "-of", "csv=p=0", str(video)], capture_output=True,
                       text=True, creationflags=cortes.SEM_JANELA)
    try:
        num, den = (r.stdout.strip().split(",")[0]).split("/")
        return 60 if float(num) / max(1.0, float(den)) >= 48 else 30
    except (ValueError, ZeroDivisionError):
        return 30


def _duracao_util(video: Path) -> float:
    """Duração que o render consegue entregar: a da trilha MAIS CURTA (o render usa -shortest).
    O 'format duration' pega a mais longa, e no trecho baixado do YouTube elas diferem."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
                        "-of", "json", str(video)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=cortes.SEM_JANELA)
    try:
        durs = [float(st["duration"]) for st in json.loads(r.stdout).get("streams", [])
                if st.get("codec_type") in ("video", "audio") and st.get("duration") not in (None, "N/A")]
    except (ValueError, KeyError, TypeError):
        durs = []
    return min(durs) if durs else cortes.duracao_video(video)


def tem_audio(video: Path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                        "stream=index", "-of", "csv=p=0", str(video)], capture_output=True,
                       text=True, creationflags=cortes.SEM_JANELA)
    return bool(r.stdout.strip())


def info_video(video: Path):
    r = cortes.rodar(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height", "-of", "csv=p=0", str(video)])
    try:
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        return w, h
    except ValueError:
        return 1280, 720
