"""Limites locais de recursos e diagnóstico reprodutível."""
import datetime
import importlib.metadata
import os
import shutil
import sqlite3
from contextlib import closing
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent


def configurar_ffmpeg():
    candidatos = [None]
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        raiz = Path(os.environ['LOCALAPPDATA']) / 'Microsoft/WinGet/Packages'
        candidatos += [p.parent for p in raiz.glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe')]
    for pasta in candidatos:
        executavel = str(pasta / 'ffmpeg.exe') if pasta else shutil.which('ffmpeg')
        if not executavel:
            continue
        try:
            r = subprocess.run([executavel, '-version'], capture_output=True, timeout=10,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if r.returncode == 0:
                if pasta:
                    os.environ['PATH'] = str(pasta) + os.pathsep + os.environ.get('PATH', '')
                return executavel
        except (OSError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError('FFmpeg não está executável. Repare a instalação em Contas & IA.')


def verificar_disco(caminho, minimo_gb=2):
    livre = shutil.disk_usage(caminho).free / 1024**3
    if livre < minimo_gb:
        raise RuntimeError(f'Espaço insuficiente: {livre:.1f} GB livres; reserva mínima {minimo_gb:g} GB.')
    return livre


def reservar_ia(limite, arquivo=None, dia=None):
    if limite <= 0:
        return True
    dia = dia or datetime.date.today().isoformat()
    with closing(sqlite3.connect(str(arquivo or BASE / 'consumo_ia.sqlite3'), timeout=20)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS consumo (dia TEXT PRIMARY KEY, chamadas INTEGER NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT chamadas FROM consumo WHERE dia=?', (dia,)).fetchone()
        if row and row[0] >= limite:
            return False
        db.execute('INSERT INTO consumo VALUES(?,1) ON CONFLICT(dia) DO UPDATE SET chamadas=chamadas+1', (dia,))
    return True


def diagnostico():
    pacotes = {}
    for nome in ['yt-dlp', 'streamlink', 'faster-whisper', 'numpy', 'Pillow', 'opencv-python-headless']:
        try:
            pacotes[nome] = importlib.metadata.version(nome)
        except importlib.metadata.PackageNotFoundError:
            pacotes[nome] = 'não instalado'
    try:
        ffmpeg = configurar_ffmpeg()
    except RuntimeError as e:
        ffmpeg = str(e)
    try:
        from otimizador_corte import relatorio_economia_tokens
        economia_ia = relatorio_economia_tokens()
    except Exception:
        economia_ia = {}
    return dict(python=sys.version.split()[0], bibliotecas=pacotes, ffmpeg=ffmpeg,
                disco_livre_gb=round(shutil.disk_usage(BASE).free/1024**3, 2),
                economia_ia=economia_ia)


def limpar_gravacoes(raiz, dias, protegidas, em_uso, agora=None):
    """Retenção opt-in; somente subpastas reais da pasta de gravações do projeto."""
    if dias <= 0:
        return []
    raiz = Path(raiz).resolve()
    if not raiz.is_relative_to(BASE.resolve()) or raiz == BASE.resolve():
        raise ValueError('Pasta de retenção fora da área de gravações.')
    agora = agora or time.time()
    protegidas = {Path(p).resolve() for p in protegidas}
    removidas = []
    if not raiz.is_dir():
        return removidas
    for pasta in raiz.iterdir():
        alvo = pasta.resolve()
        if not pasta.is_dir() or pasta.is_symlink() or (hasattr(pasta, 'is_junction') and pasta.is_junction()):
            continue
        if not alvo.is_relative_to(raiz) or alvo == raiz or alvo in protegidas or em_uso(alvo):
            continue
        ultima = max([pasta.stat().st_mtime] + [p.stat().st_mtime for p in pasta.iterdir() if p.is_file()])
        if agora-ultima > dias*86400:
            shutil.rmtree(alvo)
            removidas.append(pasta.name)
    return removidas
