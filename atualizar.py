"""
Atualização automática pelo GitHub.

Como funciona: você publica uma "Release" no seu repositório do GitHub com o .zip do projeto
(ou só cria a release, que o GitHub já gera o .zip do código). O programa compara a versão
da release (ex: v3.1.0) com o VERSAO.txt e, se for mais nova, baixa e troca os arquivos —
sem mexer nas suas configurações, contas, cortes e gravações.

Se a pasta do projeto for um repositório git (o jeito recomendado), a atualização é feita com
'git pull' e é recusada enquanto houver alteração sua não salva (commit) — nada é sobrescrito.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQ_VERSAO = PASTA / "VERSAO.txt"
# nunca são substituídos
PROTEGIDOS = {"config.json", "canais.json", "estado.json", "agenda_postagens.json", "aprendizado.json",
              "tendencias.json", "resultados_extra.json", "client_secret.json", "monitor.log"}
PASTAS_PROTEGIDAS = {"cortes_prontos", "gravacoes", "__pycache__", ".git", "analises", "feedback_editorial", "_validacao", "_jobs"}


def versao_atual():
    try:
        return ARQ_VERSAO.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def _tupla(v):
    nums = [int(x) for x in "".join(c if c.isdigit() or c == "." else " " for c in v).split()[0].split(".") if x.isdigit()] \
        if any(c.isdigit() for c in v) else [0]
    return tuple(nums + [0] * (3 - len(nums)))


def verificar_git(interativo=False):
    """Projeto no git: busca o GitHub (git fetch) e compara. Funciona com repositório privado (usa o login
    do git). Sem 'interativo', nunca abre janela de senha. Devolve (tem_nova, versao_nova, None, notas)."""
    env = None
    if not interativo:
        import os
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    r = subprocess.run(["git", "fetch", "-q"], cwd=PASTA, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=60,
                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    if r.returncode != 0:
        raise RuntimeError(f"não consegui falar com o GitHub ({(r.stderr or '').strip()[:150]})")
    novidades = _git("log", "--format=- %s", "HEAD..@{u}").stdout.strip()
    remota = _git("show", "@{u}:VERSAO.txt")
    nova = remota.stdout.strip() if remota.returncode == 0 else versao_atual()
    return bool(novidades), nova, None, novidades


def verificar(repo):
    """Devolve (tem_nova, versao_nova, url_zip, notas) ou levanta erro."""
    if em_git() and _git("rev-parse", "--abbrev-ref", "@{u}").returncode == 0:
        return verificar_git()                     # repositório com GitHub ligado: compara pelo git
    repo = repo.strip().removeprefix("https://github.com/").strip("/")
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "cortes916"})
    with urllib.request.urlopen(req, timeout=20) as r:
        rel = json.loads(r.read().decode("utf-8"))
    nova = rel.get("tag_name") or rel.get("name") or "0"
    zip_url = next((a["browser_download_url"] for a in rel.get("assets", []) if a["name"].endswith(".zip")),
                   rel.get("zipball_url"))
    return _tupla(nova) > _tupla(versao_atual()), nova.lstrip("v"), zip_url, rel.get("body") or ""


def _git(*args):
    return subprocess.run(["git", *args], cwd=PASTA, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


def em_git():
    """O projeto está num repositório git (com o programa git instalado)?"""
    return (PASTA / ".git").exists() and shutil.which("git") is not None


def mudancas_locais():
    """Arquivos do projeto alterados e ainda não salvos (commit) no git."""
    r = _git("status", "--porcelain", "--untracked-files=no")
    return [linha[3:] for linha in r.stdout.splitlines() if linha.strip()]


def _instalar_requisitos(antes, log):
    depois = (PASTA / "requirements.txt").read_text(encoding="utf-8") if (PASTA / "requirements.txt").exists() else ""
    if depois != antes:
        log("Instalando bibliotecas novas...")
        py = sys.executable.replace("pythonw.exe", "python.exe")
        subprocess.run([py, "-m", "pip", "install", "-r", str(PASTA / "requirements.txt")],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


def _aplicar_git(log):
    """Projeto no git: atualiza com 'git pull' — nunca sobrescreve mudança local."""
    pendentes = mudancas_locais()
    if pendentes:
        raise RuntimeError(f"{len(pendentes)} arquivo(s) foram alterados aqui e ainda não estão salvos no git "
                           f"({', '.join(pendentes[:3])}{'...' if len(pendentes) > 3 else ''}). Salve (commit) "
                           "antes de atualizar, pra nada se perder.")
    req_antes = (PASTA / "requirements.txt").read_text(encoding="utf-8") if (PASTA / "requirements.txt").exists() else ""
    log("Projeto no git: atualizando com 'git pull' (o que é seu não é sobrescrito)...")
    r = _git("pull", "--ff-only")
    if r.returncode != 0:
        raise RuntimeError("O git não conseguiu juntar a versão nova com a sua (as duas mudaram). Nada foi "
                           f"alterado. Detalhe: {(r.stderr or r.stdout).strip()[:200]}")
    log("✅ " + ((r.stdout or "").strip().splitlines() or ["Atualizado."])[-1][:200])
    _instalar_requisitos(req_antes, log)
    log("Feche e abra o programa pra usar a versão nova.")
    return True


def aplicar(zip_url, nova, log=print):
    if em_git():                       # com git, o histórico protege tudo: nada de copiar por cima
        return _aplicar_git(log)
    log("Baixando a nova versão...")
    req = urllib.request.Request(zip_url, headers={"User-Agent": "cortes916"})
    with urllib.request.urlopen(req, timeout=120) as r:
        dados = r.read()
    z = zipfile.ZipFile(io.BytesIO(dados))
    # acha a pasta do projeto dentro do zip (a que tem o cortes.py)
    raiz = next((Path(n).parent for n in z.namelist() if n.endswith("cortes.py")), None)
    if raiz is None:
        raise RuntimeError("O zip da release não tem o cortes.py.")
    req_antes = (PASTA / "requirements.txt").read_text(encoding="utf-8") if (PASTA / "requirements.txt").exists() else ""
    backup = PASTA / "_versao_anterior"
    if backup.is_symlink() or (hasattr(backup, "is_junction") and backup.is_junction()) or not backup.resolve().is_relative_to(PASTA.resolve()):
        raise RuntimeError("Pasta de backup fora do projeto.")
    shutil.rmtree(backup, ignore_errors=True)
    backup.mkdir()
    trocados = 0
    for nome in z.namelist():
        caminho = Path(nome)
        if nome.endswith("/") or raiz not in caminho.parents and caminho.parent != raiz:
            continue
        rel = caminho.relative_to(raiz)
        if ".." in rel.parts or rel.is_absolute() or not (PASTA / rel).resolve().is_relative_to(PASTA.resolve()):
            raise RuntimeError("A atualização contém caminho fora do projeto.")
        if rel.name.endswith((".sqlite3", ".sqlite3-wal", ".sqlite3-shm", ".lock")) or rel.parts[0].startswith("_backup_"):
            continue
        if rel.name in PROTEGIDOS or (rel.parts and rel.parts[0] in PASTAS_PROTEGIDAS) or rel.name.startswith("token_youtube"):
            continue
        destino = PASTA / rel
        if destino.exists():
            (backup / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destino, backup / rel)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(z.read(nome))
        trocados += 1
    ARQ_VERSAO.write_text(nova + "\n", encoding="utf-8")
    log(f"✅ {trocados} arquivo(s) atualizados (cópia da versão anterior em _versao_anterior).")
    _instalar_requisitos(req_antes, log)
    log("Feche e abra o programa pra usar a versão nova.")
    return True
