"""Inspeção de mídia e prévias sem dependência de serviços externos."""
import json
import re
import subprocess
from pathlib import Path


def inspecionar(video, duracao_esperada=None, exigir_audio=False, aprofundar=True):
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(video)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60, creationflags=flags)
    if r.returncode:
        raise RuntimeError('Arquivo de saída não pode ser lido: ' + r.stderr[-500:])
    info = json.loads(r.stdout)
    streams = info.get('streams', [])
    dur = float(info.get('format', {}).get('duration') or 0)
    erros, avisos = [], []
    vs = [s for s in streams if s.get('codec_type') == 'video']
    audio = [s for s in streams if s.get('codec_type') == 'audio']
    if not vs or dur < 0.5:
        erros.append('Vídeo ausente ou duração inválida.')
    if exigir_audio and not audio:
        erros.append('Áudio da fonte desapareceu na saída.')
    if duracao_esperada and abs(dur - duracao_esperada) > max(0.75, duracao_esperada * 0.03):
        # Trecho baixado do YouTube costuma ter vídeo e áudio de tamanhos um pouco diferentes
        # (o corte começa no quadro-chave). Só é ERRO se o vídeo saiu muito mais curto.
        if dur < duracao_esperada * 0.6:
            erros.append(f'Vídeo exportado ficou curto demais ({dur:.1f}s de {duracao_esperada:.1f}s).')
        else:
            avisos.append(f'Duração final {dur:.1f}s (edição tinha {duracao_esperada:.1f}s).')
    if audio and vs:
        da, dv = float(audio[0].get('duration') or dur), float(vs[0].get('duration') or dur)
        if abs(da - dv) > 0.5:
            avisos.append('Durações de áudio e vídeo diferem; revisar sincronismo.')
    if aprofundar and vs:
        cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-i', str(video), '-vf',
               'scale=320:-2,blackdetect=d=1.5:pix_th=0.10,freezedetect=n=-55dB:d=3']
        if audio:
            cmd += ['-af', 'volumedetect']
        cmd += ['-f', 'null', '-']
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=max(120, min(1800, int(dur * 5))), creationflags=flags)
        if r.returncode:
            erros.append('Falha na decodificação completa do arquivo.')
        if 'black_start:' in r.stderr:
            avisos.append('Há trecho escuro prolongado; revisar.')
        if 'freeze_start:' in r.stderr:
            avisos.append('Há imagem parada por três segundos ou mais; pode ser intencional.')
        pico = re.search(r'max_volume:\s*(-?[\d.]+) dB', r.stderr)
        if pico and float(pico[1]) >= -0.1:
            avisos.append('Pico de áudio próximo do limite digital.')
    return dict(aprovado=not erros, erros=erros, avisos=avisos, duracao=round(dur, 3),
                resolucao=[vs[0].get('width'), vs[0].get('height')] if vs else None)


def previa(fonte, destino, inicio=0, fim=None):
    if inicio < 0 or (fim is not None and fim <= inicio):
        raise ValueError('Intervalo de prévia inválido.')
    cmd = ['ffmpeg', '-y', '-v', 'error', '-ss', str(inicio), '-i', str(fonte)]
    if fim is not None:
        cmd += ['-t', str(fim - inicio)]
    cmd += ['-vf', 'scale=480:-2', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '29',
            '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(destino)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return Path(destino)


def comparar(video, referencia, ajuste="", metrica="vmaf"):
    """Nota de quão perto 'video' (depois do filtro 'ajuste', ex.: 'scale=1920:1080,unsharp=...') fica
    da 'referencia' (o original bom). metrica: 'vmaf' (0-100, o medidor da Netflix: como uma pessoa
    acha que ficou) ou 'ssim' (0-1: estrutura da imagem; cai quando a nitidez exagera e cria contorno).
    É a régua usada pra escolher os filtros de imagem — nada de 'achismo'. None se não der pra medir."""
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    filtro = f"[0:v]{ajuste + ',' if ajuste else ''}setsar=1[d];[1:v]setsar=1[r];[d][r]" + (
        "libvmaf=n_threads=4" if metrica == "vmaf" else "ssim")
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-i', str(video), '-i', str(referencia),
                        '-filter_complex', filtro, '-f', 'null', '-'], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=1800, creationflags=flags)
    padrao = r"VMAF score: ([\d.]+)" if metrica == "vmaf" else r"All:([\d.]+)"
    achados = re.findall(padrao, r.stderr)
    return float(achados[-1]) if achados else None
