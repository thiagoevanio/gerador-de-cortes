"""Música de fundo (3.9): escolhe uma faixa da pasta musicas/ pelo clima do corte.

Coloque músicas livres de direitos (Biblioteca de Áudio do YouTube, Pixabay Music, etc.) em:
    musicas/animada      humor, gameplay, reação
    musicas/tensa        polêmica, treta, choque, suspense
    musicas/emocionante  emoção, superação
    musicas/calma        informativo, reflexão, podcast
Arquivos soltos direto em musicas/ servem para qualquer clima.
O volume abaixa sozinho quando alguém fala (ducking) — isso é feito no render (cortes.renderizar).
"""
import json
import random
from pathlib import Path

PASTA = Path(__file__).resolve().parent / "musicas"
EXTENSOES = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac"}
CLIMAS = ("animada", "tensa", "emocionante", "calma")
TOM_PARA_CLIMA = {"humor": "animada", "gameplay": "animada", "polemica": "tensa", "choque": "tensa",
                  "suspense": "tensa", "emocao": "emocionante", "informativo": "calma", "reflexao": "calma"}
_HISTORICO = "_ultimas.json"

LEIA = """MÚSICA DE FUNDO DOS CORTES
==========================
Coloque aqui músicas LIVRES DE DIREITOS AUTORAIS (mp3, m4a, wav, ogg...).
Músicas comerciais (de artistas/gravadoras) podem tirar o som do vídeo ou derrubar o corte.

Boas fontes grátis: Biblioteca de Áudio do YouTube (YouTube Studio > Biblioteca de áudio),
Pixabay Music, Free Music Archive (licença CC0/CC-BY).

Separe por clima (a IA já diz o tom de cada corte e o sistema escolhe a pasta certa):
  animada/      humor, gameplay, reação
  tensa/        polêmica, treta, choque, suspense
  emocionante/  emoção, superação
  calma/        informativo, reflexão, podcast
Arquivos soltos aqui mesmo (fora das pastas) servem para qualquer clima.

O volume abaixa sozinho quando alguém fala e volta nas pausas.
Desligar: aba Visual > "Música de fundo". Volume: "musica_volume" no config.json (padrão 0.16).
"""


def garantir_pastas(pasta: Path = PASTA):
    """Cria musicas/ com as subpastas e o LEIA-ME (não mexe em nada que já exista)."""
    try:
        for c in CLIMAS:
            (pasta / c).mkdir(parents=True, exist_ok=True)
        leia = pasta / "LEIA-ME.txt"
        if not leia.exists():
            leia.write_text(LEIA, encoding="utf-8")
    except OSError:
        pass


def clima_do(tom, tipo=None):
    if tom in TOM_PARA_CLIMA:
        return TOM_PARA_CLIMA[tom]
    if tipo == "jogo":
        return "animada"
    if tipo == "podcast":
        return "calma"
    return None


def _faixas(pasta: Path):
    if not pasta.is_dir():
        return []
    return sorted(a for a in pasta.iterdir() if a.is_file() and a.suffix.lower() in EXTENSOES
                  and a.stat().st_size > 20_000)


def escolher(tom=None, tipo=None, pasta: Path = PASTA, rng=random):
    """Devolve uma faixa (Path) ou None se não houver música. Prefere a pasta do clima; se ela estiver
    vazia, usa as soltas; se não houver nenhuma das duas, qualquer uma. Evita repetir as últimas."""
    garantir_pastas(pasta)
    clima = clima_do(tom, tipo)
    candidatas = (_faixas(pasta / clima) if clima else []) or _faixas(pasta)
    if not candidatas:
        candidatas = [f for c in CLIMAS for f in _faixas(pasta / c)]
    if not candidatas:
        return None
    hist_arq = pasta / _HISTORICO
    try:
        recentes = json.loads(hist_arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        recentes = []
    nomes = {str(c.relative_to(pasta)) for c in candidatas}
    evitar = set(recentes[-max(0, len(nomes) - 1):]) if len(nomes) > 1 else set()
    livres = [c for c in candidatas if str(c.relative_to(pasta)) not in evitar] or candidatas
    escolhida = rng.choice(livres)
    try:
        hist_arq.write_text(json.dumps((recentes + [str(escolhida.relative_to(pasta))])[-20:],
                                       ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return escolhida
