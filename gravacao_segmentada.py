"""Playlist de leitura finita sobre segmentos completos de uma captura HLS."""
import os
import re
import tempfile
from pathlib import Path


def comando_ffmpeg(pasta, segundos=6):
    pasta = Path(pasta)
    return ['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', 'pipe:0', '-c', 'copy',
            '-f', 'hls', '-hls_time', str(max(2, segundos)), '-hls_list_size', '0',
            '-hls_playlist_type', 'event', '-hls_flags', 'independent_segments+temp_file',
            '-hls_segment_filename', str(pasta/'segmento_%06d.ts'), str(pasta/'captura.m3u8')]


def snapshot(pasta):
    pasta = Path(pasta)
    origem, destino = pasta/'captura.m3u8', pasta/'live.m3u8'
    if not origem.is_file():
        return destino
    texto = origem.read_text(encoding='utf-8')
    if not '#EXTINF:' in texto:
        return destino
    texto = texto.replace('#EXT-X-PLAYLIST-TYPE:EVENT', '#EXT-X-PLAYLIST-TYPE:VOD')
    if '#EXT-X-ENDLIST' not in texto:
        texto += '\n#EXT-X-ENDLIST\n'
    if destino.is_file() and destino.read_text(encoding='utf-8') == texto:
        return destino
    fd, nome = tempfile.mkstemp(dir=pasta, suffix='.m3u8.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(texto)
        try:
            os.replace(nome, destino)
        except PermissionError:
            pass  # Um leitor do Windows ainda está usando a versão anterior.
    finally:
        if os.path.exists(nome): os.unlink(nome)
    return destino


def duracao(playlist):
    return sum(float(x) for x in re.findall(r'#EXTINF:([\d.]+)', Path(playlist).read_text(encoding='utf-8')))
